#!/usr/bin/env python3
"""verify_upload.py — is the code in this checkout the release it claims to be?

Added 2026-11-11. A release that is uploaded file by file (GitHub web upload,
especially from a phone) can silently keep an OLD copy of one file. The test
suites then fail with a message about clinical logic, while the real cause is
a stale file. This script compares every file against RELEASE_MANIFEST.sha256
and names the ones that differ.

Line endings are normalised before hashing (a Windows checkout converts LF to
CRLF), so the same release gives the same hashes on every runner.

Since 2026-11-13 it also names EXTRA files: a file that is not part of the
release, typically a release file uploaded into the wrong folder (on the first
upload of v6.1 `streamlit_app.py` and `page_setup.py` landed inside `cdss/`,
and four test failures were the only symptom). When an extra file has the name
of a release file, the line says where that file belongs.

Usage:  python verify_upload.py            report only, always exits 0
        python verify_upload.py --strict   exit 1 if anything differs
        python verify_upload.py --write    regenerate the manifest (release step)
"""
import hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "RELEASE_MANIFEST.sha256")
SKIP_DIRS = {".git", "__pycache__", "build", "dist", ".venv", "venv", ".pytest_cache"}
SKIP_FILES = {"RELEASE_MANIFEST.sha256"}


def _digest(path):
    with open(path, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _files():
    for root, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for n in sorted(files):
            if (n in SKIP_FILES and root == HERE) or n.endswith((".pyc", ".exe")) or (
                    n.endswith(".spec") and n != "orange_cdss.spec"):
                continue
            p = os.path.join(root, n)
            yield os.path.relpath(p, HERE).replace(os.sep, "/"), p


def main():
    if "--write" in sys.argv:
        with open(MANIFEST, "w", encoding="utf-8", newline="\n") as m:
            for rel, p in _files():
                m.write(f"{_digest(p)}  {rel}\n")
        print(f"manifest written: {MANIFEST}")
        return 0
    if not os.path.exists(MANIFEST):
        print("verify_upload: no RELEASE_MANIFEST.sha256 — nothing to compare.")
        return 0
    expected = {}
    with open(MANIFEST, encoding="utf-8") as m:
        release = ""
        for line in m:
            line = line.rstrip("\n")
            if line.startswith("#"):
                release = release or line.lstrip("# ")
                continue
            if line.strip():
                h, rel = line.split("  ", 1)
                expected[rel] = h
    stale, missing = [], []
    for rel, h in expected.items():
        p = os.path.join(HERE, rel)
        if not os.path.exists(p):
            missing.append(rel)
        elif _digest(p) != h:
            stale.append(rel)
    home_of = {}                                   # file name -> its release path(s)
    for rel in expected:
        home_of.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)
    extra = [rel for rel, _p in _files() if rel not in expected]
    print(f"verify_upload: {len(expected)} files in the release manifest {release}".rstrip())
    if not stale and not missing and not extra:
        print("  OK — every file matches the release.")
        return 0
    for rel in missing:
        print(f"  MISSING  {rel}")
    for rel in stale:
        print(f"  DIFFERS  {rel}   (old copy, or edited after the release)")
    for rel in extra:
        homes = [h for h in home_of.get(rel.rsplit("/", 1)[-1], []) if h != rel]
        where = f"   -> wrong folder? this file belongs at: {', '.join(homes)}" if homes \
            else "   (not part of the release)"
        print(f"  EXTRA    {rel}{where}")
    if missing or stale:
        print("  -> Re-upload the MISSING / DIFFERS files from the release zip, then re-run.")
    if extra:
        print("  -> Delete the EXTRA files that were uploaded into the wrong folder.")
    return 1 if "--strict" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
