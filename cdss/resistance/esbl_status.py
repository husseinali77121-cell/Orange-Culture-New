# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Suspected versus confirmed ESBL -- one label for every report (v7.4) --
and, since v7.9, the one MDR / XDR statement every report prints.

DEFECT THIS CLOSES (external case review, 2026-11-20)
The physician PDF header printed three pills, "MDR | ESBL | ESBL+", for an
E. coli whose only ESBL evidence was the resistance pattern (ceftriaxone /
cefotaxime R). The "ESBL" pill came from the phenotype list and "ESBL+" from
the mechanism predictor -- the same prediction twice, the second worded as a
laboratory result. The AST-QA sheet itself said the pattern is "often seen
with ESBL production", i.e. not confirmed.

Three states, from the evidence actually available:
  confirmed      the phenotypic confirmatory test (CLSI M100 Table 3A combination
                 disk / DDST) was entered as Positive
  test_negative  the pattern suggests ESBL but the confirmatory test was Negative
                 (another mechanism, e.g. AmpC, is more likely)
  suspected      the pattern only -- labelled "Suspected ESBL (phenotype)"
The AST is never edited by any of them (CLSI M100: report as tested).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from cdss.common.aux_tests import read_aux_tests

_LABELS = {
    "confirmed": ("ESBL CONFIRMED", "ESBL confirmed (phenotypic confirmatory test positive)",
                  "ESBL مؤكد (اختبار التأكيد الظاهري موجب)"),
    "suspected": ("SUSPECTED ESBL", "Suspected ESBL (pattern only, not confirmed)",
                  "اشتباه ESBL من نمط المقاومة فقط — غير مؤكد"),
    "test_negative": ("ESBL TEST NEG.", "ESBL pattern but the confirmatory test was NEGATIVE - consider "
                      "AmpC or another mechanism",
                      "نمط ESBL لكن اختبار التأكيد سالب — فكّر في AmpC أو آلية أخرى"),
}


def esbl_status(esbl_result: Optional[Dict[str, Any]],
                raw_panel: Optional[Mapping[str, Any]] = None) -> Optional[Dict[str, str]]:
    """{state, pill, label_en, label_ar} or None when ESBL is not in question."""
    prob = str((esbl_result or {}).get("probability") or "").lower()
    test = read_aux_tests(raw_panel).get("esbl_confirm", "")
    if test == "POSITIVE":
        state = "confirmed"
    elif prob in ("high", "moderate"):
        state = "test_negative" if test == "NEGATIVE" else "suspected"
    else:
        return None
    pill, en, ar = _LABELS[state]
    return {"state": state, "pill": pill, "label_en": en, "label_ar": ar}


# ── v7.9 (external case review, 2026-11-21) ─────────────────────────────────
# The physician advisory printed "MDR -- NS in 8 of 10" and the AST-QA sheet
# printed "XDR -- NS in 8 of 10" for the SAME isolate: the QA heading used the
# raw level and dropped the "possible" qualifier that classify_mdr() had already
# set (4 Magiorakos categories untested). Both reports now state the
# ESTABLISHED level the same way, and say once, in the same words, that XDR is
# a possibility that cannot be confirmed on this panel.
def mdr_xdr_note(mdr_result: Dict[str, Any], *, list_categories: bool = False) -> str:
    """'' unless XDR/PDR is provisional; then why it is not confirmed (same text everywhere)."""
    m = mdr_result or {}
    if not (m.get("provisional") and m.get("level") in ("XDR", "PDR")):
        return ""
    unt = list(m.get("untested_categories") or [])
    n = len(unt)
    txt = (f"{m['level']} pattern in the tested categories, NOT confirmed: "
           f"{n} Magiorakos categor{'y' if n == 1 else 'ies'} not tested")
    if list_categories and unt:
        txt += f" ({', '.join(unt)})"
    return txt


def mdr_heading(mdr_result: Dict[str, Any], *, with_note: bool = False) -> str:
    """'MDR — non-susceptible in 8 of 10 tested categories' (the ESTABLISHED level).

    A provisional XDR/PDR prints its established level (MDR); `with_note` adds
    the mdr_xdr_note() sentence.
    """
    from cdss.resistance.mdr import physician_mdr_level
    m = mdr_result or {}
    lvl = physician_mdr_level(m) or m.get("level") or "not MDR"
    head = (f"{lvl} — non-susceptible in {m.get('resistant_count', 0)} of "
            f"{m.get('total_tested', 0)} tested categories")
    note = mdr_xdr_note(m) if with_note else ""
    return f"{head} · {note}" if note else head


def unverified_results(organism: str, sir_map: Dict[str, Any], sdd=()) -> List[str]:
    """Agents whose printed category cannot be used as reported (v7.9).

    Today: an I on a CLSI pair that has no I category (cefepime /
    piperacillin-tazobactam in Enterobacterales, ...): the true result is SDD or
    R and is not known until the MIC is read.
    """
    from cdss.astqc.phenotype_plausibility import no_i_pair
    _sdd = set(sdd or ())
    return [d for d, v in (sir_map or {}).items()
            if str(v or "").strip().upper() == "I" and d not in _sdd and no_i_pair(d, organism)]


def mdr_without_unverified(organism: str, sir_map: Dict[str, Any], mdr_result: Dict[str, Any],
                           unverified) -> Dict[str, Any]:
    """Does the level stand without the unverified results? (v7.9)

    {"unverified": [...], "level_without": str|None, "changed": bool,
     "categories_resting_on_unverified": [...]}. The classification itself is
    not altered: Magiorakos counts I as non-susceptible and a re-read can only
    move the agent to SDD (still non-susceptible at the standard dose) or R.
    What is reported is whether any category verdict depends on it.
    """
    unv = [d for d in (unverified or []) if d in (sir_map or {})]
    out = {"unverified": unv, "level_without": (mdr_result or {}).get("level"),
           "changed": False, "categories_resting_on_unverified": []}
    if not unv:
        return out
    from cdss.resistance.mdr import MDR_CATEGORIES, classify_mdr
    rest = {d: v for d, v in (sir_map or {}).items() if d not in unv}
    base = classify_mdr(organism, rest)
    out["level_without"] = base.get("level")
    out["changed"] = (base.get("level") != (mdr_result or {}).get("level")
                      or bool(base.get("provisional")) != bool((mdr_result or {}).get("provisional")))
    sir = {k: str(v or "").strip().upper() for k, v in (sir_map or {}).items()}
    for cat in (mdr_result or {}).get("resistant_categories") or []:
        ns = [d for d in MDR_CATEGORIES.get(cat, []) if sir.get(d) in ("I", "R")]
        if ns and all(d in unv for d in ns):
            out["categories_resting_on_unverified"].append(cat)
    return out


__all__ = ["esbl_status", "mdr_xdr_note", "mdr_heading", "unverified_results",
           "mdr_without_unverified"]
