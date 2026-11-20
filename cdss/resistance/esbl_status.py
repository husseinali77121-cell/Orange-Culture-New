# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Suspected versus confirmed ESBL -- one label for every report (v7.4).

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

from typing import Any, Dict, Mapping, Optional

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


__all__ = ["esbl_status"]
