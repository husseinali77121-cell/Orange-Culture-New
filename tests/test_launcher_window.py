"""The exe's own window (v6.5).

launcher.py opens the app in an Edge/Chrome APP WINDOW (no address bar, no tabs,
its own profile), stops the server when that window is closed, opens one more
window on the running server instead of a second server, and reads the login
data from a secrets.toml placed next to the exe.

The last test drives a REAL Chromium-family browser with a real window. It runs
where there is a display (Linux with DISPLAY, e.g. under xvfb-run) and is skipped
elsewhere; on Windows set ORANGE_CDSS_WINDOW_TEST=1 to run it against Edge.
"""
import http.server
import json
import os
import pathlib
import socket
import sys
import threading
import time
import types
import urllib.request

import pytest

import launcher

ROOT = pathlib.Path(__file__).resolve().parents[1]
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("ORANGE_CDSS_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    """A local page standing in for Streamlit, with its health endpoint."""

    def __init__(self, port=0):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"ok" if self.path.startswith("/_stcore/health") else \
                    b"<title>Microbiology CDSS</title><h1>Orange CDSS</h1>"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain" if body == b"ok" else "text/html")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def page():
    s = _Server()
    yield s
    s.stop()


# ── which browser ──────────────────────────────────────────────────────────
def _fake_install(root, *parts):
    p = root.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"MZ")
    return str(p)


def test_edge_is_preferred_then_chrome_then_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    pf86, pf, local = tmp_path / "pf86", tmp_path / "pf", tmp_path / "appdata"
    monkeypatch.setenv("PROGRAMFILES(X86)", str(pf86))
    monkeypatch.setenv("PROGRAMFILES", str(pf))
    chrome = _fake_install(local, "Google", "Chrome", "Application", "chrome.exe")   # per-user Chrome
    edge = _fake_install(pf86, "Microsoft", "Edge", "Application", "msedge.exe")
    assert launcher._find_app_browser() == edge
    os.remove(edge)
    assert launcher._find_app_browser() == chrome
    os.remove(chrome)
    assert launcher._find_app_browser() == ""


def test_an_explicit_browser_path_wins_only_if_it_exists(tmp_path, monkeypatch):
    mine = _fake_install(tmp_path, "my", "browser.exe")
    monkeypatch.setenv("ORANGE_CDSS_APP_BROWSER", mine)
    assert launcher._find_app_browser() == mine
    monkeypatch.setenv("ORANGE_CDSS_APP_BROWSER", mine + ".missing")
    assert launcher._find_app_browser() == ""


def test_the_window_has_no_address_bar_and_its_own_profile(monkeypatch):
    monkeypatch.setenv("ORANGE_CDSS_WINDOW_FLAGS", "--extra-one --extra-two")
    cmd = launcher._window_command("edge.exe", "http://127.0.0.1:8501", "C:/p")
    assert cmd[0] == "edge.exe"
    assert "--app=http://127.0.0.1:8501" in cmd            # app mode: no address bar, no tabs
    assert "--user-data-dir=C:/p" in cmd                    # never the user's own browser profile
    assert {"--no-first-run", "--no-default-browser-check", "--disable-background-mode"} <= set(cmd)
    assert cmd[-2:] == ["--extra-one", "--extra-two"]


def test_the_window_gets_the_original_path_not_the_bundle_dll_folders(tmp_path, monkeypatch):
    browser = _fake_install(tmp_path, "edge", "msedge.exe")
    monkeypatch.setenv("ORANGE_CDSS_APP_BROWSER", browser)
    monkeypatch.setattr(launcher, "_ORIGINAL_PATH", "C:/Windows/system32")
    monkeypatch.setenv("PATH", "C:/bundle/gtk3-runtime/bin;C:/Windows/system32")
    monkeypatch.setenv("TESSDATA_PREFIX", "C:/bundle/tesseract/tessdata")
    seen = {}

    class FakePopen:
        pid = 4242

        def __init__(self, cmd, **kw):
            seen.update(cmd=cmd, **kw)

    monkeypatch.setattr(launcher.subprocess, "Popen", FakePopen)
    proc = launcher._open_app_window("http://127.0.0.1:8501")
    assert isinstance(proc, FakePopen)
    assert seen["env"]["PATH"] == "C:/Windows/system32"
    assert "TESSDATA_PREFIX" not in seen["env"]
    profile = pathlib.Path(launcher._state_dir()) / "window-profile"
    assert f"--user-data-dir={profile}" in seen["cmd"] and profile.is_dir()


def test_no_browser_installed_means_no_window(monkeypatch):
    monkeypatch.setattr(launcher, "_find_app_browser", lambda: "")
    assert launcher._open_app_window("http://127.0.0.1:8501") is None


# ── what the end of the window means ──────────────────────────────────────
class _Proc:
    def __init__(self, lives, code):
        self.lives, self.code = lives, code

    def wait(self):
        time.sleep(self.lives)
        return self.code


@pytest.mark.parametrize("lives,code,outcome", [
    (0.4, 0, "closed"),      # the user used the window, then closed it
    (0.4, 1, "closed"),      # closed is closed, whatever the exit code
    (0.0, 0, "handoff"),     # an app window was already open and took this one
    (0.0, 21, "failed"),     # the browser would not start
])
def test_watching_the_window(lives, code, outcome):
    calls = []
    got = launcher._watch_window(_Proc(lives, code), lambda: calls.append("closed"),
                                 lambda: calls.append("failed"), handoff_seconds=0.2)
    assert got == outcome
    assert calls == ([outcome] if outcome != "handoff" else [])


def test_show_watches_only_the_window_it_serves(monkeypatch):
    opened, threads, browser = [], [], []
    monkeypatch.setattr(launcher, "_open_app_window", lambda url: opened.append(url) or object())
    monkeypatch.setattr(launcher.webbrowser, "open", browser.append)

    class T:
        def __init__(self, target, daemon, args):
            threads.append(target)

        def start(self):
            pass

    monkeypatch.setattr(launcher.threading, "Thread", T)
    launcher._show("http://a", watch=True)
    launcher._show("http://b", watch=False)
    assert opened == ["http://a", "http://b"] and threads == [launcher._watch_window] and browser == []


def test_browser_switch_and_fallback(monkeypatch):
    browser = []
    monkeypatch.setattr(launcher.webbrowser, "open", browser.append)
    monkeypatch.setattr(launcher, "_open_app_window", lambda url: None)      # no Edge / Chrome
    launcher._show("http://fallback", watch=True)
    monkeypatch.setattr(launcher, "_open_app_window", lambda url: pytest.fail("window opened"))
    monkeypatch.setattr(sys, "argv", ["Orange-CDSS.exe", "--browser"])
    launcher._show("http://asked-for", watch=True)
    monkeypatch.setattr(sys, "argv", ["Orange-CDSS.exe"])
    monkeypatch.setenv("ORANGE_CDSS_BROWSER", "default")
    launcher._show("http://env", watch=True)
    assert browser == ["http://fallback", "http://asked-for", "http://env"]


# ── one server per user ───────────────────────────────────────────────────
def test_a_running_server_is_found(page):
    launcher._record_instance(page.port)
    assert launcher._running_instance() == page.url


def test_a_server_that_is_still_starting_is_waited_for(monkeypatch):
    port = _free_port()
    launcher._record_instance(port)               # written before Streamlit is up
    later = []
    threading.Timer(1.0, lambda: later.append(_Server(port))).start()
    try:
        t = time.monotonic()
        assert launcher._running_instance(grace=15, poll=0.2) == f"http://127.0.0.1:{port}"
        assert time.monotonic() - t >= 0.9
    finally:
        for s in later:
            s.stop()


def test_a_dead_server_is_not_waited_for(monkeypatch):
    port = _free_port()
    os.makedirs(launcher._state_dir(), exist_ok=True)
    with open(launcher._instance_file(), "w") as fh:     # left behind by a server killed an hour ago
        json.dump({"port": port, "pid": 1, "started": time.time() - 3600}, fh)
    t = time.monotonic()
    assert launcher._running_instance() == ""
    assert time.monotonic() - t < 5
    os.remove(launcher._instance_file())
    assert launcher._running_instance() == ""          # no file at all


def test_the_health_check_ignores_a_configured_proxy(page, monkeypatch):
    for k in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(k, "http://127.0.0.1:9")    # nothing listens there
    for k in ("no_proxy", "NO_PROXY"):
        monkeypatch.delenv(k, raising=False)
    assert launcher._healthy(page.url)


def test_only_the_owner_removes_the_instance_file():
    launcher._record_instance(1234)
    with open(launcher._instance_file()) as fh:
        data = json.load(fh)
    data["pid"] = os.getpid() + 1                      # another launcher's file
    with open(launcher._instance_file(), "w") as fh:
        json.dump(data, fh)
    launcher._forget_instance()
    assert os.path.exists(launcher._instance_file())
    launcher._record_instance(1234)
    launcher._forget_instance()
    assert not os.path.exists(launcher._instance_file())


def _fake_streamlit(monkeypatch, calls):
    st, web, cli = (types.ModuleType(n) for n in ("streamlit", "streamlit.web", "streamlit.web.cli"))
    cli.main = lambda: calls.append(list(sys.argv)) or 0
    st.web, web.cli = web, cli
    for m in (st, web, cli):
        monkeypatch.setitem(sys.modules, m.__name__, m)


def test_a_second_start_opens_a_window_on_the_running_server(monkeypatch):
    shown, started = [], []
    _fake_streamlit(monkeypatch, started)
    monkeypatch.setattr(sys, "argv", ["Orange-CDSS.exe"])
    monkeypatch.setattr(launcher, "_running_instance", lambda: "http://127.0.0.1:8501")
    monkeypatch.setattr(launcher, "_show", lambda url, watch: shown.append((url, watch)))
    assert launcher._serve(str(ROOT), "") == 0
    assert shown == [("http://127.0.0.1:8501", False)] and started == []


def test_a_first_start_records_itself_and_serves(monkeypatch):
    started = []
    _fake_streamlit(monkeypatch, started)
    monkeypatch.setattr(sys, "argv", ["Orange-CDSS.exe"])
    monkeypatch.setattr(launcher, "_running_instance", lambda: "")
    monkeypatch.setattr(launcher.threading, "Thread",
                        lambda **kw: types.SimpleNamespace(start=lambda: None))
    assert launcher._serve(str(ROOT), "") == 0
    with open(launcher._instance_file()) as fh:
        port = json.load(fh)["port"]
    assert started and "--server.port" in started[0] and str(port) in started[0]


def test_ci_runs_touch_neither_windows_nor_the_instance_file(monkeypatch):
    started = []
    _fake_streamlit(monkeypatch, started)
    monkeypatch.setenv("ORANGE_CDSS_NO_BROWSER", "1")
    monkeypatch.setattr(sys, "argv", ["Orange-CDSS.exe"])
    monkeypatch.setattr(launcher, "_running_instance", lambda: pytest.fail("looked for an instance"))
    monkeypatch.setattr(launcher.threading, "Thread",
                        lambda **kw: types.SimpleNamespace(start=lambda: None))
    assert launcher._serve(str(ROOT), "") == 0 and started
    assert not os.path.exists(launcher._instance_file())


# ── secrets.toml next to the exe ──────────────────────────────────────────
SECRETS = ('# المشتركون\nsubscribers = \'{"lab@x.com": "2035-12-31"}\'\n'
           'subscriber_hashes = \'{"lab@x.com": "pbkdf2_sha256$1$c2FsdA==$aGFzaA=="}\'\n')


@pytest.fixture
def dirs(tmp_path):
    base, exe = tmp_path / "Orange-CDSS" / "_internal", tmp_path / "Orange-CDSS"
    base.mkdir(parents=True)
    return base, exe, base / ".streamlit" / "secrets.toml"


@pytest.mark.parametrize("name,data", [
    ("secrets.toml", SECRETS.encode("utf-8")),
    ("secrets.toml.txt", b"\xef\xbb\xbf" + SECRETS.encode("utf-8")),      # Notepad: hidden .txt + BOM
    ("secrets.txt", SECRETS.encode("cp1256")),                            # Notepad: ANSI (Arabic Windows)
])
def test_secrets_next_to_the_exe_are_used(dirs, name, data):
    tomllib = pytest.importorskip("tomllib")
    base, exe, dst = dirs
    (exe / name).write_bytes(data)
    assert "login data from" in launcher._use_local_secrets(str(base), str(exe))
    got = tomllib.loads(dst.read_text(encoding="utf-8"))
    assert json.loads(got["subscribers"]) == {"lab@x.com": "2035-12-31"}
    assert not dst.read_bytes().startswith(b"\xef\xbb\xbf")


def test_removing_the_secrets_file_removes_the_copy(dirs):
    base, exe, dst = dirs
    (exe / "secrets.toml").write_text(SECRETS, encoding="utf-8")
    launcher._use_local_secrets(str(base), str(exe))
    os.remove(exe / "secrets.toml")
    assert "nobody can log in" in launcher._use_local_secrets(str(base), str(exe))
    assert not dst.exists()


def test_a_broken_secrets_file_is_reported_not_used(dirs):
    pytest.importorskip("tomllib")
    base, exe, dst = dirs
    (exe / "secrets.toml").write_text(SECRETS, encoding="utf-8")
    launcher._use_local_secrets(str(base), str(exe))
    (exe / "secrets.toml").write_text('subscribers = \'{"a@b.c": "2035-12-31"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="not valid TOML"):
        launcher._use_local_secrets(str(base), str(exe))
    assert not dst.exists()


def test_source_runs_never_touch_a_developers_secrets(monkeypatch, tmp_path):
    """Only the frozen exe copies secrets: from source the exe folder IS the repo."""
    called = []
    monkeypatch.setattr(launcher, "_setup_logging", lambda: "")
    monkeypatch.setattr(launcher, "_use_local_secrets", lambda *a: called.append(a) or "")
    monkeypatch.setattr(launcher, "_serve", lambda base, log: 0)
    monkeypatch.setattr(launcher, "_configure_environment", lambda base: None)
    monkeypatch.setattr(launcher.os, "chdir", lambda p: None)
    monkeypatch.setattr(sys, "argv", ["launcher.py"])
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert launcher.main() == 0 and called == []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert launcher.main() == 0 and len(called) == 1


# ── a real browser, a real window ─────────────────────────────────────────
def _real_window_possible():
    if os.name == "nt":
        return os.environ.get("ORANGE_CDSS_WINDOW_TEST") == "1"
    return bool(os.environ.get("DISPLAY"))


def _pages(cdp):
    with NO_PROXY.open(f"http://127.0.0.1:{cdp}/json", timeout=5) as r:
        return [t for t in json.load(r) if t.get("type") == "page"]


def _wait(cond, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if cond():
                return True
        except OSError:
            pass
        time.sleep(0.25)
    return False


@pytest.mark.skipif(not _real_window_possible(), reason="needs a display (Linux) or "
                    "ORANGE_CDSS_WINDOW_TEST=1 (Windows)")
def test_a_real_app_window_lives_hands_off_and_stops_the_server_when_closed(page, monkeypatch):
    if not launcher._find_app_browser():
        pytest.skip("no Edge / Chrome on this machine")
    cdp = _free_port()
    flags = f"--remote-debugging-port={cdp}"
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        flags += " --no-sandbox"                     # Chromium refuses to run as root otherwise
    monkeypatch.setenv("ORANGE_CDSS_WINDOW_FLAGS", flags)
    closed, failed = threading.Event(), threading.Event()

    first = launcher._open_app_window(page.url)
    assert first is not None
    try:
        watcher = threading.Thread(target=launcher._watch_window, daemon=True,
                                   args=(first, closed.set, failed.set))
        watcher.start()
        assert _wait(lambda: any(p["url"].startswith(page.url) for p in _pages(cdp)), 30), \
            "the app window never showed the page"
        time.sleep(launcher.HANDOFF_SECONDS)
        assert first.poll() is None and not closed.is_set(), "the window's process ended on its own"

        # a second start while the window is open: same profile -> handed to the first
        second = launcher._open_app_window(page.url)
        assert launcher._watch_window(second, pytest.fail, pytest.fail) == "handoff"
        assert _wait(lambda: len(_pages(cdp)) == 2, 15), "the second window did not open"
        assert first.poll() is None

        # the user closes both windows -> the first process ends -> "closed"
        for p in _pages(cdp):
            NO_PROXY.open(f"http://127.0.0.1:{cdp}/json/close/{p['id']}", timeout=5).read()
            time.sleep(0.5)
        assert closed.wait(30), "closing every window did not end the browser process"
        assert not failed.is_set()
    finally:
        if first.poll() is None:
            first.kill()
