# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Supplementary tests that travel in the panel but are not S / I / R.

A culture panel is `{drug: "S" | "I" | "R"}`.  Two bench tests are reported
alongside it with a Positive / Negative answer:

    D-test          inducible clindamycin resistance (erythromycin R, clindamycin S)
    Penicillinase   zone-edge / nitrocefin / blaZ, for penicillin-S staphylococci
    ESBL test       v7.4: phenotypic ESBL confirmation (CLSI combination disk / DDST)

`normalize_sir_map()` keeps S/I/R only, so these two were thrown away before
the rules that ask for them ever ran: a recorded "D-test: Negative" could not
release clindamycin, and a positive one was reported as "not confirmed".
read_aux_tests() takes them from the RAW panel, before normalisation.
"""
from typing import Any, Dict, Mapping, Optional

D_TEST_KEYS = ("D-test", "D test", "D-Test", "D Test", "Dtest", "D-zone test")
PENICILLINASE_KEYS = ("Penicillinase", "Beta-lactamase", "blaZ")
# v7.4 (external case review): the ESBL phenotypic confirmatory test (CLSI M100
# Table 3A combination disk -- ceftazidime / cefotaxime +/- clavulanate -- or a
# double-disk synergy test). Without it every ESBL call is a PREDICTION from the
# resistance pattern and is labelled "suspected", never "ESBL+".
ESBL_CONFIRM_KEYS = ("ESBL confirmation", "ESBL confirmatory test", "ESBL test", "DDST",
                     "Combination disk", "ESBL")

_POSITIVE = {"positive", "pos", "+", "+ve", "موجب", "إيجابي", "ايجابي"}
_NEGATIVE = {"negative", "neg", "-", "-ve", "سالب", "سلبي"}


def normalize_aux_result(value: Any) -> str:
    """'POSITIVE' | 'NEGATIVE' | '' (not done / unreadable). Never guesses."""
    v = str(value or "").strip().lower()
    if v in _POSITIVE:
        return "POSITIVE"
    if v in _NEGATIVE:
        return "NEGATIVE"
    return ""


def _first(panel: Optional[Mapping[str, Any]], keys) -> str:
    if not panel:
        return ""
    by_key = {str(k or "").strip().lower(): v for k, v in panel.items()}
    for key in keys:
        res = normalize_aux_result(by_key.get(key.lower()))
        if res:
            return res
    return ""


def read_aux_tests(raw_panel: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """{'d_test': ..., 'penicillinase': ...} from the panel as entered (before normalisation)."""
    return {
        "d_test": _first(raw_panel, D_TEST_KEYS),
        "penicillinase": _first(raw_panel, PENICILLINASE_KEYS),
        "esbl_confirm": _first(raw_panel, ESBL_CONFIRM_KEYS),
    }


def is_aux_key(key: Any) -> bool:
    k = str(key or "").strip().lower()
    return k in {x.lower() for x in D_TEST_KEYS + PENICILLINASE_KEYS + ESBL_CONFIRM_KEYS}
