# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""The structure itself is under test: layering, importability, the rule table."""
import ast
import importlib
import inspect
import json
import pathlib
import pkgutil
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = sorted((ROOT / "cdss").rglob("*.py"))
PAGE = sorted((ROOT / "cdss_ui").rglob("*.py"))


def _imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_engine_never_imports_streamlit_or_the_page():
    bad = [(str(p.relative_to(ROOT)), m) for p in ENGINE for m in _imports(p)
           if m.split(".")[0] in ("streamlit", "cdss_ui")]
    assert not bad, f"the clinical engine must stay UI-free: {bad}"


def _utf8_env():
    """The child writes UTF-8 and the parent reads UTF-8, on Windows too (whose
    default is cp1252: a few Arabic letters encode to bytes cp1252 cannot decode)."""
    import os
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def test_engine_imports_in_a_process_that_has_no_streamlit():
    code = ("import sys, importlib, pkgutil\n"
            "sys.modules['streamlit'] = None      # any import of it now raises ImportError\n"
            "import cdss\n"
            "names = [m.name for m in pkgutil.walk_packages(cdss.__path__, 'cdss.')]\n"
            "[importlib.import_module(n) for n in names]\n"
            "print('CDSS_MODULES=%d' % len(names))\n")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=_utf8_env())
    assert r.returncode == 0, r.stderr[-1500:]
    # Third-party libraries may print to stdout while importing (WeasyPrint does
    # when GTK is not installed yet -- the Windows build's test step): read only
    # our own line.
    counts = [ln for ln in r.stdout.splitlines() if ln.startswith("CDSS_MODULES=")]
    assert counts, r.stdout[-800:]
    assert int(counts[-1].split("=")[1]) > 40


def test_entry_point_is_only_an_entry_point():
    """Imports the page and runs it; the only other thing it may do is the
    partial-upload clean-up (tests/test_partial_upload.py)."""
    tree = ast.parse((ROOT / "streamlit_app.py").read_text(encoding="utf-8"))
    body = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert [type(n).__name__ for n in body] == ["Import", "Try", "Expr"]
    assert ast.unparse(body[1].body[0]) == "from cdss_ui.app import main"
    assert ast.unparse(body[-1]) == "main()"


def test_every_exported_name_exists():
    import cdss
    stale = []
    for m in pkgutil.walk_packages(cdss.__path__, "cdss."):
        mod = importlib.import_module(m.name)
        stale += [(m.name, n) for n in getattr(mod, "__all__", []) if not hasattr(mod, n)]
    assert not stale, f"__all__ names that do not exist: {stale}"


# Modules that were already separate files in the single-file era and were MOVED,
# not split. Tables are large by nature; the three marked "logic" still hold very
# long functions and are the next candidates for the treatment the therapy
# engine got (see ARCHITECTURE.md, "Not split yet").
LARGE_BY_DESIGN = {
    "abx_guidelines.py", "organism_profile.py", "clinical_data.py", "clinical_matrix.py",
    "guideline_registry.py", "specimen_organism_map.py",           # data tables
    "ast_qa_engine.py", "ast_reportability.py", "ast_panel_completeness.py",   # QC rule tables
    "ocr_parsing.py",
    # logic: split into section / per-specimen functions in v6.7, but the files
    # still hold the remaining renderers and the per-specimen tables
    "report_service.py", "pathogenicity.py",
}


def test_no_new_monolith():
    """Everything cut out of the old single file stays under a size budget."""
    over = [(str(p.relative_to(ROOT)), n) for p in ENGINE + PAGE
            if p.name not in LARGE_BY_DESIGN
            and (n := p.read_text(encoding="utf-8").count("\n")) > 650]
    assert not over, f"modules over the 650-line budget: {over}"


def test_the_split_renderers_and_pathogenicity_stay_split():
    """v6.7: the 1,000-line PDF function and the 890-line pathogenicity engine
    were split into one function per section / specimen. Keep them that way."""
    limits = {("cdss/reports/report_service.py", "generate_pdf_html_report"): 300,
              ("cdss/reports/report_service.py", "generate_decision_tree_image"): 420,
              ("cdss/reports/report_service.py", "generate_report"): 200,
              ("cdss/organisms/pathogenicity.py", "assess_pathogenicity"): 350}
    over = []
    for (path, name), limit in limits.items():
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if fn.end_lineno - fn.lineno > limit:
            over.append((name, fn.end_lineno - fn.lineno, limit))
    assert not over, over


def test_no_function_in_the_therapy_engine_is_long():
    over = []
    for p in sorted((ROOT / "cdss" / "therapy" / "rules").glob("*.py")) + [
            ROOT / "cdss" / "therapy" / "engine.py", ROOT / "cdss" / "therapy" / "outcome.py"]:
        for node in ast.parse(p.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and node.end_lineno - node.lineno > 175:
                over.append((p.name, node.name, node.end_lineno - node.lineno))
    assert not over, over


# ── the rule table ──────────────────────────────────────────────────────────
def test_rules_have_one_shape_and_a_docstring():
    from cdss.therapy.engine import RULES
    assert len(RULES) == len(set(RULES)) >= 39
    for rule in RULES:
        assert list(inspect.signature(rule).parameters) == ["cx", "dg", "out"], rule.__name__
        assert (rule.__doc__ or "").strip(), f"{rule.__name__} has no docstring"


def test_rule_order_keeps_its_three_guarantees():
    from cdss.therapy.engine import RULES
    names = [r.__name__ for r in RULES]
    # 1. the panel's own verdict (unreadable / R) is decided before anything else
    assert names[:2] == ["rule_unreadable", "rule_resistant"]
    # 2. host cautions run last, after every absolute contraindication
    assert names[-3:] == ["rule_hepatic", "rule_renal_adjustment", "rule_intermediate"]
    # 3. pregnancy is judged after the age bans and before the host cautions
    assert names.index("rule_child") < names.index("rule_pregnancy") < names.index("rule_hepatic")


def test_every_rule_function_is_registered():
    """A rule written but never added to RULES would silently never run."""
    from cdss.therapy import engine
    registered = {r.__name__ for r in engine.RULES}
    defined = set()
    for p in (ROOT / "cdss" / "therapy" / "rules").glob("*.py"):
        defined |= {n.name for n in ast.parse(p.read_text(encoding="utf-8")).body
                    if isinstance(n, ast.FunctionDef) and n.name.startswith("rule_")}
    assert defined == registered, f"unregistered: {defined - registered}; unknown: {registered - defined}"


def test_context_is_frozen():
    import dataclasses
    from support.cases import context, drug
    cx = context()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cx.is_preg = True
    with pytest.raises(dataclasses.FrozenInstanceError):
        drug("Ciprofloxacin").result = "S"


# ── the page ────────────────────────────────────────────────────────────────
def test_page_sections_take_only_the_page_object():
    for p in PAGE:
        for node in ast.parse(p.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith(("render_", "run_case", "prepare_", "load_report")):
                args = [a.arg for a in node.args.args]
                assert args in (["page"], []), f"{p.name}:{node.name}{args}"


def test_page_never_calls_the_per_drug_engine_directly():
    """The page goes through run_analysis(); analyze_antibiotics is the engine's business."""
    offenders = []
    for p in PAGE:
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "analyze_antibiotics"):
                offenders.append(f"{p.name}:{node.lineno}")
    assert not offenders, offenders


# ── bridges kept for the legacy suites ──────────────────────────────────────
def test_every_legacy_name_still_resolves():
    sys.path.insert(0, str(ROOT / "tests" / "legacy"))
    import legacy_support as L
    L.install_streamlit_stub()
    names = json.loads((ROOT / "tests" / "legacy" / "legacy_names.json").read_text(encoding="utf-8"))
    broken = []
    for name in names:
        try:
            L.resolve(name)
        except Exception as exc:                      # noqa: BLE001
            broken.append((name, repr(exc)))
    assert not broken, broken[:10]


# ── data tables agree with each other ───────────────────────────────────────
def test_startup_validator_is_clean():
    """Every organism profile names real formulary drugs, every specimen map names real
    organisms.  (This was an inline 40-line script in the CI workflow.)"""
    from support.ui_harness import st  # noqa: F401  (installs the fake streamlit)
    from cdss_ui.startup import get_startup_validation_issues
    issues = [i for i in get_startup_validation_issues() if "[SECURITY]" not in i]
    assert not issues, issues
