# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""Guard 0 (verify_upload.py) must stop a broken upload at the first step.

Every failed run of the first v6.x uploads was a broken UPLOAD: cdss/therapy/
not uploaded; streamlit_app.py and page_setup.py dropped inside cdss/. Guard 0
stayed green each time and the cause surfaced later as cryptic test errors.
Each case below replays one of those uploads on a copy of the release.
"""
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture()
def release(tmp_path):
    """A copy of the release as it should be on GitHub."""
    dst = tmp_path / "repo"
    keep = [p for p in ROOT.iterdir() if p.name not in (".git", ".pytest_cache", "__pycache__")]
    dst.mkdir()
    for p in keep:
        if p.is_dir():
            shutil.copytree(p, dst / p.name, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        else:
            shutil.copy(p, dst / p.name)
    # The copy gets a manifest of its own: these tests check the CHECKER, and
    # must not fail because a document was edited on GitHub after the release.
    subprocess.run([sys.executable, "verify_upload.py", "--write"], cwd=dst, check=True,
                   capture_output=True)
    return dst


def guard0(repo, *args):
    r = subprocess.run([sys.executable, "verify_upload.py", *args], cwd=repo, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, r.stdout


def test_a_complete_upload_passes(release):
    code, out = guard0(release)
    assert code == 0 and "OK" in out, out


def test_a_folder_that_was_not_uploaded_blocks(release):
    shutil.rmtree(release / "cdss" / "therapy")                     # what happened first
    code, out = guard0(release)
    assert code == 1
    assert "MISSING    cdss/therapy/engine.py" in out and "BROKEN UPLOAD" in out


def test_files_uploaded_into_the_wrong_folder_block_and_say_where_they_belong(release):
    shutil.copy(release / "streamlit_app.py", release / "cdss" / "streamlit_app.py")   # what happened next
    shutil.copy(release / "cdss_ui" / "page_setup.py", release / "cdss" / "page_setup.py")
    shutil.copy(release / "RELEASE_MANIFEST.sha256", release / "cdss" / "RELEASE_MANIFEST.sha256")
    code, out = guard0(release)
    assert "MISPLACED  cdss/RELEASE_MANIFEST.sha256" in out
    assert code == 1
    assert "MISPLACED  cdss/streamlit_app.py   -> delete it (its place is streamlit_app.py)" in out
    assert "MISPLACED  cdss/page_setup.py   -> delete it (its place is cdss_ui/page_setup.py)" in out


def test_a_stray_python_file_inside_the_engine_blocks(release):
    (release / "cdss" / "my_notes.py").write_text("x = 1\n", encoding="utf-8")
    code, out = guard0(release)
    assert code == 1 and "STRAY      cdss/my_notes.py" in out


def test_an_edited_file_is_reported_but_does_not_block(release):
    readme = release / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nedited on GitHub\n", encoding="utf-8")
    (release / "cdss" / "health.py").write_text(
        (release / "cdss" / "health.py").read_text(encoding="utf-8") + "\n# local edit\n", encoding="utf-8")
    code, out = guard0(release)
    assert code == 0, out
    assert "DIFFERS  README.md" in out and "DIFFERS  cdss/health.py" in out
    assert guard0(release, "--strict")[0] == 1


def test_a_missing_document_does_not_block(release):
    (release / "AUDIT.md").unlink()
    code, out = guard0(release)
    assert code == 0 and "MISSING  AUDIT.md" in out


def test_windows_line_endings_are_not_a_difference(release):
    p = release / "cdss" / "pipeline.py"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert guard0(release)[0] == 0


def test_a_file_left_at_an_earlier_release_blocks(release):
    """What happened with v6.3: cdss/health.py on GitHub was still the v6 copy."""
    health = release / "cdss" / "health.py"
    now = health.read_text(encoding="utf-8")
    earlier = now + "\n# the earlier release's version\n"
    guard_write = lambda title: subprocess.run(                              # noqa: E731
        [sys.executable, "verify_upload.py", "--write", "--release", title],
        cwd=release, check=True, capture_output=True)
    health.write_text(earlier, encoding="utf-8")
    guard_write("vTEST-1 the earlier release")
    health.write_text(now, encoding="utf-8")
    guard_write("vTEST-2 the current release")
    assert guard0(release)[0] == 0

    health.write_text(earlier, encoding="utf-8")                            # the stale upload
    code, out = guard0(release)
    assert code == 1
    assert "OLD COPY   cdss/health.py   -> upload it again (what is there is the vTEST-1 version)" in out

    health.write_text(now + "\n# an edit made on GitHub, never released\n", encoding="utf-8")
    code, out = guard0(release)
    assert code == 0 and "DIFFERS  cdss/health.py   (edited after the release)" in out


def test_regenerating_the_manifest_keeps_the_history(release):
    manifest = release / "RELEASE_MANIFEST.sha256"
    before = [ln for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.startswith("#old ")]
    subprocess.run([sys.executable, "verify_upload.py", "--write"], cwd=release, check=True,
                   capture_output=True)
    after = [ln for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.startswith("#old ")]
    assert before and before == after


def test_the_shipped_manifest_knows_every_earlier_release():
    lines = (ROOT / "RELEASE_MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
    old = {}
    for ln in lines:
        if ln.startswith("#old "):
            _h, rel, label = ln[5:].split("  ")
            old.setdefault(rel, set()).add(label)
    assert "v6" in old.get("cdss/health.py", set()), "the v6 health.py (mandatory-gate regression) must be recognised"
    assert {"single-file", "v6"} <= old.get("streamlit_app.py", set())


def test_rewriting_during_a_release_records_no_history(release):
    """In-between versions of a release never reached anybody: not an 'old copy'."""
    notes = release / "cdss" / "health.py"
    notes.write_text(notes.read_text(encoding="utf-8") + "\n# work in progress\n", encoding="utf-8")
    manifest = release / "RELEASE_MANIFEST.sha256"
    before = [ln for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.startswith("#old ")]
    subprocess.run([sys.executable, "verify_upload.py", "--write"], cwd=release, check=True,
                   capture_output=True)
    after = [ln for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.startswith("#old ")]
    assert after == before
