# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""Support for the legacy regression suites (tests/legacy/test_*.py).

Those suites were written against the old single-file app: they sliced
`streamlit_app.py` with `ast`, exec'd the pieces into a dict and called the
functions from there.  The app is now a package of small importable modules, so
the slicing is gone -- the suites get the same NAMES, resolved to the real
modules:

    from legacy_support import APP      # attribute access:  APP.run_analysis(...)
    NS = namespace()                    # plain dict:        NS["classify_mdr"](...)

`legacy_names.json` maps every global the old file exposed to "module:attr".
`tests/test_architecture.py` checks that every entry still resolves.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LEGACY_NAMES = json.loads((HERE / "legacy_names.json").read_text(encoding="utf-8"))


def install_streamlit_stub() -> types.ModuleType:
    """A do-nothing `streamlit`, only for suites that import the UI package."""
    if "streamlit" in sys.modules:
        return sys.modules["streamlit"]

    class _Ctx:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def __getattr__(self, n): return lambda *a, **k: _Ctx()
        def __iter__(self): return iter([_Ctx() for _ in range(6)])
        def __getitem__(self, i): return _Ctx()
        def __bool__(self): return False

    class _State(dict):
        def __getattr__(self, k):
            try: return self[k]
            except KeyError: raise AttributeError(k)
        def __setattr__(self, k, v): self[k] = v

    class _Stop(BaseException):
        pass

    m = types.ModuleType("streamlit")
    m.session_state, m.secrets, m._Stop = _State(), _State(), _Stop
    noop = lambda *a, **k: _Ctx()                                       # noqa: E731
    m.stop = lambda *a, **k: (_ for _ in ()).throw(_Stop())
    m.cache_data = m.cache_resource = lambda f=None, **k: (f if f else (lambda g: g))
    m.columns = lambda spec, **k: [_Ctx() for _ in range(spec if isinstance(spec, int) else len(spec))]
    m.tabs = lambda names, **k: [_Ctx() for _ in names]
    m.button = m.form_submit_button = m.download_button = lambda *a, **k: False
    m.checkbox = lambda *a, **k: k.get("value", False)
    m.selectbox = m.radio = lambda label=None, options=None, *a, **k: (
        list(options)[k.get("index", 0) or 0] if options else None)
    m.multiselect = lambda *a, **k: list(k.get("default") or [])
    m.text_input = m.text_area = lambda *a, **k: k.get("value", "") or ""
    m.number_input = m.slider = lambda *a, **k: k.get("value", 0) or 0
    m.file_uploader = lambda *a, **k: None
    m.__getattr__ = lambda n: noop
    sys.modules["streamlit"] = m
    return m


def resolve(name: str):
    target = LEGACY_NAMES[name]
    mod, _, attr = target.partition(":")
    if mod.startswith("cdss_ui"):
        install_streamlit_stub()
    module = importlib.import_module(mod)
    return getattr(module, attr) if attr else module


def namespace(include_ui: bool = False) -> dict:
    """Every legacy global as a plain dict (what the old exec-into-dict loaders built)."""
    ns = {}
    for name, target in LEGACY_NAMES.items():
        if target.startswith("cdss_ui") and not include_ui:
            continue
        try:
            ns[name] = resolve(name)
        except Exception:                                    # pragma: no cover
            raise
    return ns


class _App:
    """Module-like view of the legacy names.

    Setting an attribute writes through to EVERY loaded cdss module that binds
    that name -- the old file was one namespace, so a suite that flipped
    `A.SAFETY_GATE_AVAILABLE` expected every function to see it.
    """
    def __getattr__(self, name):
        if name in LEGACY_NAMES:
            return resolve(name)
        raise AttributeError(f"legacy name {name!r} is not mapped (tests/legacy/legacy_names.json)")

    def __setattr__(self, name, value):
        hit = False
        for mname, module in list(sys.modules.items()):
            if module is not None and mname.split(".")[0] in ("cdss", "cdss_ui") \
                    and name in getattr(module, "__dict__", {}):
                setattr(module, name, value)
                hit = True
        if not hit:
            raise AttributeError(f"{name!r} is not a global of any cdss module")

    def __dir__(self):
        return sorted(LEGACY_NAMES)


APP = _App()


def _string_interior(text: str) -> set:
    """1-based numbers of the lines that lie inside a multi-line string literal."""
    import io
    import tokenize
    skip, fstart = set(), None
    for t in tokenize.generate_tokens(io.StringIO(text).readline):
        if t.type == tokenize.STRING and t.end[0] > t.start[0]:
            skip.update(range(t.start[0] + 1, t.end[0] + 1))
        elif t.type == getattr(tokenize, "FSTRING_START", -1):
            fstart = t.start[0]
        elif t.type == getattr(tokenize, "FSTRING_END", -2) and fstart is not None:
            if t.end[0] > fstart:
                skip.update(range(fstart + 1, t.end[0] + 1))
            fstart = None
    return skip


def ui_page_source() -> str:
    """The page as ONE script, in execution order, without the `page.` prefix.

    The page is now main() calling ~20 section functions that share a `page`
    object.  The legacy static checks were written against one long script
    ("the Child-Pugh selector appears before the analysis call", "the renal
    widget is keyed by file hash").  This rebuilds that view mechanically:
    every `section(page)` call in main() is replaced by the section's body,
    recursively, and `page.x` is written `x` again.  It is valid Python.
    """
    import ast
    import re
    ui = ROOT / "cdss_ui"
    funcs = {}                                   # section name -> (source lines, FunctionDef)
    for path in sorted(ui.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and [a.arg for a in node.args.args] == ["page"]:
                funcs[node.name] = (lines, node)
    app_lines = (ui / "app.py").read_text(encoding="utf-8").split("\n")
    call_rx = re.compile(r"^(\s*)(\w+)\(page\)\s*$")

    def body_of(name: str, indent: str) -> list:
        lines, node = funcs[name]
        stmts = node.body[1:] if (isinstance(node.body[0], ast.Expr)
                                  and isinstance(getattr(node.body[0], "value", None), ast.Constant)
                                  and isinstance(node.body[0].value.value, str)) else node.body
        first = (node.body[0].end_lineno + 1) if stmts is not node.body else node.body[0].lineno
        block = lines[first - 1:node.end_lineno]
        skip = {i - 1 for i in _string_interior("if 1:\n" + "\n".join(block) + "\n")}
        out = []
        for i, ln in enumerate(block, 1):
            if i in skip or not ln.strip():
                out.append(ln)
            else:
                out.append(indent + ln[4:])
        return expand(out)

    def expand(lines: list) -> list:
        out = []
        for ln in lines:
            m = call_rx.match(ln)
            if m and m.group(2) in funcs:
                out.extend(body_of(m.group(2), m.group(1)))
            else:
                out.append(ln)
        return out

    flat = "\n".join(expand(app_lines))
    return re.sub(r"\bpage\.(?=[A-Za-z_])", "", flat)


def source_of(*modules: str) -> str:
    """Concatenated source text of package modules ('cdss.pipeline', ...).
    'cdss_ui.app' means the whole page as one script (see ui_page_source)."""
    out = []
    for m in modules:
        if m == "cdss_ui.app":
            out.append(ui_page_source())
            continue
        p = ROOT.joinpath(*m.split(".")).with_suffix(".py")
        out.append(p.read_text(encoding="utf-8"))
    return "\n".join(out)


def all_source(*packages: str) -> str:
    """Source of the engine plus the page as one script plus the remaining UI modules."""
    out = []
    for pkg in (packages or ("cdss", "cdss_ui")):
        if pkg == "cdss_ui":
            import ast
            out.append(ui_page_source())
            for p in sorted((ROOT / pkg).glob("*.py")):
                text = p.read_text(encoding="utf-8")
                is_section_module = any(
                    isinstance(n, ast.FunctionDef) and [a.arg for a in n.args.args] == ["page"]
                    for n in ast.parse(text).body)
                if p.name != "app.py" and not is_section_module:
                    out.append(text)
            continue
        for p in sorted((ROOT / pkg).rglob("*.py")):
            out.append(p.read_text(encoding="utf-8"))
    return "\n".join(out)


MODULE_MOVES = json.loads((HERE / "module_moves.json").read_text(encoding="utf-8"))


def module_path(old_name: str) -> str:
    """Path of a module the old layout kept at the repository root ('report_service' ...)."""
    old_name = old_name[:-3] if old_name.endswith(".py") else old_name
    return str(ROOT.joinpath(*MODULE_MOVES[old_name].split(".")).with_suffix(".py"))


# v6.7 (2026-11-14): generate_pdf_html_report() was split into report_service
# (the orchestration), pdf_parts (style, strings, helpers) and pdf_sections (one
# function per section). A check that reads "the PDF renderer's source" reads
# all three.
PDF_LAYER_MODULES = ("cdss.reports.report_service", "cdss.reports.pdf_parts",
                     "cdss.reports.pdf_sections", "cdss.reports.image_parts")


def pdf_layer_source() -> str:
    """Source of the whole PDF layer, concatenated."""
    return "\n".join(ROOT.joinpath(*m.split(".")).with_suffix(".py").read_text(encoding="utf-8")
                     for m in PDF_LAYER_MODULES)


def iter_trees(*packages: str):
    """(path, ast.Module) for every module under the given packages (default: engine + UI)."""
    import ast
    for pkg in (packages or ("cdss", "cdss_ui")):
        for p in sorted((ROOT / pkg).rglob("*.py")):
            yield p, ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def walk_all_nodes(*packages: str):
    """ast.walk over every module of the package (replaces walking the one old file)."""
    import ast
    for _p, tree in iter_trees(*packages):
        yield from ast.walk(tree)


def combined_tree(*packages: str):
    """One ast.Module holding the bodies of every module (for whole-program static checks)."""
    import ast
    body = []
    for _p, tree in iter_trees(*packages):
        body.extend(tree.body)
    return ast.Module(body=body, type_ignores=[])


def legacy_source(name: str) -> str:
    """Source text of a legacy function/class ('' for plain data)."""
    import inspect
    try:
        return inspect.getsource(resolve(name))
    except (TypeError, OSError, KeyError):
        return ""
