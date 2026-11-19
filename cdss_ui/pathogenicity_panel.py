# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Left column: pathogenicity assessment.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.common.specimen import classify_specimen
from cdss.organisms.pathogenicity import HOST_FACTORS_OTHER
from cdss.organisms.pathogenicity import HOST_FACTORS_URINE
from cdss.organisms.pathogenicity import RESPIRATORY_SIGNS
from cdss.organisms.pathogenicity import URINE_COLLECTION_METHODS
from cdss.organisms.pathogenicity import URINE_SYMPTOMS
from cdss.organisms.pathogenicity import WOUND_SIGNS
from cdss.organisms.pathogenicity import WOUND_TYPES
from cdss.organisms.pathogenicity import assess_pathogenicity
from cdss.organisms.pathogenicity import gram_choice_in, gram_options_for
from cdss_ui.patho_view import _render_patho_result
from cdss_ui.resistance_panels import render_resistance_profile


def render_pathogenicity(page):
    """Pathogenicity assessment (urine and non-urine) and, for non-urine, the resistance panels."""
    # ── Pathogenicity Assessment Module v2 ───────────────────────────────
    # ⚠️ التعديل: Pathogenicity Assessment يظهر للبول فقط.
    #    لباقي المزارع يظهر بدلاً منه: Resistance Profile (ESBL / MDR / XDR / PDR).
    _is_urine_specimen = "urine" in page.culture_type.lower()

    # Clear stale patho_result when specimen changes
    if st.session_state.get("last_patho_specimen","") != page.culture_type:
        st.session_state.patho_result = None
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

                patho_collection = st.selectbox(
                    "طريقة جمع العينة",
                    URINE_COLLECTION_METHODS,
                    key="patho_coll_sel",
                    help="عتبة عدّ المستعمرات تختلف حسب طريقة الجمع: midstream / قسطرة "
                         "(≥10³ مع أعراض) / SPA (أي نمو) — IDSA 2009 و AAP."
                )
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

            if st.button("🔬 احسب Pathogenicity Score", use_container_width=True, key="patho_calc_btn"):
                # FIX 2026-11-11 (round 4): the engine read pregnancy only
                # from this multiselect, never from the sidebar flag, so a
                # pregnant patient's asymptomatic bacteriuria >= 10^5 came
                # back "do NOT treat" -- IDSA 2019 says treat it -- unless
                # "Pregnant" was ticked a second time here.
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
                    age=page.age,
                    sex=page.sex,
                    host_factors=patho_host,
                    collection_method=patho_collection,
                )
                patho_result = assess_pathogenicity(**patho_kwargs)
                st.session_state.patho_result = patho_result
                st.session_state.patho_pdf_ctx = {
                    "panel": "urine", "organism": page.organism_type, "specimen": page.culture_type,
                    "inputs": {
                        "Colony count": patho_kwargs.get("colony_count_text"),
                        "Collection method": patho_kwargs.get("collection_method"),
                        "Culture purity": patho_kwargs.get("culture_purity"),
                        "Pus cells / HPF": patho_kwargs.get("pus_cells_text"),
                        "Urinalysis": patho_kwargs.get("urinalysis_result"),
                        "Gram stain": patho_kwargs.get("gram_stain"),
                        "Symptoms": patho_kwargs.get("symptoms"),
                        "Host factors": patho_kwargs.get("host_factors"),
                        "Age / Sex": f"{patho_kwargs.get('age')} / {patho_kwargs.get('sex')}",
                    }}

            # ── Display Result (persists after button) ────────────────────
            patho_result = st.session_state.get("patho_result")
            if patho_result:
                _render_patho_result(patho_result)

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
                "csf":    "عينة من موقع معقم -- أي نمو مرضي بالضرورة",
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

                if _pcat == "blood":
                    np_sirs = st.multiselect(
                        "SIRS Criteria (≥2 = SIRS · ≥3 = sepsis probable)",
                        ["Temp > 38°C or < 36°C",
                         "Heart rate > 90 / min",
                         "Resp rate > 20 / min (or PaCO₂ < 32)",
                         "WBC > 12k or < 4k (or > 10% bands)"],
                        key="np_sirs_ms")
                    np_blood_source = st.selectbox(
                        "عدد الزجاجات الإيجابية",
                        ["مش محدد", "Single bottle positive",
                         "Multiple bottles positive"],
                        key="np_bsrc_sel")

                elif _pcat == "sputum":
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

                if st.button("🔬 احسب Pathogenicity Score",
                             use_container_width=True, key="np_calc_btn"):
                    st.session_state.patho_result = assess_pathogenicity(
                        specimen=page.culture_type,
                        organism=page.organism_type,
                        colony_count_text=page.colony_count,
                        culture_purity=np_purity,
                        symptoms=np_symptoms,
                        pus_cells_text="",
                        urinalysis_result="",
                        gram_stain=np_gram,
                        age=page.age, sex=page.sex,
                        host_factors=np_host,
                        sputum_pus_cells=np_sputum_wbc,
                        sputum_epithelial=np_sputum_epi,
                        sirs_criteria=np_sirs,
                        blood_source=np_blood_source,
                        wound_type=np_wound_type,
                    )
                    st.session_state.patho_pdf_ctx = {
                        "panel": "other", "organism": page.organism_type, "specimen": page.culture_type,
                        "inputs": {
                            "Colony count": page.colony_count, "Culture purity": np_purity,
                            "Gram stain": np_gram, "Signs / symptoms": np_symptoms,
                            "SIRS criteria": np_sirs, "Positive bottles": np_blood_source,
                            "Sputum WBC / LPF": np_sputum_wbc,
                            "Sputum epithelial / LPF": np_sputum_epi,
                            "Wound type": np_wound_type, "Host factors": np_host,
                            "Age / Sex": f"{page.age} / {page.sex}",
                        }}

                _npr = st.session_state.get("patho_result")
                if _npr:
                    _render_patho_result(_npr)

        render_resistance_profile(page)
