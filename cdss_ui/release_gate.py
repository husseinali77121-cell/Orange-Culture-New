# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Release gate for the physician-facing exports (v7.4 / v7.5).

External review of v7.4: the final checklist showed a whole-case validation
error in red, and the text report, the PDF and the summary image could still be
downloaded -- only the laboratory-report mismatch blocked them. Every export now
asks this module first:

  * a CRITICAL laboratory-report / case mismatch blocks (v7.4);
  * any whole-case validation ERROR blocks (v7.5);
  * a validation that did not run blocks (fail closed);
  * v7.6: every document is built and validated together, BEFORE the first
    download button (cdss_ui/release.py) -- one decision for all of them.
"""
from __future__ import annotations

import streamlit as st


def reports_blocked(page, what: str) -> bool:
    """True = do not offer this export. Reads the ONE decision prepare_release() made.

    v7.4: a CRITICAL lab-report / case mismatch blocks. v7.5: so does any
    whole-case validation error. v7.6 (external review of v7.5): the decision is
    made once, for every document together, before the first download button --
    a PDF error can no longer leave the text report downloadable above it. No
    decision on the page (prepare_release did not run) = blocked (fail closed).
    """
    rel = getattr(page, "release", None)
    if getattr(page, "data_blocked", False):
        st.error(f"🛑 {what} موقوف: بيانات العينة في البرنامج مختلفة عن تقرير المعمل "
                 "(راجع التنبيه الأحمر فوق) — صحّح الإدخال أو أكّده.")
        return True
    if not rel:
        st.error(f"🛑 {what} موقوف — فحص الإصدار ما اشتغلش، فمفيش تقرير بيطلع.")
        return True
    if rel.get("blocked"):
        st.error(f"🛑 {what} موقوف — فحص الحالة كاملة فيه أخطاء لازم تتصلح قبل إصدار أي تقرير:  \n"
                 + "  \n".join(f"• {v['id']}: {v['message']}" for v in rel.get("errors") or []))
        return True
    return False


def validation_input(page) -> dict:
    """What the page knows about the finished case, for validate_case()."""
    return {"ranked": getattr(page, "ranked", []) or [], "allowed": page.allowed,
            "warned": page.warned, "banned": page.banned, "preg_warn": page.preg_warn_items,
            "mechanism": getattr(page, "esbl_result", None) or {},
            "treatment_gate": getattr(page, "treatment_gate", None),
            "case": getattr(page, "case", None), "data_blocked": getattr(page, "data_blocked", False),
            "degraded": getattr(page, "degraded", None) or [],
            "gate_applied": getattr(page, "gate_applied", None),
            # v7.6: V12 checks the printed mechanism against its evidence level
            "aux_tests": getattr(page, "aux_tests", None) or {},
            "carbapenemase_type": getattr(page, "_carb_type_now", None),
            # v7.7: V14 -- a laboratory SDD left on a pair CLSI defines none for
            "sdd_reported": getattr(page, "sdd_drugs", None) or [],
            "organism": getattr(page, "organism_type", "") or ""}
