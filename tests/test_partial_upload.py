# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""A half-finished upload must never leave the running app in a degraded state.

Regression, 2026-11-13: cdss/therapy/ was missing after the first browser upload.
The app failed (correctly), but cdss.health had already been imported with
SAFETY_GATE_AVAILABLE = False. Streamlit keeps one Python process across reruns,
so after the folder WAS uploaded the app kept running -- with the terminal
safety gate switched off -- until it was rebooted by hand.

The test replays that sequence in a fresh process, on a copy of the repository:
run the entry point with cdss/therapy/ absent, put the folder back, run again.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]

SCRIPT = textwrap.dedent('''
    import os, shutil, sys, time, runpy
    sys.path.insert(0, os.getcwd())
    sys.path.insert(0, sys.argv[1])                 # tests/ -> support.fake_streamlit
    from support import fake_streamlit
    fake_streamlit.install()

    def run():
        try:
            runpy.run_path("streamlit_app.py", run_name="__main__")
            return "ok"
        except (fake_streamlit.Stop, fake_streamlit.Rerun):
            return "ok"
        except ImportError as exc:
            return "import-error: %s" % exc

    first = run()
    leftovers = sorted(m for m in sys.modules if m.split(".")[0] in ("cdss", "cdss_ui"))
    time.sleep(1.1)                                 # directory mtime must move on
    shutil.move("therapy_upload_later", os.path.join("cdss", "therapy"))
    second = run()
    import cdss.health, cdss.pipeline
    print("FIRST=" + first)
    print("LEFTOVERS=" + ",".join(leftovers))
    print("SECOND=" + second)
    print("GATE=%s,%s" % (cdss.health.SAFETY_GATE_AVAILABLE, cdss.pipeline.SAFETY_GATE_AVAILABLE))
''')


def test_first_run_after_the_missing_folder_arrives_is_complete(tmp_path):
    for item in ("cdss", "cdss_ui", "streamlit_app.py"):
        src = ROOT / item
        if src.is_dir():
            shutil.copytree(src, tmp_path / item, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(src, tmp_path / item)
    shutil.move(str(tmp_path / "cdss" / "therapy"), str(tmp_path / "therapy_upload_later"))
    (tmp_path / "replay.py").write_text(SCRIPT, encoding="utf-8")

    r = subprocess.run([sys.executable, "replay.py", str(ROOT / "tests")], cwd=tmp_path,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 0, r.stderr[-2000:]
    out = dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln and ln.split("=")[0].isupper())

    assert out["FIRST"].startswith("import-error"), "the app must not start without cdss/therapy"
    assert out["LEFTOVERS"] == "", f"half-imported modules survived the failed run: {out['LEFTOVERS']}"
    assert out["SECOND"] == "ok", out["SECOND"]
    assert out["GATE"] == "True,True", "the safety gate must be on in the first complete run"


def test_safety_gate_and_intrinsic_table_have_no_fallback():
    """They are imported unconditionally: there is no 'run without them' state to get stuck in."""
    import ast
    tree = ast.parse((ROOT / "cdss" / "health.py").read_text(encoding="utf-8"))
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for sub in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(sub, ast.ImportFrom):
                    guarded.add(sub.module)
    assert "cdss.therapy.safety_gate" not in guarded
    assert "cdss.therapy.clinical_matrix" not in guarded
    assert "cdss.organisms.clinical_data" not in guarded
