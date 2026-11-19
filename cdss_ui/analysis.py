# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Runs the clinical pipeline for the current inputs.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.common.case_context import build_case_context
from cdss.common.clinical_utils import Patient
from cdss.common.patient_checks import validate_patient_context
from cdss.common.specimen import classify_specimen
from cdss.health import SAFETY_GATE_AVAILABLE
from cdss.pipeline import run_analysis
from cdss.resistance.mdr import classify_mdr
from cdss.resistance.mechanism import predict_esbl
from cdss.therapy.therapy_rules import normalize_carbapenemase_type
from cdss.therapy.therapy_rules import resolve_uti_syndrome


def run_case_analysis(page):
    """Build the Patient, run the clinical pipeline, show the safety-gate report."""
    # ── تحليل المضادات ────────────────────────────────────────────────────
    # النقطة ٤: analyze_antibiotics يُستدعى مباشرة بقيم اللحظة
    # فأي تغيير في أي widget يُعيد تشغيل Streamlit -> تحديث فوري
    # The grade now comes from the sidebar widget, which runs BEFORE this
    # point, so it reflects what the clinician actually selected on this run.
    # The default is "C" in both places: an ungraded liver must not be read as
    # the mildest one.
    page._child_pugh_now = st.session_state.get("child_pugh_class", "C") if page.is_hepatic else "A"

    for _pp in validate_patient_context(page.age, page.sex, page.is_preg, page.cl_cr, page.age_months):
        st.warning(_pp)
    # ONE call instead of two inlined ones. run_analysis() is this same
    # pipeline exposed as a pure function, so a test can walk exactly the
    # path the clinician walks — see its docstring for why that matters.
    # v7.0: ONE record of the case facts (review 2026-11-19: the pathogenicity
    # panel said Foley + quadriplegia while the image said Mid-Stream and the
    # syndrome card assumed no catheter). Every later section reads page.case.
    _is_urine_now = classify_specimen(page.culture_type) == "urine"
    page.case = build_case_context(
        page.culture_type,
        list(st.session_state.get("patho_host_factors" if _is_urine_now else "np_host_sel")
             or []),
        st.session_state.get("patho_collection", "") if _is_urine_now else "",
    )
    _patient = Patient(
        age_years=page.age, age_months=page.age_months, sex=page.sex,
        is_pregnant=page.is_preg, is_renal=page.is_renal, cl_cr=page.cl_cr,
        is_hepatic=page.is_hepatic, child_pugh=page._child_pugh_now,
        current_meds=list(page.current_meds or []),
        allergies=list(page.allergies or []),
        host_factors=list(page.case.host_factors),
        collection_method=page.case.collection_method,
    )
    page._carb_type_now = normalize_carbapenemase_type(page.carbapenemase_choice)
    page._uti_syn_now = resolve_uti_syndrome(page.uti_syndrome_choice,
                                        st.session_state.get("patho_symptoms") or [])
    st.session_state["carb_type_now"] = page._carb_type_now
    # page.aux_tests (D-test / penicillinase) ride in the panel; run_analysis()
    # hands them to the therapy rules and strips them for every other step.
    # The RAW panel (SDD kept): the therapy engine names the CLSI SDD regimen.
    _res = run_analysis(_patient, page.organism_type, page.culture_type,
                        {**getattr(page, "sir_map_raw", page.sir_map), **page.aux_tests},
                        drugs=page.final_drugs, carbapenemase_type=page._carb_type_now,
                        uti_syndrome=page._uti_syn_now)
    if page._uti_syn_now == "upper" and classify_specimen(page.culture_type) == "urine":
        st.info("🫘 التهاب حويضة / cUTI — Nitrofurantoin و Fosfomycin الفموي و Norfloxacin "
                "مُستبعدة (لا تصل لنسيج الكلى).")
    page.allowed              = _res["allowed"]
    page.warned               = _res["warned"]
    page.banned               = _res["banned"]
    page.preg_warn_items      = _res["preg_warn"]
    page.interactions_alerts  = _res["interactions"]
    for _pw in _res["patient_warnings"]:
        st.warning(_pw)

    # ══════════════════════════════════════════════════════════════════════
    # TERMINAL SAFETY GATE — second, independent opinion before display
    # ----------------------------------------------------------------------
    # clinical_matrix.py + safety_gate.py were written, tested (33 proofs)
    # and then never imported by this file, so the whole layer was inert.
    # It supplies what analyze_antibiotics structurally cannot: the
    # pharmacokinetic compartment. Without it this app was placing
    # Cefazolin, Cephalexin, Clindamycin, Azithromycin and Ertapenem in the
    # RECOMMENDED bucket for a CSF isolate — none of them reliably cross the
    # blood-brain barrier at meningeal doses.
    #
    # The gate is DEMOTE-ONLY (allowed -> caution -> avoid, never the
    # reverse), which is what makes it safe to run in front of a live
    # engine: the worst a bug in it can do is make the advice stricter.
    # ══════════════════════════════════════════════════════════════════════
    if SAFETY_GATE_AVAILABLE:
        _gate_report = _res["gate_report"]
        _moves = _gate_report.get("moves") or []
        if _moves:
            with st.expander(
                f"🛡️ Safety gate — {len(_moves)} agent(s) reclassified",
                expanded=any(m.get("to") == "banned" for m in _moves),
            ):
                st.caption(
                    "طبقة أمان مستقلة راجعت المخرجات (نفاذية الموقع، الحمل، الكبد، "
                    "الكلى، العمر). لا يمكنها ترقية أي دواء — فقط تشديد التصنيف."
                )
                for _m in _moves:
                    st.write(
                        f"- **{_m.get('drug')}**: `{_m.get('from')}` → "
                        f"`{_m.get('to')}` — "
                        # `why` is what safety_gate has always emitted;
                        # reason_ar/_en were added 2026-08-01. Neither of
                        # the two keys this line used to read existed, so
                        # 33/33 moves rendered with a blank reason.
                        f"{_m.get('reason_ar') or _m.get('why') or _m.get('reason_en') or ''}"
                    )
        if not _gate_report.get("specimen_recognised", True):
            st.warning(
                f"⚠️ الطبقة الآمنة لم تتعرف على نوع العينة «{page.culture_type}» — "
                "تم تطبيق سياسة fail-closed. راجع التوصيات يدوياً."
            )

    if page.interactions_alerts:
        st.warning("⚡ Interactions / Hepatic Warnings")
        for alert in page.interactions_alerts:
            st.write(alert)

    # ── MDR / XDR / PDR Classification ───────────────────────────────────
    page.mdr_result  = classify_mdr(page.organism_type, page.sir_map)
    page.esbl_result = predict_esbl(page.organism_type, page.sir_map)
