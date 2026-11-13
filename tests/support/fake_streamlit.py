# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""A recording fake of the Streamlit API surface the page uses.

Every call is appended to `R.trace`; widgets return scripted or seeded
pseudo-random values, with Streamlit's own widget-state rule (a keyed widget
returns st.session_state[key] when it exists).  The page can therefore be run
end to end in a test, with no browser and no Streamlit installed:

    st = fake_streamlit.install()        # becomes sys.modules["streamlit"]
    fake_streamlit.R.reset(seed=1, script={"some_widget_key": "value"})
    cdss_ui.app.main()                   # raises Stop / Rerun like the real thing
    fake_streamlit.R.trace               # [(call, args, kwargs, returned), ...]
"""
from __future__ import annotations

import hashlib
import random
import re
import sys
import types
from datetime import date, datetime


class Stop(BaseException):
    pass


class Rerun(BaseException):
    pass


class SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v

    def __delattr__(self, k):
        try:
            del self[k]
        except KeyError:
            raise AttributeError(k)


class Secrets(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


_TS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?"), "<TS>"),
    (re.compile(r"\d{8}[-_]\d{4,6}"), "<TS>"),
    (re.compile(r"\d{2}/\d{2}/\d{4}( \d{2}:\d{2})?"), "<TS>"),
]


def canon(x, depth=0):
    if isinstance(x, (bytes, bytearray)):
        return f"<bytes {len(x)} {hashlib.sha256(bytes(x)).hexdigest()[:16]}>"
    if isinstance(x, str):
        for rx, rep in _TS:
            x = rx.sub(rep, x)
        return x
    if isinstance(x, (int, float, bool)) or x is None:
        return x
    if isinstance(x, (date, datetime)):
        return f"<date {x.isoformat()[:10]}>"
    if isinstance(x, dict):
        return {str(k): canon(v, depth + 1) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [canon(v, depth + 1) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(str(canon(v, depth + 1)) for v in x)
    if callable(x):
        return f"<fn {getattr(x, '__name__', '?')}>"
    if isinstance(x, _Ctx):
        return f"<ctx {x._name}>"
    return f"<{type(x).__name__}>"


class Recorder:
    def __init__(self):
        self.trace = []
        self.rng = random.Random(0)
        self.script = {}        # key-or-label -> forced value
        self.explore = 0.0      # probability a widget takes a random (non-default) value
        self.click = 0.0        # probability a button reports "clicked"
        self.upload = None      # bytes returned by file_uploader

    def reset(self, seed, script=None, explore=0.0, click=0.0, upload=None):
        self.trace = []
        self.rng = random.Random(seed)
        self.script = dict(script or {})
        self.explore, self.click, self.upload = explore, click, upload

    def rec(self, name, args, kwargs, ret=None):
        self.trace.append((name, canon(list(args)), canon(kwargs), canon(ret)))


R = Recorder()
session_state = SessionState()
secrets = Secrets()


class _Ctx:
    """Container / column / tab / expander: a context manager that also exposes st.*"""
    def __init__(self, name):
        self._name = name

    def __enter__(self):
        R.rec(f"enter:{self._name}", (), {})
        return self

    def __exit__(self, et, ev, tb):
        R.rec(f"exit:{self._name}", (), {"exc": et.__name__ if et else None})
        return False

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return getattr(sys.modules["streamlit"], n)

    def empty(self):
        return _Ctx("empty")

    def progress(self, *a, **k):
        R.rec("ctx.progress", a, k)
        return self

    def update(self, *a, **k):
        R.rec("ctx.update", a, k)


class UploadedFile:
    def __init__(self, data, name="report.png"):
        self._d, self.name, self.type, self.size = data, name, "image/png", len(data)

    def getvalue(self):
        return self._d

    def read(self):
        return self._d


def _scripted(label, key):
    if key is not None and key in R.script:
        return True, R.script[key]
    if label in R.script:
        return True, R.script[label]
    return False, None


def _bind(key, default, chooser):
    """Streamlit widget-state semantics + scripted / exploratory user input."""
    if key is not None and key in session_state:
        val = session_state[key]
    else:
        val = default
    if R.explore and R.rng.random() < R.explore:
        val = chooser()
    if key is not None:
        session_state[key] = val
    return val


def _display(name):
    def f(*a, **k):
        R.rec(name, a, k)
        return _Ctx(name) if name in ("empty", "container", "expander", "spinner", "status",
                                      "popover", "form", "progress") else None
    f.__name__ = name
    return f


def checkbox(label, value=False, key=None, **k):
    forced, v = _scripted(label, key)
    if forced:
        if key is not None:
            session_state[key] = v
    else:
        v = _bind(key, value, lambda: R.rng.random() < 0.5)
    R.rec("checkbox", (label,), {"value": value, "key": key, **k}, v)
    return v


toggle = checkbox


def _opts(options):
    return list(options) if options is not None else []


def selectbox(label, options=(), index=0, key=None, format_func=None, **k):
    o = _opts(options)
    forced, v = _scripted(label, key)
    if forced and v in o:
        if key is not None:
            session_state[key] = v
    else:
        default = o[index] if (o and index is not None and 0 <= index < len(o)) else None
        v = _bind(key, default, lambda: R.rng.choice(o) if o else None)
        if o and v not in o:
            v = default
            if key is not None:
                session_state[key] = v
    R.rec("selectbox", (label,), {"options": o, "index": index, "key": key,
                                  "fmt": [format_func(x) for x in o] if format_func else None, **k}, v)
    return v


def radio(label, options=(), index=0, key=None, format_func=None, **k):
    o = _opts(options)
    forced, v = _scripted(label, key)
    if forced and v in o:
        if key is not None:
            session_state[key] = v
    else:
        default = o[index] if (o and index is not None and 0 <= index < len(o)) else None
        v = _bind(key, default, lambda: R.rng.choice(o) if o else None)
        if o and v not in o:
            v = default
    R.rec("radio", (label,), {"options": o, "index": index, "key": key, **k}, v)
    return v


def multiselect(label, options=(), default=None, key=None, format_func=None, **k):
    o = _opts(options)
    forced, v = _scripted(label, key)
    if forced:
        v = [x for x in v if x in o]
        if key is not None:
            session_state[key] = v
    else:
        d = [x for x in (default or []) if x in o]

        def choose():
            n = R.rng.choice([0, 1, 2, max(0, len(o) // 2)])
            return R.rng.sample(o, k=min(n, len(o)))
        v = _bind(key, d, choose)
        v = [x for x in (v or []) if x in o]
        if key is not None:
            session_state[key] = v
    R.rec("multiselect", (label,), {"options": o, "default": default, "key": key, **k}, v)
    return list(v)


def number_input(label, min_value=None, max_value=None, value=0, step=None, key=None, **k):
    forced, v = _scripted(label, key)
    if forced:
        if key is not None:
            session_state[key] = v
    else:
        def choose():
            lo = min_value if min_value is not None else 0
            hi = max_value if max_value is not None else (lo + 100)
            if isinstance(value, float) or isinstance(lo, float) or isinstance(hi, float):
                return round(R.rng.uniform(float(lo), float(hi)), 1)
            return R.rng.randint(int(lo), int(hi))
        v = _bind(key, value, choose)
    R.rec("number_input", (label,), {"min": min_value, "max": max_value, "value": value,
                                     "step": step, "key": key, **k}, v)
    return v


slider = number_input


def text_input(label, value="", key=None, **k):
    forced, v = _scripted(label, key)
    if forced:
        if key is not None:
            session_state[key] = v
    else:
        v = _bind(key, value or "", lambda: R.rng.choice(["", "Test", "10^4", "Dr. X", "25", "abc 12"]))
    R.rec("text_input", (label,), {"value": value, "key": key, **k}, v)
    return v


text_area = text_input


def date_input(label, value=None, key=None, **k):
    v = _bind(key, value if value is not None else date.today(), lambda: date(2026, 11, 1))
    R.rec("date_input", (label,), {"value": value, "key": key, **k}, v)
    return v


def button(label, key=None, **k):
    forced, v = _scripted(label, key)
    if not forced:
        v = bool(R.click and R.rng.random() < R.click)
    R.rec("button", (label,), {"key": key, **k}, v)
    return v


form_submit_button = button


def download_button(label, data=None, key=None, **k):
    R.rec("download_button", (label,), {"data": data, "key": key, **k}, False)
    return False


def file_uploader(label, **k):
    R.rec("file_uploader", (label,), k)
    return UploadedFile(R.upload) if R.upload is not None else None


def columns(spec, **k):
    n = spec if isinstance(spec, int) else len(spec)
    R.rec("columns", (spec,), k)
    return [_Ctx(f"col{i}") for i in range(n)]


def tabs(names, **k):
    R.rec("tabs", (list(names),), k)
    return [_Ctx(f"tab{i}") for i, _ in enumerate(names)]


def stop():
    R.rec("stop", (), {})
    raise Stop()


def rerun(*a, **k):
    R.rec("rerun", a, k)
    raise Rerun()


def _cache(f=None, **k):
    return f if f else (lambda g: g)


def install():
    m = types.ModuleType("streamlit")
    m.session_state = session_state
    m.secrets = secrets
    for n in ("markdown", "write", "error", "warning", "info", "success", "caption", "text",
              "header", "subheader", "title", "divider", "image", "toast", "metric",
              "dataframe", "table", "json", "code", "set_page_config", "progress",
              "expander", "container", "spinner", "status", "popover", "form", "empty",
              "html", "latex", "balloons", "snow"):
        setattr(m, n, _display(n))
    for n, f in dict(checkbox=checkbox, toggle=toggle, selectbox=selectbox, radio=radio,
                     multiselect=multiselect, number_input=number_input, slider=slider,
                     text_input=text_input, text_area=text_area, date_input=date_input,
                     button=button, form_submit_button=form_submit_button,
                     download_button=download_button, file_uploader=file_uploader,
                     columns=columns, tabs=tabs, stop=stop, rerun=rerun,
                     cache_data=_cache, cache_resource=_cache).items():
        setattr(m, n, f)
    m.sidebar = _Ctx("sidebar")
    m.fragment = m.dialog = lambda *a, **k: (lambda f: f)

    def _missing(name):
        raise AttributeError(f"fake streamlit has no attribute {name!r} — add it to tools/fake_st.py")
    m.__getattr__ = _missing
    comp = types.ModuleType("streamlit.components")
    comp.v1 = types.SimpleNamespace(html=_display("components.html"), iframe=_display("components.iframe"))
    sys.modules["streamlit"] = m
    sys.modules["streamlit.components"] = comp
    sys.modules["streamlit.components.v1"] = comp.v1
    return m
