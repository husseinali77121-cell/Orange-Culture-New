# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""What gets shipped: the EXE spec must carry every module, without a hand-kept list."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _spec_discovery():
    """Execute only the module-discovery block of orange_cdss.spec."""
    text = (ROOT / "orange_cdss.spec").read_text(encoding="utf-8")
    a = text.index("APP_PACKAGES = [")
    b = text.index("if not any(d[0].endswith(\"commercial_names.txt\")")
    ns = {"os": os, "ROOT": str(ROOT)}
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        exec(text[a:b], ns)                                   # noqa: S102 - our own spec file
    finally:
        os.chdir(cwd)
    return ns


def test_spec_bundles_every_module_of_both_packages():
    ns = _spec_discovery()
    bundled = {pathlib.Path(src).as_posix() for src, _dest in ns["datas"]}
    on_disk = {p.relative_to(ROOT).as_posix() for pkg in ("cdss", "cdss_ui")
               for p in (ROOT / pkg).rglob("*.py") if "__pycache__" not in p.parts}
    assert on_disk <= bundled, f"not bundled: {sorted(on_disk - bundled)}"
    assert "streamlit_app.py" in bundled and "launcher.py" in bundled


def test_spec_declares_every_module_as_a_hidden_import():
    ns = _spec_discovery()
    names = set(ns["APP_MODULE_NAMES"])
    for must in ("cdss.pipeline", "cdss.therapy.engine", "cdss.therapy.therapy_rules",
                 "cdss.astqc.final_checklist", "cdss.therapy.rules.host", "cdss_ui.app"):
        assert must in names, must


def test_spec_has_no_hand_maintained_module_list():
    text = (ROOT / "orange_cdss.spec").read_text(encoding="utf-8")
    assert "APP_MODULES = [" not in text


def test_brand_names_file_ships_next_to_its_loader():
    assert (ROOT / "cdss" / "formulary" / "commercial_names.txt").exists()
    ns = _spec_discovery()
    assert ("cdss/formulary/commercial_names.txt", "cdss/formulary") in {
        (pathlib.Path(s).as_posix(), pathlib.Path(d).as_posix()) for s, d in ns["datas"]}
    from cdss.formulary.commercial_names import COMMERCIAL_NAMES
    assert len(COMMERCIAL_NAMES) > 50


def test_brand_names_load_from_any_working_directory(tmp_path, monkeypatch):
    import importlib
    monkeypatch.chdir(tmp_path)
    import cdss.formulary.commercial_names as cn
    assert len(importlib.reload(cn).COMMERCIAL_NAMES) > 50


def test_no_stray_python_at_the_repository_root():
    root_py = sorted(p.name for p in ROOT.glob("*.py"))
    assert root_py == ["launcher.py", "streamlit_app.py", "verify_upload.py"], root_py
