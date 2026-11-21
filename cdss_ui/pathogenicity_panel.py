# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Left column: pathogenicity assessment.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.common.specimen import classify_specimen
from cdss.organisms.pathogenicity import BLOOD_SET_OPTIONS
from cdss.organisms.pathogenicity import HOST_FACTORS_OTHER
from cdss.organisms.pathogenicity import HOST_FACTORS_URINE
from cdss.organisms.pathogenicity import RESPIRATORY_SIGNS
from cdss.organisms.pathogenicity import RESP_SPECIMEN_SUBTYPES
from cdss.organisms.pathogenicity import URINE_COLLECTION_METHODS
from cdss.organisms.pathogenicity import SCI_TYPE_SYMPTOMS, SYMPTOM_COURSE_OPTIONS
from cdss.organisms.pathogenicity import (AD_ASSESSMENT_OPTIONS, AD_SYMPTOM,
                                          CATHETER_SAMPLE_SITES, catheter_collection)
from cdss.organisms.pathogenicity import URINE_SYMPTOMS
from cdss.organisms.pathogenicity import WOUND_SIGNS
from cdss.organisms.pathogenicity import WOUND_TYPES
from cdss.organisms.pathogenicity import assess_pathogenicity
from cdss.organisms.pathogenicity import gram_choice_in, gram_options_for
from cdss_ui.patho_view import _render_patho_result
from cdss_ui.resistance_panels import render_resistance_profile
from cdss_ui.state import patho_signature


def _patho_age(page) -> float:
    """Age in years with the months the UI collects for infants (v7.1): the
    pathogenicity rules split under 2 months / 2-24 months (AAP 2021 / 2011).
    v7.2: the days, when entered for an infant under 2 months (first week /
    8-60 days). v7.3: up to 2 months -- the 60 / 61-day boundary."""
    from cdss.common.clinical_utils import resolve_age_years
    _days = getattr(page, "age_days", None)
    _m = getattr(page, "age_months", None)
    if _days is not None and _m is not None and _m <= 2:
        try:
            return float(_days) / 365.25
        except (TypeError, ValueError):
            pass
    a = resolve_age_years(page.age, _m)
    return float(a if a is not None else (page.age or 0))


def _age_label(page) -> str:
    """The age as the clinician entered it (days / months / years)."""
    if getattr(page, "age_days", None) is not None and getattr(page, "age_months", None) is not None:
        return f"{page.age_days} days"
    if getattr(page, "age_months", None) is not None:
        return f"{page.age_months} months"
    return f"{page.age} years"


def _calc_and_track(kwargs: dict, clicked: bool) -> bool:
    """Run the engine on a click; mark a kept result stale when the inputs moved.

    v7.2 (second external review 2026-11-19): a result calculated for other
    inputs (symptoms ticked later, the collection method corrected) stayed on
    screen and flowed into the gate, the checklist and the reports as current.
    Returns True when the shown result is current.
    """
    _sig = patho_signature(kwargs)
    if clicked:
        st.session_state.patho_result = assess_pathogenicity(**kwargs)
        st.session_state.patho_sig = _sig
    _res = st.session_state.get("patho_result")
    _stale = bool(_res) and st.session_state.get("patho_sig") != _sig
    st.session_state.patho_stale = _stale
    if _stale:
        st.warning("⚠️ المدخلات اتغيرت بعد آخر حساب — النتيجة القديمة لم تعد تُستخدم في التوصيات "
                   "ولا قائمة المراجعة ولا التقارير. اضغط «احسب Pathogenicity Score» تاني.")
    return bool(_res) and not _stale


def render_pathogenicity(page):
    """Pathogenicity assessment (urine and non-urine) and, for non-urine, the resistance panels."""
    # ── Pathogenicity Assessment Module v2 ───────────────────────────────
    # ⚠️ التعديل: Pathogenicity Assessment يظهر للبول فقط.
    #    لباقي المزارع يظهر بدلاً منه: Resistance Profile (ESBL / MDR / XDR / PDR).
    _is_urine_specimen = "urine" in page.culture_type.lower()

    # Clear stale patho_result when specimen changes
    if st.session_state.get("last_patho_specimen","") != page.culture_type:
        st.session_state.patho_result = None
        st.session_state.patho_sig = None
        st.session_state.patho_stale = False
        st.session_state.last_patho_specimen = page.culture_type
        # Reset specimen-specific symptoms to avoid stale defaults
        st.session_state.patho_symptoms = []
        st.session_state.patho_sirs = []
        st.session_state.patho_blood_source = ""
        st.session_state.patho_wound_type = ""

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════
    # الفرع (أ): Pathogenicity Assessment -- للبول فقط
    # ═══════════════════════════════════════════════════════════════════════
    if _is_urine_specimen:
        with st.expander("🧫 Pathogenicity Assessment", expanded=False):
            st.caption("هل العينة تمثل عدوى حقيقية أم تلوث؟ -- خاص بمزارع البول")

            pa_col1, pa_col2 = st.columns(2)
            with pa_col1:
                patho_purity = st.selectbox(
                    "نقاء المزرعة",
                    ["Pure growth", "Mixed growth"],
                    index=0 if st.session_state.patho_culture_purity == "Pure growth" else 1,
                    key="patho_purity_sel"
                )
                st.session_state.patho_culture_purity = patho_purity

                _gram_opts = gram_options_for(page.organism_type)
                # v7.0: a choice remembered from another organism (or a pre-v7.0
                # "Rods" label) is mapped or dropped, never kept out of sight.
                if "patho_gram_sel" in st.session_state:
                    _g_keep = gram_choice_in(st.session_state["patho_gram_sel"], _gram_opts)
                    if _g_keep is None:
                        del st.session_state["patho_gram_sel"]
                    else:
                        st.session_state["patho_gram_sel"] = _g_keep
                patho_gram = st.selectbox(
                    "Gram Stain",
                    _gram_opts,
                    key="patho_gram_sel",
                    help="Gram-variable = نتيجة صبغة وليست نوع بكتيريا: Acinetobacter، "
                         "Gardnerella، مزارع قديمة، أو خطأ إزالة اللون."
                )
                st.session_state.patho_gram_stain = patho_gram

            with pa_col2:
                patho_urinalysis = st.selectbox(
                    "نتيجة Urinalysis",
                    ["مش معروف / مش مذكور", "Urinalysis طبيعي",
                     "Pyuria (WBCs > 5/HPF)", "Nitrites Positive", "Hematuria"],
                    key="patho_ua_sel"
                )
                st.session_state.patho_urinalysis = patho_urinalysis

                # v7.4 (external case review): the laboratory report printed "Mid
                # stream urine" and the case was entered as a Foley specimen. The
                # report's method (OCR) now pre-selects this field and is shown
                # beside it; a disagreement is a CRITICAL alert (analysis step).
                _ocr_pt = getattr(page, "patient", None) or {}
                _lab_coll = _ocr_pt.get("CollectionMethod") if isinstance(_ocr_pt, dict) else None
                if (_lab_coll in URINE_COLLECTION_METHODS
                        and "patho_coll_sel" not in st.session_state):
                    st.session_state["patho_coll_sel"] = _lab_coll
                patho_collection = st.selectbox(
                    "طريقة جمع العينة",
                    URINE_COLLECTION_METHODS,
                    key="patho_coll_sel",
                    help="عتبة عدّ المستعمرات تختلف حسب طريقة الجمع: midstream / قسطرة "
                         "(≥10³ مع أعراض) / SPA (أي نمو) — IDSA 2009 و AAP."
                )
                if _lab_coll:
                    st.caption(f"📄 تقرير المعمل: **{_lab_coll}**"
                               + ("" if _lab_coll == patho_collection else
                                  " — ⛔ مختلف عن الاختيار"))
                # v7.9 (external case review): the device is not the method --
                # where on the catheter the urine was drawn decides if it is valid.
                patho_sample_site = ""
                if catheter_collection(patho_collection):
                    patho_sample_site = st.selectbox(
                        "العينة اتسحبت منين في القسطرة؟",
                        CATHETER_SAMPLE_SITES, key="patho_site_sel",
                        help="الصحيح: منفذ أخذ العينات بعد تطهيره (ومن قسطرة جديدة لو القديمة ≥ "
                             "أسبوعين). بول الكيس أو من حول القسطرة / مكان دخولها في الجلد = عينة "
                             "مرفوضة (IDSA CA-UTI 2009).")
                # v7.0: the one case record (cdss.common.case_context) reads this
                st.session_state.patho_collection = patho_collection

            # ── Urine symptoms ─────────────────────────────────────────
            patho_symptoms = st.multiselect(
                "الأعراض الكلينيكية",
                URINE_SYMPTOMS,
                default=[x for x in st.session_state.patho_symptoms if x in URINE_SYMPTOMS],
                key="patho_symp_urine",
                help="اختر Asymptomatic صراحةً لو المريض بلا أعراض — ترك الخانة فاضية معناه "
                     "«غير مُدخل» ولا يُحتسب ضد العدوى. أعراض (SCI) تُحتسب مع إصابة النخاع "
                     "الشوكي أو القسطرة فقط."
            )
            st.session_state.patho_symptoms = patho_symptoms
            # v7.4 (external case review): catheter / SCI symptoms count only when
            # new or worse than baseline and unexplained (IDSA CA-UTI 2009).
            patho_course = ""
            if any(x in SCI_TYPE_SYMPTOMS for x in patho_symptoms):
                patho_course = st.selectbox(
                    "أعراض القسطرة / إصابة النخاع: جديدة ولا موجودة من قبل؟",
                    SYMPTOM_COURSE_OPTIONS, key="patho_course_sel",
                    help="IDSA CA-UTI 2009: التوعك / الخمول / التشنج / الـ dysreflexia / التسريب "
                         "تُحتسب فقط لو جديدة أو أسوأ من المعتاد ومفيش سبب تاني. «موجودة من قبل» = "
                         "bacteriuria مرتبطة بالقسطرة ولا تُعالَج. بدون إجابة: «عدوى محتملة» فقط.")
            # v7.9 (external case review): sweating above the injury level was
            # entered as autonomic dysreflexia and scored as a confirmed symptom.
            patho_ad = ""
            if AD_SYMPTOM in patho_symptoms:
                patho_ad = st.selectbox(
                    "الـ Autonomic dysreflexia: متأكدة؟",
                    AD_ASSESSMENT_OPTIONS, key="patho_ad_sel",
                    help="الـ AD = ارتفاع الضغط الانقباضي ≥ 20 مم زئبق عن المعتاد للمريض (مع تعرق / "
                         "احمرار فوق مستوى الإصابة). التعرق وحده = اشتباه فقط. لو السبب قسطرة مسدودة أو "
                         "مثانة ممتلئة أو إمساك أو قرحة: مش عَرَض UTI. وفي كل الأحوال: حالة طارئة — "
                         "اجلس المريض وقِس الضغط وافحص القسطرة الآن.")
                st.error("🚨 Autonomic dysreflexia حالة طارئة: اجلس المريض، قِس الضغط كل 2–5 دقائق، "
                         "وافحص القسطرة / المثانة والأمعاء والجلد الآن — لا تنتظر المزرعة.")

            # Host factors
            patho_host = st.multiselect(
                "عوامل المضيف",
                HOST_FACTORS_URINE,
                default=[x for x in st.session_state.patho_host_factors
                         if x in HOST_FACTORS_URINE],
                key="patho_host_sel",
                help="Paraplegia / Quadriplegia = مثانة عصبية: الـ bacteriuria شبه دائمة ولا "
                     "تُعالَج بلا أعراض، والأعراض غير نمطية (spasticity / dysreflexia)."
            )
            st.session_state.patho_host_factors = patho_host

            # FIX 2026-11-11 (round 4): the engine read pregnancy only from
            # this multiselect, never from the sidebar flag, so a pregnant
            # patient's asymptomatic bacteriuria >= 10^5 came back "do NOT
            # treat" -- IDSA 2019 says treat it -- unless "Pregnant" was ticked
            # a second time here.
            if page.is_preg and "Pregnant" not in patho_host:
                patho_host = list(patho_host) + ["Pregnant"]
            patho_kwargs = dict(
                specimen=page.culture_type,
                organism=page.organism_type,
                colony_count_text=page.colony_count,
                culture_purity=patho_purity,
                symptoms=patho_symptoms,
                pus_cells_text=page.pus_cells_text,
                urinalysis_result=patho_urinalysis,
                gram_stain=patho_gram,
                age=_patho_age(page),
                sex=page.sex,
                host_factors=patho_host,
                collection_method=patho_collection,
                symptom_course=patho_course,
                ad_assessment=patho_ad,
                catheter_sample_site=patho_sample_site,
            )
            _clicked = st.button("🔬 احسب Pathogenicity Score", use_container_width=True,
                                 key="patho_calc_btn")
            if _clicked:
                st.session_state.patho_pdf_ctx = {
                    "panel": "urine", "organism": page.organism_type, "specimen": page.culture_type,
                    "inputs": {
                        "Colony count": patho_kwargs.get("colony_count_text"),
                        "Collection method": patho_kwargs.get("collection_method"),
                        # v7.4: what the laboratory report says, beside what was entered
                        "Collection (lab report)": _lab_coll or "—",
                        "Culture purity": patho_kwargs.get("culture_purity"),
                        "Pus cells / HPF": patho_kwargs.get("pus_cells_text"),
                        "Urinalysis": patho_kwargs.get("urinalysis_result"),
                        "Gram stain": patho_kwargs.get("gram_stain"),
                        "Symptoms": patho_kwargs.get("symptoms"),
                        "Symptom course": patho_kwargs.get("symptom_course") or "—",
                        # v7.9
                        "Catheter sampling site": patho_kwargs.get("catheter_sample_site") or "—",
                        "Autonomic dysreflexia": patho_kwargs.get("ad_assessment") or "—",
                        "Host factors": patho_kwargs.get("host_factors"),
                        "Age / Sex": f"{_age_label(page)} / {patho_kwargs.get('sex')}",
                    }}
                # v7.9: the two new rows only where they were asked
                _inp = st.session_state.patho_pdf_ctx["inputs"]
                if not catheter_collection(patho_collection):
                    _inp.pop("Catheter sampling site", None)
                if AD_SYMPTOM not in (patho_symptoms or []):
                    _inp.pop("Autonomic dysreflexia", None)

            # ── Display Result (persists after button, only while current) ──
            if _calc_and_track(patho_kwargs, _clicked):
                _render_patho_result(st.session_state.get("patho_result"))

    # ═══════════════════════════════════════════════════════════════════════
    # الفرع (ب): Resistance Profile -- لكل المزارع غير البول
    #    يعرض: MDR/XDR/PDR + ESBL/AmpC/Carbapenemase + Phenotypes
    # ═══════════════════════════════════════════════════════════════════════
    else:
        # ═══════════════════════════════════════════════════════════════
        # الفرع (ب-1): Pathogenicity Assessment للعينات غير البول
        #   Blood (SIRS) · Sputum (Murray-Washington) · Stool (GI flora) ·
        #   Wound/Pus (SSTI) · CSF (sterile site)
        # ═══════════════════════════════════════════════════════════════
        _pcat = classify_specimen(page.culture_type)
        if _pcat in ("blood", "sputum", "stool", "wound", "pus", "csf"):
            _pcap = {
                "blood":  "هل عدوى مجرى دم حقيقية أم تلوث؟ -- SIRS + نوع الكائن",
                "sputum": "هل عينة بلغم كافية أم لعاب؟ -- Murray-Washington",
                "stool":  "هل ممرض معوي حقيقي أم flora طبيعي؟",
                "wound":  "هل ممرض جرح حقيقي؟ -- نوع الجرح + العلامات الموضعية",
                "pus":    "هل ممرض حقيقي؟ -- نوع الجرح + العلامات الموضعية",
                # v7.2 (second external review): "any growth is pathogenic" contradicted
                # the engine, which reads skin flora without a shunt as a likely contaminant.
                "csf":    "CSF موقع معقم: ممرض معروف = ذو دلالة؛ فلورا الجلد بدون shunt/EVD قد تكون تلوثاً",
            }[_pcat]
            with st.expander("🧫 Pathogenicity Assessment", expanded=False):
                st.caption(_pcap)

                # ── Common inputs ──────────────────────────────────────
                np_c1, np_c2 = st.columns(2)
                with np_c1:
                    np_purity = st.selectbox(
                        "نقاء المزرعة",
                        ["Pure growth", "Mixed growth"],
                        key="np_purity_sel")
                with np_c2:
                    _np_gram_opts = gram_options_for(page.organism_type)
                    if "np_gram_sel" in st.session_state:
                        _np_keep = gram_choice_in(st.session_state["np_gram_sel"], _np_gram_opts)
                        if _np_keep is None:
                            del st.session_state["np_gram_sel"]
                        else:
                            st.session_state["np_gram_sel"] = _np_keep
                    np_gram = st.selectbox(
                        "Gram Stain",
                        _np_gram_opts,
                        key="np_gram_sel",
                        help="Gram-variable = نتيجة صبغة وليست نوع بكتيريا: Acinetobacter، "
                             "Gardnerella، مزارع قديمة، أو خطأ إزالة اللون.")

                # ── Category-specific inputs ───────────────────────────
                np_sirs = []; np_blood_source = ""
                np_sputum_wbc = ""; np_sputum_epi = ""
                np_wound_type = ""; np_symptoms = []
                np_spec = page.culture_type; np_cfu = page.colony_count

                if _pcat == "blood":
                    # v7.2 (second external review): SIRS is not sepsis (Sepsis-3), and
                    # bottles are not sets -- several bottles of one venepuncture are one
                    # draw. "Multiple bottles positive" was scored as independent sets.
                    np_sirs = st.multiselect(
                        "SIRS criteria (≥2 = SIRS criteria met · sepsis = infection + organ "
                        "dysfunction, Sepsis-3)",
                        ["Temp > 38°C or < 36°C",
                         "Heart rate > 90 / min",
                         "Resp rate > 20 / min (or PaCO₂ < 32)",
                         "WBC > 12k or < 4k (or > 10% bands)"],
                        key="np_sirs_ms")
                    if st.session_state.get("np_bsrc_sel") not in (None, *BLOOD_SET_OPTIONS):
                        # a pre-v7.2 "bottles" label: bottles are not sets -- ask again
                        st.session_state["np_bsrc_sel"] = BLOOD_SET_OPTIONS[0]
                    np_blood_source = st.selectbox(
                        "المجموعات (sets) الإيجابية — لا الزجاجات",
                        BLOOD_SET_OPTIONS,
                        key="np_bsrc_sel",
                        help="المجموعة = سحبة واحدة (وخز واحد) مهما كان عدد الزجاجات. CoNS وفلورا "
                             "الجلد تُعتبر حقيقية فقط بنفس الكائن في مجموعتين مسحوبتين بشكل منفصل.")

                elif _pcat == "sputum":
                    _cl = page.culture_type.lower()
                    if not any(k in _cl for k in ("throat", "pharyn", "tonsil")):
                        # v7.2: the threshold depends on the specimen (BAL 10^4,
                        # PSB 10^3, ETA 10^5 / semi-quantitative); only "Sputum" existed.
                        np_sub = st.selectbox("نوع العينة التنفسية", RESP_SPECIMEN_SUBTYPES,
                                              key="np_resp_sub_sel")
                        if np_sub != RESP_SPECIMEN_SUBTYPES[0]:
                            np_spec = f"{page.culture_type} — {np_sub}"
                            np_cfu = st.text_input(
                                "العدّ الكمّي / شبه الكمّي",
                                placeholder="مثال: 10^4 CFU/mL أو moderate growth",
                                key="np_resp_cfu",
                                help="BAL ≥ 10⁴ · PSB ≥ 10³ · ETA ≥ 10⁵ أو moderate/heavy growth "
                                     "(ATS/IDSA 2016).")
                    sp_c1, sp_c2 = st.columns(2)
                    with sp_c1:
                        np_sputum_wbc = st.text_input(
                            "WBCs / LPF", placeholder="مثال: 25",
                            key="np_spwbc")
                    with sp_c2:
                        np_sputum_epi = st.text_input(
                            "Epithelial cells / LPF", placeholder="مثال: 5",
                            key="np_spepi")
                    np_symptoms = st.multiselect(
                        "الأعراض التنفسية",
                        RESPIRATORY_SIGNS,
                        key="np_symp_resp")

                elif _pcat == "stool":
                    np_symptoms = st.multiselect(
                        "الأعراض المعوية",
                        ["Fever (> 38°C)", "Bloody diarrhea",
                         "Watery diarrhea", "Vomiting", "Abdominal cramps"],
                        key="np_symp_gi")

                elif _pcat in ("wound", "pus"):
                    np_wound_type = st.selectbox(
                        "نوع الجرح",
                        WOUND_TYPES,
                        key="np_wtype_sel")
                    np_symptoms = st.multiselect(
                        "علامات العدوى الموضعية",
                        WOUND_SIGNS,
                        key="np_symp_wound")

                elif _pcat == "csf":
                    st.info("🧠 CSF موقع معقم. فلورا الجلد (CoNS وغيرها) بدون shunt/EVD أو "
                            "جراحة أعصاب حديثة قد تكون تلوثاً — سجّل الجهاز في عوامل المضيف.")

                # ── Host factors (shared) ──────────────────────────────
                np_host = st.multiselect(
                    "عوامل المضيف",
                    HOST_FACTORS_OTHER,
                    key="np_host_sel",
                    help="Paraplegia / Quadriplegia: قرح الفراش (مسحة سطحية = استعمار) وضعف "
                         "السعال في الإصابات العنقية يغيّران تفسير المزرعة.")

                np_kwargs = dict(
                    specimen=np_spec,
                    organism=page.organism_type,
                    colony_count_text=np_cfu,
                    culture_purity=np_purity,
                    symptoms=np_symptoms,
                    pus_cells_text="",
                    urinalysis_result="",
                    gram_stain=np_gram,
                    age=_patho_age(page), sex=page.sex,
                    host_factors=np_host,
                    sputum_pus_cells=np_sputum_wbc,
                    sputum_epithelial=np_sputum_epi,
                    sirs_criteria=np_sirs,
                    blood_source=np_blood_source,
                    wound_type=np_wound_type,
                )
                _np_clicked = st.button("🔬 احسب Pathogenicity Score",
                                        use_container_width=True, key="np_calc_btn")
                if _np_clicked:
                    st.session_state.patho_pdf_ctx = {
                        "panel": "other", "organism": page.organism_type, "specimen": np_spec,
                        "inputs": {
                            "Colony count": np_cfu, "Culture purity": np_purity,
                            "Gram stain": np_gram, "Signs / symptoms": np_symptoms,
                            "SIRS criteria": np_sirs, "Positive independent sets": np_blood_source,
                            "Sputum WBC / LPF": np_sputum_wbc,
                            "Sputum epithelial / LPF": np_sputum_epi,
                            "Wound type": np_wound_type, "Host factors": np_host,
                            "Age / Sex": f"{_age_label(page)} / {page.sex}",
                        }}

                if _calc_and_track(np_kwargs, _np_clicked):
                    _render_patho_result(st.session_state.get("patho_result"))

        render_resistance_profile(page)
