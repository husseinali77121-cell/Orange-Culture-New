# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Left column: everything the user types about the patient and the culture.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.common.catalog import BACTERIA_TYPES
from cdss.common.catalog import SPECIMEN_TYPES
from cdss.common.renal import ASSUMED_CRCL_UNKNOWN
from cdss.common.renal import calc_creatinine_clearance
from cdss.common.renal import calc_paediatric_egfr
from cdss.common.renal import get_renal_severity
from cdss.common.util import best_default_index
from cdss.common.util import safe_int
from cdss.formulary.co_medications import COMMON_MEDS
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.organisms.specimen_organism_map import get_organisms_for_specimen
from cdss.therapy.panel_filters import _drop_intrinsic
from cdss.therapy.panel_filters import _hide_urine_only
from cdss.therapy.therapy_rules import CARBAPENEMASE_TYPE_OPTIONS
from cdss.therapy.therapy_rules import UTI_SYNDROME_OPTIONS


def render_specimen_and_organism(page):
    """Patient name, specimen and organism pickers."""
    st.subheader("👤 Patient & Culture")

    # اسم المريض -- إدخال يدوي فقط
    page.patient_name = st.text_input(
        "👤 اسم المريض / Patient Name",
        value=st.session_state.get("patient_name_final", ""),
        placeholder="أدخل اسم المريض",
        help="يظهر في التقرير وصورة الملخص.",
        key=f"pname_{page.file_hash[:8]}"
    )
    st.session_state.patient_name_final = page.patient_name.strip()

    # Round 5 (2026-11-12): specimen, organism, age, months, sex and weight
    # had NO key, so Streamlit identified them by their parameters. When
    # the next report's OCR produced the same default (e.g. age unread ->
    # 25 both times, or the same organism), the widget was "the same
    # widget" and kept the PREVIOUS patient's manually entered value --
    # a child analysed at the last adult's age. Keyed per file like the
    # round-4 widgets, so a new report always starts from its own OCR.
    page._fh = page.file_hash[:8]
    page.culture_type = st.selectbox(
        "🧫 Specimen",
        SPECIMEN_TYPES,
        index=best_default_index(SPECIMEN_TYPES, page.patient.get("Specimen")),
        key=f"specimen_sel_{page._fh}",
    )

    filtered_organisms = [
        org for org in get_organisms_for_specimen(page.culture_type)
        if org in ORGANISM_PROFILE
    ]
    if not filtered_organisms:
        filtered_organisms = BACTERIA_TYPES

    page.organism_type = st.selectbox(
        "🦠 Organism",
        filtered_organisms,
        index=best_default_index(filtered_organisms, page.patient.get("Organism")),
        help=f"بكتيريا شائعة في عينة {page.culture_type}",
        key=f"organism_sel_{page._fh}_{page.culture_type}",
    )

    # ── Atypical organisms: NOT recovered on routine culture, NO disc AST ──
    # Legionella / Mycoplasma / Rickettsia are diagnosed by PCR / serology /
    # urine antigen — any S/I/R entered for them is not meaningful. Surface
    # empiric therapy from the profile and tell the user to ignore the AST panel.
    _ATYPICAL_NO_AST = {"Legionella pneumophila", "Mycoplasma spp."}
    if page.organism_type in _ATYPICAL_NO_AST:
        _emp = _drop_intrinsic(
            (ORGANISM_PROFILE.get(page.organism_type) or {}).get("first_line", []),
            page.organism_type)
        _emp_txt = "، ".join(_emp) if _emp else "—"
        st.warning(
            f"⚠️ **{page.organism_type}** لا يُزرع بالمزرعة الروتينية ولا يوجد له اختبار "
            f"حساسية (AST) بالأقراص — يُشخَّص بـ PCR / Serology / Urine Antigen.\n\n"
            f"**العلاج تجريبي (Empiric):** {_emp_txt}.\n\n"
            f"تجاهل أي نتائج S/I/R بالأسفل — غير ذات دلالة لهذا الكائن."
        )


def render_microscopy(page):
    """Colony count, pus cells, RBCs, culture condition; organism profile note."""
    # ── حقول المزرعة والمجهر ──────────────────────────────────────────────
    st.divider()
    st.subheader("🔬 Culture & Microscopic Details")

    # Colony count is a urine-only concept — showing/carrying it into a
    # blood/sputum/CSF report is clinically wrong. Only render it for urine;
    # for other specimens send nothing downstream (stored value is preserved
    # so switching back to Urine restores it).
    if "urine" in (page.culture_type or "").lower():
        page.colony_count = st.text_input(
            "Colony Count (CFU/mL)",
            value=st.session_state.colony_count,
            placeholder="≥ 10^5 CFU/mL",
            key="colony_count_input"
        )
        st.session_state.colony_count = page.colony_count
    else:
        page.colony_count = ""

    page.date_in = st.date_input(
        "📅 Date In (تاريخ استلام العينة)",
        value=st.session_state.date_in,
        key="date_in_input"
    )
    st.session_state.date_in = page.date_in

    # ── Auto-populate Pus/RBCs/Condition from OCR -- only ONCE per file ────
    _ocr_done_key = f"_ocr_filled_{page.file_hash[:12]}"
    if page.payload and not st.session_state.get(_ocr_done_key, False):
        _ocr_pus = page.payload.get("pus_cells", "")
        _ocr_rbc = page.payload.get("rbcs", "")
        _ocr_cnd = page.payload.get("condition", "")
        _filled  = []
        if _ocr_pus and not st.session_state.get("pus_cells_text",""):
            st.session_state.pus_cells_text = _ocr_pus
            _filled.append(f"Pus: {_ocr_pus}/HPF")
        if _ocr_rbc and not st.session_state.get("rbcs_text",""):
            st.session_state.rbcs_text = _ocr_rbc
            _filled.append(f"RBCs: {_ocr_rbc}/HPF")
        if _ocr_cnd and st.session_state.get("culture_condition","Aerobic") == "Aerobic":
            st.session_state.culture_condition = _ocr_cnd
            _filled.append(f"Condition: {_ocr_cnd}")
        if _filled:
            st.toast("🔍 OCR auto-filled: " + " | ".join(_filled), icon="🔬")
        st.session_state[_ocr_done_key] = True  # never fire again for this file

    c_pus, c_rbc = st.columns(2)
    with c_pus:
        page.pus_cells_text = st.text_input(
            "Pus Cells (/HPF)",
            value=st.session_state.pus_cells_text,
            placeholder="مثال: 4 - 6",
            key="pus_cells_input"
        )
        st.session_state.pus_cells_text = page.pus_cells_text
    with c_rbc:
        page.rbcs_text = st.text_input(
            "RBC Cells (/HPF)",
            value=st.session_state.rbcs_text,
            placeholder="مثال: 2 - 4",
            key="rbcs_input"
        )
        st.session_state.rbcs_text = page.rbcs_text

    # Organism guidance
    if page.organism_type in ORGANISM_PROFILE:
        op = ORGANISM_PROFILE[page.organism_type]
        with st.expander("📌 Organism Guidance", expanded=True):
            st.info(op.get("note", ""))
            spec_ctx = (op.get("specimen_context") or {}).get(page.culture_type, "")
            if spec_ctx:
                st.warning(f"**{page.culture_type} Context:** {spec_ctx}")
            _t_first_line = _drop_intrinsic(
                _hide_urine_only(op.get("first_line"), page.culture_type), page.organism_type)
            if _t_first_line:
                st.write("**First-line:**", ", ".join(_t_first_line))
            _t_second_line = _drop_intrinsic(
                _hide_urine_only(op.get("second_line"), page.culture_type), page.organism_type)
            if _t_second_line:
                st.write("**Second-line:**", ", ".join(_t_second_line))
            _t_third_line = _drop_intrinsic(
                _hide_urine_only(op.get("third_line"), page.culture_type), page.organism_type)
            if _t_third_line:
                st.write("**Third-line:**", ", ".join(_t_third_line))
            if op.get("avoid"):
                st.error("**Avoid:** " + ", ".join(op["avoid"]))
            if page.culture_type == "Urine" and op.get("urine_note"):
                st.info(f"📌 Urine notes:\n{op['urine_note']}")


def render_patient(page):
    """Age, weight, creatinine, renal / hepatic / pregnancy flags, allergies, test options."""
    st.divider()

    # Infants are common in every culture type, and a plain "Age (years)"
    # field forces them to 0 -- which reads as "0 yrs" on the report and
    # seeds a wrong weight. Offer months instead; the clinical engines still
    # receive age=0 (years), so all existing pediatric logic is unchanged.
    _ocr_months = page.patient.get("AgeMonths")
    _ocr_under_1 = (_ocr_months is not None
                    or safe_int(page.patient.get("Age"), 25) == 0)
    # Round 5: an age the OCR could not read used to become "25 years"
    # with nothing on screen saying it was a guess, and "Age: 3 M" (three
    # months, or 3 years / Male?) was read as years. Both now ask.
    if page.patient.get("Age") is None:
        st.warning("⚠️ العمر لم يُقرأ من التقرير — القيمة 25 سنة افتراضية وليست عمر "
                   "المريض. أدخل العمر الصحيح: حظر أدوية الأطفال والرضّع يعتمد عليه.")
    elif page.patient.get("AgeAmbiguous"):
        st.warning(f"⚠️ العمر مكتوب «{page.patient.get('Age')} M» — قد يعني شهوراً أو "
                   "(سنوات + Male). قُرئ كسنوات؛ لو المريض رضيع علّم «أقل من سنة» "
                   "وأدخل الشهور.")
    _under_1 = st.checkbox("👶 أقل من سنة (< 1 year)", value=bool(_ocr_under_1),
                           key=f"under1_{page._fh}")
    if _under_1:
        page.age_months = st.number_input(
            "Age (months)", min_value=0, max_value=11,
            value=safe_int(_ocr_months, 6), step=1, key=f"age_months_{page._fh}")
        page.age = 0
        st.caption(f"👶 رضيع {page.age_months} شهر -- يُقيَّم إكلينيكياً كعمر 0 "
                   f"(Infant < 1 yr: أي عدد مستعمرات ذو دلالة).")
    else:
        page.age_months = None
        page.age = st.number_input("Age (years)", min_value=0, max_value=120,
                               value=safe_int(page.patient.get("Age"), 25),
                               key=f"age_years_{page._fh}")
    default_sex = page.patient.get("Sex") if page.patient.get("Sex") in ["Female", "Male"] else "Male"
    page.sex    = st.selectbox("Gender", ["Female", "Male"],
                          index=0 if default_sex == "Female" else 1,
                          key=f"sex_sel_{page._fh}")
    # Age-appropriate default (APLS estimate) so pediatric CrCl/dosing isn't
    # seeded with an adult 70 kg. Still fully editable.
    # Infants use the WHO/APLS infant rule: kg ≈ (months + 9) / 2.
    _wt_default = (
        max(1, round((page.age_months + 9) / 2)) if page.age_months is not None
        else 8 if page.age < 1
        else int(2 * (page.age + 4)) if page.age <= 5
        else int(3 * page.age + 7) if page.age <= 12
        else 70
    )
    # A neonate is ~3.5 kg, so the adult-oriented 5 kg floor has to drop for
    # infants or the correct weight simply cannot be entered.
    _wt_min = 1 if page.age_months is not None else 5
    # The key carries the age so the age-appropriate default is re-seeded
    # when the age changes (a keyed widget keeps its value otherwise).
    page.weight = st.number_input("Weight (kg)", min_value=_wt_min, max_value=300,
                             value=_wt_default,
                             key=f"weight_{page._fh}_{page.age}_{page.age_months}")

    st.divider()

    # Patient-fact widgets are keyed PER FILE (round 4, 2026-11-11): a new
    # report recreates them empty instead of inheriting the last patient's
    # flags. The old keys carry the old hash and are deleted on upload.
    # (_fh is defined above, with the specimen widget.)
    _renal_flag = st.checkbox("🚩 Renal Impairment", key=f"renal_flag_{page._fh}")
    # Always offered, not hidden behind the checkbox: a reduced clearance that
    # nobody thought to flag is exactly the case that needs catching.
    s_cr = st.number_input(
        "Serum Creatinine (mg/dL) — leave 0 if not available",
        min_value=0.0, max_value=20.0, value=0.0, step=0.1,
        key=f"scr_{page._fh}",
        help="If entered, CrCl is calculated (Cockcroft-Gault for adults, "
             "bedside Schwartz for under-18s) and a value below 60 ml/min "
             "engages renal dosing on its own.")
    # Children: Cockcroft-Gault is validated in adults only. Fed an infant's
    # weight and creatinine it reports a healthy neonate (3.5 kg, SCr 0.5)
    # as ~14 ml/min -- kidney failure -- which refused gentamicin (the
    # standard neonatal sepsis partner) and cut the dose of everything
    # renally cleared. Under 18 the bedside Schwartz equation is used, and
    # it needs the height (round 4, 2026-11-11).
    _height = 0.0
    if page.age < 18 and s_cr > 0:
        _height = st.number_input(
            "Height (cm) — needed for paediatric eGFR (Schwartz)",
            min_value=0.0, max_value=200.0, value=0.0, step=1.0,
            key=f"height_{page._fh}")
    # cl_cr is None when nothing was measured. It used to be set to 100.0,
    # which is a NORMAL clearance, so ticking the impairment box without a
    # creatinine produced exactly the same recommendations as a patient with
    # healthy kidneys: no dose-adjustment note on any agent (no renal_limit
    # reaches 100) and Nitrofurantoin recommended rather than refused.
    page.cl_cr = None
    if s_cr > 0 and page.age >= 18:
        page.cl_cr = calc_creatinine_clearance(page.age, page.weight, s_cr, page.sex)
        st.metric("CrCl (Cockcroft-Gault)", f"{page.cl_cr:.1f} ml/min",
                  delta=get_renal_severity(page.cl_cr),
                  delta_color="normal" if page.cl_cr >= 60 else ("off" if page.cl_cr >= 30 else "inverse"))
    elif s_cr > 0:
        page.cl_cr = calc_paediatric_egfr(_height, s_cr, page.age, page.age_months)
        if page.cl_cr is None:
            st.warning("⚠️ Cockcroft-Gault غير صالح تحت 18 سنة — أدخل الطول لحساب "
                       "eGFR بمعادلة Schwartz. لم تُحسب وظيفة الكلى من الكرياتينين.")
        else:
            st.metric("eGFR (bedside Schwartz)", f"{page.cl_cr:.1f} ml/min/1.73m²",
                      delta=get_renal_severity(page.cl_cr),
                      delta_color="normal" if page.cl_cr >= 60 else ("off" if page.cl_cr >= 30 else "inverse"))
    # Under two years a GFR below 60 is physiological (it matures over the
    # first two years), so it must not switch adult renal dosing on by
    # itself; the value is used only if the clinician flags impairment.
    if page.cl_cr is not None and page.age < 2 and not _renal_flag:
        st.caption("ℹ️ GFR الطبيعي أقل من البالغين في أول سنتين — لم يُفعَّل تعديل الجرعة "
                   "الكلوي تلقائياً. علّم Renal Impairment إن كان هناك قصور فعلي.")
        page.cl_cr = None
    # Engage renal handling if EITHER the clinician flagged it OR the measured
    # clearance is impaired.
    page.is_renal = bool(_renal_flag) or (page.cl_cr is not None and page.cl_cr < 60)
    if page.is_renal and page.cl_cr is None:
        st.warning(
            f"⚠️ Renal impairment flagged with no creatinine. Dosing will "
            f"assume **CrCl ≈ {ASSUMED_CRCL_UNKNOWN:.0f} ml/min** (the "
            f"conservative direction) and every renal note will say so. "
            f"Enter the creatinine for patient-specific doses.")
    elif page.is_renal and not _renal_flag:
        st.warning(f"⚠️ CrCl {page.cl_cr:.0f} ml/min — renal dose adjustment applied "
                   "automatically (the impairment box was not ticked).")

    page.is_hepatic = st.checkbox("🚩 Hepatic Impairment", key=f"hepatic_{page._fh}")
    # ── Child-Pugh is captured HERE, next to the flag that needs it ────────
    # It used to be asked for inside an expander further down the page, which
    # in Streamlit's top-to-bottom execution runs AFTER analyze_antibiotics().
    # So on the run where the clinician ticked hepatic impairment the engine
    # was still evaluating the seeded grade, and the hepatic contraindications
    # never fired on the screen that mattered. Asking here removes the
    # ordering dependency permanently rather than papering over it.
    if page.is_hepatic:
        child_pugh_class = st.selectbox(
            "Child-Pugh Class", ["C", "B", "A"],
            index=["C", "B", "A"].index(
                st.session_state.get("child_pugh_class", "C")),
            format_func=lambda x: {"A": "A — Mild (5-6 pts)",
                                   "B": "B — Moderate (7-9 pts)",
                                   "C": "C — Severe (10-15 pts)"}[x],
            key=f"cp_sel_sidebar_{page._fh}",
            help="Starts at C (most conservative) until graded. Grade the "
                 "patient — C refuses agents that are acceptable in A.")
        st.session_state.child_pugh_class = child_pugh_class
        if child_pugh_class == "C":
            st.caption("⚠️ Assuming Child-Pugh C until graded.")
    page.is_preg    = False
    if page.sex == "Female":
        page.is_preg = st.checkbox(
            "🤰 Patient is Pregnant", key=f"preg_{page._fh}",
            help="Shown for every female patient. The age window used to hide "
                 "this control entirely, which made the pregnancy safety rules "
                 "unreachable outside 15-55 rather than merely unticked.")

    page.current_meds = st.multiselect("💊 Current Medications", COMMON_MEDS, key=f"meds_{page._fh}")

    # ─── Added 2026-11-10 (guideline review) ─────────────────────────────
    # Three facts the engine could not know, and which change the answer:
    # the allergy (Patient.allergies existed and nothing filled it), the
    # carbapenemase CLASS (decides between the novel agents, IDSA 2026),
    # and whether a urine isolate is cystitis or pyelonephritis.
    page.allergies = st.multiselect(
        "🚫 Drug allergies",
        ["Penicillin — mild / delayed rash", "Penicillin — severe / anaphylaxis",
         "Cephalosporin", "Ceftazidime", "Sulfonamide (sulfa)",
         "Fluoroquinolone", "Macrolide"],
        key=f"allergies_input_{page._fh}",
        help="الحساسية المسجّلة تحظر الصنف نفسه، وتضيف تحذير تفاعل متصالب للأصناف القريبة.")
    page.carbapenemase_choice = st.selectbox(
        "🧬 Carbapenemase type (if tested)", list(CARBAPENEMASE_TYPE_OPTIONS),
        key=f"carb_type_input_{page._fh}",
        help="من NG-Test CARBA-5 أو Xpert Carba-R أو PCR. يحدد أي عامل حديث يعمل "
             "(KPC / OXA-48 / MBL) — IDSA AMR Guidance 2026.")
    page.uti_syndrome_choice = st.selectbox(
        "🫘 UTI syndrome (urine only)", list(UTI_SYNDROME_OPTIONS),
        key=f"uti_syndrome_input_{page._fh}",
        help="تلقائي: حمى أو ألم الخاصرة ← التهاب حويضة/cUTI. Nitrofurantoin و Fosfomycin "
             "الفموي و Norfloxacin لا تصلح للحويضة.")


def render_lab_fields(page):
    """Lab report fields (dates, numbers, signatures)."""
    # ─── New clinical/lab fields ──────────────────────────────────────────
    with st.expander("🏥 Lab Report Fields", expanded=False):
        _ref_phys = st.text_input(
            "Referred by (Physician Name)",
            value=st.session_state.get("referring_physician",""),
            placeholder="Dr. Ahmed Mohamed",
            key="ref_phys_input"
        )
        st.session_state.referring_physician = _ref_phys

        _culture_cond = st.selectbox(
            "Culture Condition",
            ["Aerobic", "Anaerobic", "Both (Aerobic + Anaerobic)"],
            index=["Aerobic","Anaerobic","Both (Aerobic + Anaerobic)"].index(
                st.session_state.get("culture_condition","Aerobic")
            ),
            key="culture_cond_sel"
        )
        st.session_state.culture_condition = _culture_cond

        _micro_name = st.text_input(
            "Microbiologist Name",
            value=st.session_state.get("microbiologist",""),
            placeholder="Dr. Aya Gamal",
            key="micro_name_input"
        )
        st.session_state.microbiologist = _micro_name
