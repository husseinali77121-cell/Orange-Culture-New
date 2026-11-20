# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""One release step for every physician-facing export (v7.6).

External review of v7.5: the release gate checked each document as it was
drawn, top to bottom -- so the text report's download button was already on the
page when the PDF check (V12) failed further down, and the PDF was checked
only when someone pressed "Generate PDF". "Any error blocks every export" was
not true.

Now `prepare_release(page)` runs BEFORE the final checklist and before any
export section. It builds the text report, the PDF HTML (for the options
currently selected) and the image lists, validates all of them together with
the analysis (validate_case V01-V13), and records one decision in
`page.release`. Every export section shows its download only when that one
decision is "released", and the PDF file is made from the exact HTML that was
validated. A build failure, a validation that did not run, or any error =
nothing is released (fail closed).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

import streamlit as st

from cdss.organisms.pathogenicity import gate_suppresses
from cdss.pipeline import duration_syndrome_key
from cdss.reports.report_service import generate_pdf_html_report, generate_report
from cdss.stewardship.combination import get_combination_therapy
from cdss.stewardship.duration import get_treatment_duration
from cdss.stewardship.hepatic import get_hepatic_recommendations
from cdss_ui.release_gate import validation_input
from cdss_ui.state import current_patho_result


def pdf_options() -> Dict[str, Any]:
    """The PDF options as the widgets will show them in this run.

    The widgets live further down the page; Streamlit has already written a
    changed widget's value into session_state before the script reruns, so
    reading the widget keys here gives the same values the widgets will show.
    """
    ss = st.session_state
    return {"lang": ss.get("pdf_lang_radio", ss.get("pdf_lang", "ar")),
            "combo": bool(ss.get("pdf_cb_combo", ss.get("pdf_include_combo", True))),
            "dur": bool(ss.get("pdf_cb_dur", ss.get("pdf_include_duration", True))),
            "patho": bool(ss.get("pdf_cb_patho", ss.get("pdf_include_patho", True))),
            "cp": ss.get("child_pugh_class", "A"),
            "sev": ss.get("severity_level", "moderate")}


def pdf_signature(page, opts: Dict[str, Any]) -> str:
    return (f"{page._rpt_input_hash}|{opts['lang']}|{opts['combo']}|{opts['dur']}"
            f"|{opts['patho']}|{opts['cp']}|{opts['sev']}")


def build_text(page) -> str:
    """The clinical text report (cached on the inputs that change it)."""
    page._lab  = st.session_state.get("lab_name", "Your Lab Name")
    page._city = st.session_state.get("lab_city", "")
    page._pt   = page.patient_name.strip() or "غير محدد"

    # Hash all inputs that affect the report.
    # patho_result is serialized IN FULL (not just its score): its verdict,
    # factors_pos/neg and recommendations depend on UI inputs (culture
    # purity, symptoms, urinalysis, gram stain, host factors) that are NOT
    # otherwise present in this hash — so a score-only key leaves the report
    # stale whenever those change while the numeric score stays the same.
    _patho_sig = json.dumps(
        [current_patho_result() or {}, getattr(page, "treatment_gate", None)],
        sort_keys=True, default=str, ensure_ascii=False,
    )
    # FIX 2026-11-11 (round 4): the buckets were hashed by their LENGTH.
    # Two different verdicts of equal size (a drug swapping between
    # caution and avoid after a Child-Pugh change, a novel agent's note
    # after a carbapenemase class was entered) kept the old report, and
    # current medications / interactions, allergies, Child-Pugh, the
    # carbapenemase class and the UTI syndrome were not hashed at all --
    # so adding warfarin left the interaction out of the report.
    def _bsig(items):
        return ";".join(
            f"{i.get('name')}:{i.get('warning_reason') or i.get('category') or ''}"
            f":{len(str(i.get('clinical_note') or i.get('preg_note') or ''))}"
            for i in (items or []))
    page._rpt_input_hash = hashlib.md5(
        f"{page._pt}|{page.age}|{page.age_months}|{page.sex}|{page.weight}|{page.cl_cr}|{page.is_renal}|{page.is_preg}|{page.is_hepatic}"
        f"|{page._child_pugh_now}|{sorted(page.current_meds or [])}|{sorted(page.allergies or [])}"
        f"|{page._carb_type_now}|{page._uti_syn_now}|{getattr(page, 'uti_note', '')}"
        f"|{page.organism_type}|{page.culture_type}|{page.colony_count}|{page.date_in}"
        f"|{page.pus_cells_text}|{page.rbcs_text}|{str(sorted(page.sir_map.items()))}"
        f"|{_bsig(page.allowed)}|{_bsig(page.warned)}|{_bsig(page.banned)}|{_bsig(page.preg_warn_items)}"
        f"|{sorted(page.interactions_alerts or [])}"
        f"|{page.show_commercial}|{page._lab}|{page._city}|{_patho_sig}"
        f"|{getattr(page, 'case', None)!r}|{getattr(page, 'data_issues', None)!r}"
        f"|{sorted((getattr(page, 'aux_tests', None) or {}).items())}".encode()
    ).hexdigest()[:16]

    if st.session_state.get("_rpt_hash") != page._rpt_input_hash:
        _new_report = generate_report(
            patient_name=page._pt,
            age=page.age, age_months=page.age_months, sex=page.sex, weight=page.weight,
            cl_cr=page.cl_cr, is_renal=page.is_renal,
            is_preg=page.is_preg, is_hepatic=page.is_hepatic,
            allowed=page.allowed, warned=page.warned, banned=page.banned,
            preg_warn_items=page.preg_warn_items,
            organism=page.organism_type, specimen=page.culture_type,
            interactions=page.interactions_alerts, sir_map=page.sir_map,
            colony_count=page.colony_count,
            date_in=str(page.date_in),
            pus_cells=page.pus_cells_text,
            rbcs=page.rbcs_text,
            lab_name=page._lab,
            lab_city=page._city,
            patho_assessment=current_patho_result(),
            show_commercial_names=page.show_commercial,
            case=getattr(page, "case", None),
            treatment_gate=getattr(page, "treatment_gate", None),
            uti_note=getattr(page, "uti_note", ""),
            data_issues=getattr(page, "data_issues", None),
            aux_tests=getattr(page, "aux_tests", None),
        )
        st.session_state._rpt_text = _new_report
        st.session_state._rpt_hash = page._rpt_input_hash
    return st.session_state.get("_rpt_text", "")


def build_pdf_html(page, opts: Dict[str, Any]) -> str:
    """The physician PDF as validated HTML (cached on its signature)."""
    sig = pdf_signature(page, opts)
    if st.session_state.get("_pdf_html_sig") == sig and st.session_state.get("_pdf_html"):
        return st.session_state["_pdf_html"]
    _dur_for_pdf = get_treatment_duration(
        specimen=page.culture_type, organism=page.organism_type,
        syndrome=duration_syndrome_key(page.syndrome_info, page._uti_syn_now, page.culture_type),
        age=page.age, sex=page.sex, is_renal=page.is_renal,
        phenotypes=page.phenotypes, severity=opts["sev"],
        is_cath=bool(getattr(getattr(page, "case", None), "is_cath", False)
                     and getattr(page.case, "is_urine", False)),
        primary=(getattr(page, "ranked", None) or [None])[0],
        is_preg=bool(page.is_preg),
    ) if (opts["dur"] and not gate_suppresses(getattr(page, "treatment_gate", None))) else None
    # organism= restored 2026-08-21 -- see the matching note on
    # the UI call site above. Same missing-organism defect, same
    # consequence (Colistin/Proteus-class intrinsic annotation
    # silently skipped), on the PDF a clinician downloads and keeps.
    _combo_for_pdf = get_combination_therapy(
        page.phenotypes,
        is_pregnant=page.is_preg, age_years=page.age, age_months=page.age_months,
        is_renal=page.is_renal, cl_cr=page.cl_cr, is_hepatic=page.is_hepatic,
        organism=page.organism_type,
        carbapenemase_type=st.session_state.get("carb_type_now"),
    ) if (opts["combo"] and not gate_suppresses(getattr(page, "treatment_gate", None))) else None
    _hep_for_pdf   = (get_hepatic_recommendations(page.allowed, opts["cp"])
                      if page.is_hepatic else None)
    html = generate_pdf_html_report(
        patient_name         = page._pt,
        age=page.age, sex=page.sex, weight=page.weight,
        cl_cr=page.cl_cr, is_renal=page.is_renal,
        is_preg=page.is_preg, is_hepatic=page.is_hepatic,
        allowed=page.allowed, warned=page.warned, banned=page.banned,
        preg_warn_items=page.preg_warn_items,
        organism=page.organism_type, specimen=page.culture_type,
        sir_map=page.sir_map,
        interactions=page.interactions_alerts,
        mdr_result=page.mdr_result,
        esbl_result=page.esbl_result,
        phenotypes=page.phenotypes,
        colony_count=page.colony_count,
        date_in=str(page.date_in),
        pus_cells=page.pus_cells_text,
        rbcs=page.rbcs_text,
        lab_name=page._lab,
        lab_city=page._city,
        patho_assessment=(current_patho_result()
                          if opts["patho"] else None),
        duration_data=_dur_for_pdf,
        combo_suggestions=_combo_for_pdf,
        show_commercial_names=page.show_commercial,
        child_pugh=opts["cp"],
        hepatic_recs=_hep_for_pdf,
        lang=opts["lang"],
        carbapenemase_type=getattr(page, "_carb_type_now", None),
        uti_syndrome=getattr(page, "_uti_syn_now", None),
        treatment_gate=getattr(page, "treatment_gate", None),
        data_issues=getattr(page, "data_issues", None),
        aux_tests=getattr(page, "aux_tests", None),
        case=getattr(page, "case", None),
        return_html=True,
    )
    if isinstance(html, bytes):
        html = html.decode("utf-8", "replace")
    st.session_state["_pdf_html"] = html or ""
    st.session_state["_pdf_html_sig"] = sig
    return html or ""


def prepare_release(page) -> None:
    """Build every export, validate them together, record one decision."""
    from cdss.validation.case_validator import release_decision, validate_case
    page.show_commercial = bool(st.session_state.get(
        "show_commercial_chk", st.session_state.get("show_commercial_names", False)))
    opts = pdf_options()
    try:
        # A critical data mismatch: nothing is built at all (no report text sits
        # in the session for a case whose specimen is in doubt).
        _hold = bool(getattr(page, "data_blocked", False))
        text = None if _hold else build_text(page)
        pdf_html = None if _hold else build_pdf_html(page, opts)
        violations = validate_case(
            validation_input(page), specimen=page.culture_type, sir_map=page.sir_map,
            uti_syndrome=getattr(page, "_uti_syn_now", None),
            report_text=text, pdf_html=pdf_html,
            image_lists={"preferred": getattr(page, "preferred_with_badge", []),
                         "caution": getattr(page, "use_caution_names", []),
                         "avoid": getattr(page, "banned_names", []),
                         "reserve": getattr(page, "reserve_names", [])})
    except Exception as exc:                                     # fail closed
        text, pdf_html = "", ""
        violations = [{"id": "V00", "severity": "error",
                       "message": f"A report could not be built ({type(exc).__name__}: {exc}) - "
                                  "nothing is released."}]
    page.validation = violations
    decision = release_decision(violations)
    page.release = {"text": text or "", "pdf_html": pdf_html or "", "opts": opts,
                    "pdf_sig": (pdf_signature(page, opts)
                                if getattr(page, "_rpt_input_hash", None) else ""),
                    "blocked": bool(getattr(page, "data_blocked", False)) or decision["blocked"],
                    "errors": decision["errors"]}


__all__ = ["prepare_release", "build_text", "build_pdf_html", "pdf_options", "pdf_signature"]
