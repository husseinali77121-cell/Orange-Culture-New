# orange_cdss.spec — PyInstaller build spec, Orange Lab Microbiology CDSS
#
# Built and run on windows-latest by .github/workflows/build-exe.yml, which
# is also where Tesseract/GTK3/fonts get staged into the local folders this
# spec expects (tesseract/, gtk3-runtime/, fonts/ — see that workflow for
# exactly where each comes from). This file assumes those folders already
# exist relative to it when PyInstaller runs; it does not download anything
# itself.
#
# Run locally (Windows, after staging the three folders above by hand):
#   pip install pyinstaller
#   pyinstaller orange_cdss.spec --clean
#
# WHY A .spec FILE AND NOT A ONE-LINE `pyinstaller launcher.py`:
# Streamlit does not get frozen the normal PyInstaller way. streamlit_app.py
# and every sibling module it imports (ast_qa_engine.py, clinical_data.py,
# organism_profile.py, ...) must exist as REAL, LOOSE .py FILES on disk next
# to each other inside the bundle — Streamlit's CLI opens streamlit_app.py by
# filesystem path and execs it, and that exec then does normal `import
# ast_qa_engine`-style imports that need real files to find, not PyInstaller's
# compiled-into-the-exe module cache. So every application module is listed
# under `datas` below (bundled as loose files) in addition to being picked up
# by PyInstaller's own import analysis for their third-party dependencies.
#
# 2026-11-12 — the application is now streamlit_app.py (entry point) plus the
# packages cdss/ (clinical engine) and cdss_ui/ (Streamlit page). Both trees are
# bundled as loose files AND declared as hidden imports, and both are DISCOVERED
# by walking the directories below -- there is no module list to keep in sync.
# (The list this replaced had fallen behind: therapy_rules.py and
# final_checklist.py were imported by the app and absent from the bundle.)
# NOT YET VERIFIED BY A REAL BUILD: this layout has not been through
# build-exe.yml on windows-latest. Run that workflow once before shipping an exe.
#
# 2026-10-19 — what changed and why (first run that reached the frozen exe
# failed with "exe did not serve a page"):
#   1. Packages with data files / metadata / native pieces are collected
#      WHOLE (collect_all): streamlit (its static/ web frontend and its
#      dist-info metadata — without the frontend the server answers 404 and
#      without the metadata importlib.metadata.version("streamlit") raises),
#      weasyprint (its built-in CSS), pyphen (hyphenation dictionaries),
#      arabic_reshaper (default-config.ini), bidi (native extension), cv2.
#   2. pandas is no longer excluded. It is unused by THIS repo, but it is a
#      hard dependency of Streamlit itself; excluding it can break
#      `import streamlit` inside the bundle. ~40 MB is the price of a server
#      that starts.
#   3. The app modules are also passed to Analysis as hidden imports, so
#      PyInstaller traces THEIR imports too (stdlib modules such as difflib
#      that nothing else imports would otherwise be left out of the bundle and
#      only fail later, inside the script, as ModuleNotFoundError).
#   The exe stays windowed (console=False); launcher.py writes a log file
#   instead — see its header.

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

block_cipher = None
ROOT = os.path.dirname(os.path.abspath(SPEC))

# ── Application source: every non-test .py module, as LOOSE files ──────────
# (see the note above for why these are `datas`, not left to Analysis alone)
# The application is `streamlit_app.py` (a three-line entry point) plus two
# packages: cdss/ (the clinical engine) and cdss_ui/ (the Streamlit page).
# They are DISCOVERED by walking the tree -- never listed by hand. The hand-kept
# list this replaces had silently fallen behind: therapy_rules.py and
# final_checklist.py were imported by the app and missing from the bundle.
APP_PACKAGES = ["cdss", "cdss_ui"]
APP_ROOT_FILES = ["streamlit_app.py", "launcher.py"]

datas = [(m, ".") for m in APP_ROOT_FILES if os.path.exists(os.path.join(ROOT, m))]
APP_MODULE_NAMES = []          # dotted names, for hiddenimports below
for _pkg in APP_PACKAGES:
    for _dirpath, _dirnames, _filenames in os.walk(os.path.join(ROOT, _pkg)):
        _dirnames[:] = [d for d in _dirnames if d != "__pycache__"]
        _rel = os.path.relpath(_dirpath, ROOT)
        for _fn in sorted(_filenames):
            if _fn.endswith((".py", ".txt", ".json")):
                datas.append((os.path.join(_rel, _fn), _rel))
            if _fn.endswith(".py"):
                _mod = _rel.replace(os.sep, ".") + ("" if _fn == "__init__.py" else "." + _fn[:-3])
                APP_MODULE_NAMES.append(_mod)
if not any(d[0].endswith("commercial_names.txt") for d in datas):
    raise SystemExit("orange_cdss.spec: cdss/formulary/commercial_names.txt is missing")

# Tesseract (binary + English/Arabic tessdata), GTK3 runtime (WeasyPrint's
# PDF rendering dependency — see build-exe.yml for why this is the highest-
# risk single piece of this bundle), and fonts. Staged by the CI workflow
# before this spec runs; included here only if actually present, so a local
# test build without them still produces a runnable (if OCR/PDF-limited) exe
# rather than failing the whole build over a missing font folder.
for folder, dest in (("tesseract", "tesseract"), ("gtk3-runtime", "gtk3-runtime"),
                     ("fonts", "fonts")):
    src = os.path.join(ROOT, folder)
    if os.path.isdir(src):
        for dirpath, _, filenames in os.walk(src):
            rel = os.path.relpath(dirpath, ROOT)
            for fn in filenames:
                datas.append((os.path.join(dirpath, fn), rel))

# ── Third-party packages that must be bundled WHOLE ────────────────────────
# collect_all = data files + native libs + every submodule + dist-info
# metadata. A package that is not installed on the build machine is skipped
# with a warning instead of failing the build (some of these are
# version-dependent, e.g. WeasyPrint <65 uses html5lib, >=65 uses tinyhtml5).
COLLECT_ALL_PACKAGES = [
    "streamlit",         # static/ frontend + metadata: the server needs both
    "weasyprint",        # built-in UA stylesheets
    "pyphen",            # hyphenation dictionaries
    "tinycss2", "cssselect2", "tinyhtml5", "html5lib", "webencodings",
    "pydyf", "fontTools",
    "arabic_reshaper",   # default-config.ini
    "bidi",              # python-bidi: native extension
    "cv2",
    "pytesseract",
    "tzdata",            # v7.6: Windows has no tz database; lab_today() reads Africa/Cairo
]

collected_datas, collected_binaries, collected_hidden = [], [], []
for _pkg in COLLECT_ALL_PACKAGES:
    try:
        _d, _b, _h = collect_all(_pkg)
    except Exception as _exc:
        print(f"[orange_cdss.spec] note: collect_all({_pkg!r}) skipped: {_exc}")
        continue
    collected_datas += _d
    collected_binaries += _b
    collected_hidden += _h

# Streamlit reads its own version through importlib.metadata at startup;
# make doubly sure its dist-info is present.
try:
    collected_datas += copy_metadata("streamlit")
except Exception as _exc:
    print(f"[orange_cdss.spec] WARNING: copy_metadata('streamlit') failed: {_exc}")

hiddenimports = [
    # Modules imported inside try/except ImportError blocks in
    # streamlit_app.py -- PyInstaller's static analysis usually catches
    # these anyway, but listed explicitly so a build never silently drops
    # one of the AST QC modules over an analysis edge case.
    # Streamlit's own runtime pulls in a lot dynamically; the ones below are
    # the ones known to occasionally get missed by PyInstaller's hooks.
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "pytesseract", "cv2", "PIL", "weasyprint",
    "arabic_reshaper", "bidi", "bidi.algorithm",
    "_cffi_backend",     # WeasyPrint loads Pango/Cairo through cffi
]
# Trace the application modules' own imports (loose copies in `datas` are
# invisible to Analysis). launcher.py is the entry script, so it is skipped.
hiddenimports += ["streamlit_app"] + APP_MODULE_NAMES
hiddenimports += collected_hidden

a = Analysis(
    ["launcher.py"],
    pathex=[ROOT],
    binaries=collected_binaries,
    datas=datas + collected_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Explicitly NOT bundled -- see requirements.txt's own note: these
        # were declared but never imported anywhere in the app, and only
        # widen the exe for nothing. Excluding them here (rather than just
        # not installing them) protects against PyInstaller pulling one in
        # transitively through some other package's optional dependency.
        #
        # pandas is deliberately NOT in this list any more (2026-10-19):
        # the app never imports it, but Streamlit itself requires it.
        "fpdf", "sklearn", "reportlab",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Orange-CDSS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX + antivirus false-positives on lab workstations
    console=False,       # windowed -- the browser tab IS the UI; launcher.py logs to a file
    icon=None,            # add an .ico path here once Hussein has one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Orange-CDSS",
)
