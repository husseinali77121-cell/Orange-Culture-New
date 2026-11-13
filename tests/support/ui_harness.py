# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""Run the real page under the recording fake Streamlit."""
import copy
import os
import tempfile
import time

from support import fake_streamlit

st = fake_streamlit.install()
fake_streamlit.secrets.update({"subscribers": '{"lab@example.com": "2099-12-31"}'})
os.environ.setdefault("ORANGE_AUTH_STORE", os.path.join(tempfile.gettempdir(), "cdss_test_auth.json"))

import cdss_ui.app as app                                   # noqa: E402  (after the fake is installed)
from cdss.common.util import make_file_hash                  # noqa: E402

UPLOAD = b"not-a-real-image: the OCR payload is preset, so this is never decoded"
FILE_HASH = make_file_hash(UPLOAD)


def payload(organism, specimen, sir, age=34, months=None, sex="Female"):
    return {"patient": {"Name": None, "Age": age, "AgeMonths": months, "AgeAmbiguous": False,
                        "Sex": sex, "Specimen": specimen, "Organism": organism},
            "drugs": list(sir), "sir_map": dict(sir),
            "raw_text": "\n".join(f"{d} {v}" for d, v in sir.items()),
            "pus_cells": "", "rbcs": "", "condition": ""}


def run_page(pl=None, *, runs=1, script=None, seed=1, explore=0.0, click=0.0, authenticated=True):
    """Run main() `runs` times in one session. Returns (traces, session_state, errors)."""
    fake_streamlit.session_state.clear()
    if authenticated:
        fake_streamlit.session_state.update(
            {"authenticated": True, "email": "lab@example.com", "last_activity": time.time(),
             "days_left": 400})
    if pl is not None:
        fake_streamlit.session_state.update(
            {"ocr_data": copy.deepcopy(pl), "last_file_hash": FILE_HASH,
             "sir_map_edited": dict(pl["sir_map"])})
    traces, errors = [], []
    for r in range(runs):
        s = {"تسجيل خروج": False, **(script or {})}
        fake_streamlit.R.reset(seed * 1000 + r, script=s, explore=explore, click=click,
                               upload=UPLOAD if pl is not None else None)
        try:
            app.main()
        except (fake_streamlit.Stop, fake_streamlit.Rerun):
            pass
        except Exception as exc:                                 # noqa: BLE001
            errors.append(f"run {r}: {type(exc).__name__}: {exc}")
        traces.append(list(fake_streamlit.R.trace))
    return traces, dict(fake_streamlit.session_state), errors


def calls(trace, name):
    return [c for c in trace if c[0] == name]


def rendered_text(trace):
    """Every string the page handed to Streamlit in this run."""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    for c in trace:
        walk(c[1])
        walk(c[2])
    return "\n".join(out)
