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

BLOCKING since 2026-11-13 (later the same day). Every failure of the first
uploads of v6.x was a broken UPLOAD -- a folder not uploaded, files dropped into
the wrong folder -- while this check stayed green and the real cause surfaced
three steps later as cryptic test errors. So the default run now exits 1 for
the two problems that can only mean a broken upload:
  * MISSING   an application file (cdss/, cdss_ui/, tests/, the root .py files,
              requirements, the EXE spec) is not there;
  * MISPLACED a release file sits in the wrong folder, or a stray .py file sits
              inside cdss/ or cdss_ui/.
  * OLD COPY  (added 2026-11-13, v6.4) an application file is byte-for-byte the
              version of an EARLIER release. The manifest keeps the hashes of
              every earlier version of each file ("#old" lines), so an old copy
              is told apart from an edit. This is how v6.3 failed: cdss/health.py
              on GitHub was still the v6 one, Guard 0 printed DIFFERS and let the
              build go on, and the symptom was one failing test two steps later.
A file that matches NO release (an edit made on GitHub) and other EXTRA files
stay report-only: an intentional edit must not block the build.

Usage:  python verify_upload.py            exit 1 only on a broken upload (above)
        python verify_upload.py --strict   exit 1 if anything differs at all
        python verify_upload.py --write [--release "v6.4 note"]
                                           regenerate the manifest; with --release
                                           (a new release) the hashes it replaces
                                           move to "#old", labelled with the
                                           release they came from
"""
import hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# A MISSING file under these paths breaks the app, its tests or the EXE build.
CRITICAL_PREFIXES = ("cdss/", "cdss_ui/", "tests/")
CRITICAL_ROOT_FILES = {"streamlit_app.py", "launcher.py", "verify_upload.py", "orange_cdss.spec",
                       "requirements.txt", "requirements-dev.txt", "packages.txt", "pytest.ini"}


def _critical(rel):
    return rel.startswith(CRITICAL_PREFIXES) or rel in CRITICAL_ROOT_FILES
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


def _read_manifest():
    """(release title, {path: hash}, {path: {old hash: release label}})"""
    release, expected, old = "", {}, {}
    if not os.path.exists(MANIFEST):
        return release, expected, old
    with open(MANIFEST, encoding="utf-8") as m:
        for line in m:
            line = line.rstrip("\n")
            if line.startswith("#old "):
                h, rel, label = (line[5:].split("  ") + ["", ""])[:3]
                old.setdefault(rel, {})[h] = label
            elif line.startswith("#"):
                release = release or line.lstrip("# ")
            elif line.strip():
                h, rel = line.split("  ", 1)
                expected[rel] = h
    return release, expected, old


def _label(release):
    """'release v6.3 2026-11-13 (...)' -> 'v6.3'"""
    words = release.split()
    return words[1] if len(words) > 1 and words[0] == "release" else (words[0] if words else "earlier")


def _write():
    release, previous, old = _read_manifest()
    prev_label = _label(release)
    new_release = "--release" in sys.argv
    if new_release:
        release = "release " + sys.argv[sys.argv.index("--release") + 1]
    current = {rel: _digest(p) for rel, p in _files()}
    # Only a NEW release turns the hashes it replaces into history. Re-writing the
    # manifest while a release is still being prepared records nothing: those
    # in-between versions never reached anybody, so they cannot be an "old copy".
    if new_release and _label(release) != prev_label:
        for rel, h in previous.items():
            if current.get(rel) != h:
                old.setdefault(rel, {}).setdefault(h, prev_label)
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as m:
        if release:
            m.write(f"# {release}\n")
        for rel, h in current.items():
            m.write(f"{h}  {rel}\n")
        for rel in sorted(old):
            for h, label in old[rel].items():
                if h != current.get(rel):
                    m.write(f"#old {h}  {rel}  {label}\n")
    print(f"manifest written: {MANIFEST}")
    return 0


def main():
    try:                       # a Windows console without UTF-8 must not crash on the Arabic line
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    if "--write" in sys.argv:
        return _write()
    if not os.path.exists(MANIFEST):
        print("verify_upload: no RELEASE_MANIFEST.sha256 — nothing to compare.")
        return 0
    release, expected, old = _read_manifest()
    stale, missing, outdated = [], [], {}
    for rel, h in expected.items():
        p = os.path.join(HERE, rel)
        if not os.path.exists(p):
            missing.append(rel)
        else:
            d = _digest(p)
            if d != h:
                stale.append(rel)
                if d in old.get(rel, {}):
                    outdated[rel] = old[rel][d] or "an earlier release"
    home_of = {}                                   # file name -> its release path(s)
    for rel in expected:
        home_of.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)
    home_of.setdefault("RELEASE_MANIFEST.sha256", ["RELEASE_MANIFEST.sha256"])   # not listed in itself
    extra = [rel for rel, _p in _files() if rel not in expected]
    print(f"verify_upload: {len(expected)} files in the release manifest {release}".rstrip())
    if not stale and not missing and not extra:
        print("  OK — every file matches the release.")
        return 0
    blocking = []
    for rel in missing:
        print(f"  MISSING  {rel}")
        if _critical(rel):
            blocking.append(f"MISSING    {rel}   -> upload it")
    for rel in stale:
        if rel in outdated:
            print(f"  DIFFERS  {rel}   (OLD COPY: this is the {outdated[rel]} version)")
            if _critical(rel):
                blocking.append(f"OLD COPY   {rel}   -> upload it again (what is there is the {outdated[rel]} version)")
        else:
            print(f"  DIFFERS  {rel}   (edited after the release)")
    for rel in extra:
        homes = [h for h in home_of.get(rel.rsplit("/", 1)[-1], []) if h != rel]
        where = f"   -> wrong folder? this file belongs at: {', '.join(homes)}" if homes \
            else "   (not part of the release)"
        print(f"  EXTRA    {rel}{where}")
        if homes:
            blocking.append(f"MISPLACED  {rel}   -> delete it (its place is {', '.join(homes)})")
        elif rel.endswith(".py") and rel.startswith(("cdss/", "cdss_ui/")):
            blocking.append(f"STRAY      {rel}   -> delete it (not part of the application)")
    if missing or stale:
        print("  -> Re-upload the MISSING / DIFFERS files from the release zip, then re-run.")
    if extra:
        print("  -> Delete the EXTRA files that were uploaded into the wrong folder.")
    if blocking:
        print()
        print("=" * 72)
        print("BROKEN UPLOAD -- fix these files first; nothing after this step can pass:")
        for line in blocking:
            print("  " + line)
        print("الرفع ناقص، أو فيه ملف بنسخة قديمة، أو ملفات في مكان غلط -- صلّح الملفات اللي فوق الأول.")
        print("=" * 72)
        return 1
    return 1 if "--strict" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
