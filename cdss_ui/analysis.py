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
from cdss.therapy.therapy_rules import classify_uti
from cdss.therapy.therapy_rules import SYSTEMIC_UTI_NOTE_AR, SYSTEMIC_UTI_NOTE_EN
from cdss.organisms.pathogenicity import treatment_gate
from cdss_ui.state import current_patho_result, treat_override_key


def _resolve_uti(page):
    """(engine value, note for the reports) for the UTI syndrome -- v7.3.

    Third external review: a manual "cystitis" / "cUTI without fever" choice
    no longer silences fever, flank pain or rigors. When they disagree the page
    says so and treats the UTI as upper unless the physician confirms a
    non-urinary source -- and that confirmation is printed.
    """
    if classify_specimen(page.culture_type) != "urine":
        return classify_uti(page.uti_syndrome_choice, [], False).value, ""
    _sym = st.session_state.get("patho_symptoms") or []
    _dev = page.case.cuti_device
    uc = classify_uti(page.uti_syndrome_choice, _sym, catheter=_dev)
    if not uc.conflict:
        # v7.4 (external review of v7.3): upper from fever / rigors alone is a
        # systemic / upper-tract syndrome, not a proven pyelonephritis.
        return uc.value, (SYSTEMIC_UTI_NOTE_EN if (uc.value == "upper" and uc.basis == "systemic")
                          else "")
    _picked = "التهاب مثانة" if "مثانة" in str(page.uti_syndrome_choice) else "cUTI بلا حمى"
    st.warning(f"⚠️ اخترت «{_picked}» لكن الأعراض المُدخلة فيها حمى / ألم خاصرة / رعشة — "
               "البرنامج بيتعامل معها كعدوى بولية جهازية / علوية (أدوية المثانة ممنوعة) إلا لو "
               "أكّدت إن مصدرها غير بولي.")
    _ok = st.checkbox("أؤكد إكلينيكياً: الحمى / الأعراض من مصدر غير بولي — اعتمد اختياري "
                      "(يُطبع في التقرير)", key=f"uti_nonurinary_ok_{page._fh}")
    uc = classify_uti(page.uti_syndrome_choice, _sym, catheter=_dev, confirm_non_urinary=_ok)
    if uc.confirmed:
        return uc.value, (f"UTI: physician kept '{'cystitis' if uc.value == 'lower' else 'cUTI'}' "
                          "despite fever / flank pain / rigors (non-urinary source confirmed)")
    return uc.value, ("UTI: fever / flank pain / rigors entered - treated as a systemic / "
                      "upper-tract UTI syndrome (the manual cystitis / cUTI choice was not "
                      "confirmed); pyelonephritis is not proven by these signs alone")


_CONFIRM_REPORT = ("أؤكد إكلينيكياً أن طريقة الجمع المُدخلة هي الصحيحة رغم تقرير المعمل "
                   "(يُطبع في التقرير) — بدون التأكيد أو التصحيح التقارير موقوفة")
_CONFIRM_ENTRY = ("أؤكد إكلينيكياً إن العينة فعلاً midstream / تبول رغم تسجيل القسطرة (مثلاً القسطرة "
                  "اتشالت قبل أخذ العينة) — يُطبع في التقرير؛ بدون التأكيد أو التصحيح التقارير موقوفة")


def _check_case_consistency(page, patient):
    """(report collection method, confirmed issue codes) -- v7.4, v7.8.

    External case review 2026-11-20 (v7.4): the laboratory report said "Mid
    stream urine" and the case was analysed as a Foley specimen. v7.8 (owner:
    "protect the program against conflicts in the inputs themselves"): every
    contradiction in the inputs, and between the inputs and the report the
    OCR read, is checked the same way -- a CRITICAL alert, the reports blocked
    until the entry is corrected or, where it can be legitimate, THAT issue is
    confirmed (each its own checkbox; the confirmation is printed).
    """
    import hashlib
    from cdss.common.data_consistency import check_case_consistency, check_case_inputs
    _payload_pt = (getattr(page, "patient", None) or {})
    _payload_pt = _payload_pt if isinstance(_payload_pt, dict) else {}
    _report = _payload_pt.get("CollectionMethod")
    _issues = check_case_consistency(
        specimen=page.culture_type, report_collection=_report,
        entered_collection=page.case.collection_method,
        host_factors=page.case.host_factors)
    _issues += check_case_inputs(
        patient, specimen=page.culture_type, organism=page.organism_type,
        panel=getattr(page, "sir_map_raw", None) or page.sir_map,
        symptoms=_symptoms_now(page), report=_payload_pt)
    confirmed = set()
    for _i in _issues:
        if _i.get("confirmable", True):
            _how = _i['hint_ar']
        elif _i.get("kind") == "input":
            _how = _i['hint_ar'] + " — مفيش تأكيد يحل محل التصحيح."
        else:
            _how = "اختار طريقة الجمع في خانة الـ Pathogenicity — مفيش تأكيد يحل محلها."
        st.error(f"🛑 **CRITICAL — {_i['message_ar']}**  \n" + _how)
        if not _i.get("confirmable", True):
            continue
        if _i["code"] == "SPECIMEN_ENTRY_VOIDED_WITH_CATHETER":
            _label = _CONFIRM_ENTRY
        elif _i["code"].startswith("SPECIMEN_"):
            _label = _CONFIRM_REPORT
        else:
            _label = f"أؤكد إكلينيكياً صحة الإدخال رغم التعارض: {_i['message_ar']} (يُطبع في التقرير)"
        # keyed by the report file too: a confirmation never carries over to
        # the next patient (and reset_patient_state clears the prefix)
        _key = f"data_confirm_{page.file_hash[:8]}_" + hashlib.md5(
            f"{_i['code']}|{_i['report_value']}|{_i['entered_value']}|{_report}|"
            f"{page.case.collection_method}|{sorted(page.case.host_factors)}".encode()
        ).hexdigest()[:12]
        if st.checkbox(_label, key=_key):
            confirmed.add(_i["code"])
    return _report, confirmed


def _symptoms_now(page):
    from cdss.common.specimen import classify_specimen as _cs
    if _cs(page.culture_type) == "urine":
        return list(st.session_state.get("patho_symptoms") or [])
    return []


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
        weight_kg=getattr(page, "weight", None),
    )
    page._carb_type_now = normalize_carbapenemase_type(page.carbapenemase_choice)
    page._uti_syn_now, page.uti_note = _resolve_uti(page)
    st.session_state["carb_type_now"] = page._carb_type_now
    # page.aux_tests (D-test / penicillinase) ride in the panel; run_analysis()
    # hands them to the therapy rules and strips them for every other step.
    # The RAW panel (SDD kept): the therapy engine names the CLSI SDD regimen.
    # v7.2 (second external review 2026-11-19): a "do not treat" pathogenicity
    # verdict (asymptomatic bacteriuria, contaminant, colonisation, rejected
    # sputum) reaches the advice. Only a CURRENT result counts (not one left
    # over from other inputs); the physician's override is per verdict.
    # v7.3 (third review): the override belongs to THIS assessment -- its key
    # carries the input signature, so a new assessment asks again.
    _patho_now = current_patho_result()
    _g0 = treatment_gate(_patho_now)
    _override = bool(_g0 and st.session_state.get(treat_override_key()))
    _report_coll, _confirmed = _check_case_consistency(page, _patient)
    _report_fields = getattr(page, "patient", None)
    _res = run_analysis(_patient, page.organism_type, page.culture_type,
                        {**getattr(page, "sir_map_raw", page.sir_map), **page.aux_tests},
                        drugs=page.final_drugs, carbapenemase_type=page._carb_type_now,
                        uti_syndrome=page._uti_syn_now,
                        pathogenicity=_patho_now, treat_override=_override,
                        report_collection_method=_report_coll,
                        consistency_confirmed=_confirmed,
                        report_fields=_report_fields if isinstance(_report_fields, dict) else None,
                        symptoms=_symptoms_now(page))
    page.treatment_gate = _res.get("treatment_gate")
    page.data_issues = _res.get("data_issues") or []
    page.data_blocked = bool(_res.get("data_blocked"))
    # v7.5 (external review of v7.4): the validator must see whether the safety
    # layers ran -- V09 was never checked on the page.
    page.degraded = list(_res.get("degraded") or [])
    page.gate_applied = _res.get("gate_applied")
    if page._uti_syn_now == "upper" and classify_specimen(page.culture_type) == "urine":
        st.info("🫘 عدوى بولية جهازية / علوية (حمى، رعشة، ألم خاصرة) — Nitrofurantoin و "
                "Fosfomycin الفموي و Norfloxacin مُستبعدة (لا تصل لنسيج الكلى) — IDSA cUTI 2025. "
                + ("" if "خاصرة" in " ".join(st.session_state.get("patho_symptoms") or [])
                   or "Flank" in " ".join(st.session_state.get("patho_symptoms") or [])
                   else SYSTEMIC_UTI_NOTE_AR))
    elif page._uti_syn_now == "cuti" and classify_specimen(page.culture_type) == "urine":
        # v7.2 (second external review): a catheter / stone / stent alone is a
        # COMPLICATED UTI, not a pyelonephritis.
        st.info("🫘 cUTI (قسطرة / حصوة / دعامة / nephrostomy) بلا حمى ولا ألم خاصرة — ليست "
                "التهاب حويضة. أدوية المثانة فقط (Nitrofurantoin، Fosfomycin الفموي، Norfloxacin) "
                "في قائمة الحذر: IDSA cUTI 2025 يعتبرها «غير مناسبة عادةً» للـ cUTI.")
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
