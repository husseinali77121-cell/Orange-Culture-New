"""Minimal fake `streamlit` so the ORIGINAL monolith can be imported headless."""
import sys, types


class _Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, n): return lambda *a, **k: _Ctx()
    def __iter__(self): return iter([_Ctx() for _ in range(6)])
    def __getitem__(self, i): return _Ctx()
    def __bool__(self): return False


class Stop(Exception):
    pass


class _S(dict):
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self, k, v): self[k] = v


def install():
    m = types.ModuleType("streamlit")
    m.session_state = _S()
    m.secrets = _S()
    def _noop(*a, **k): return _Ctx()
    m.expander = m.container = m.form = m.spinner = m.empty = m.status = m.popover = _noop
    m.sidebar = _Ctx()
    m.stop = lambda *a, **k: (_ for _ in ()).throw(Stop())
    m.cache_data = m.cache_resource = lambda f=None, **k: (f if f else (lambda g: g))
    m.columns = lambda spec, **k: [_Ctx() for _ in range(spec if isinstance(spec, int) else len(spec))]
    m.tabs = lambda names, **k: [_Ctx() for _ in names]
    m.button = m.form_submit_button = lambda *a, **k: False
    m.checkbox = lambda *a, **k: k.get("value", False)
    m.selectbox = m.radio = lambda label=None, options=None, *a, **k: (
        list(options)[k.get("index", 0) or 0] if options else None)
    m.multiselect = lambda *a, **k: list(k.get("default") or [])
    m.text_input = m.text_area = lambda *a, **k: k.get("value", "") or ""
    m.number_input = m.slider = lambda *a, **k: k.get("value", 0) or 0
    m.dialog = m.fragment = lambda *a, **k: (lambda f: f)
    m.file_uploader = lambda *a, **k: None
    m.__getattr__ = lambda n: _noop
    comp = types.ModuleType("streamlit.components")
    comp.v1 = types.SimpleNamespace(html=_noop, iframe=_noop)
    sys.modules["streamlit"] = m
    sys.modules["streamlit.components"] = comp
    sys.modules["streamlit.components.v1"] = comp.v1
    return m
