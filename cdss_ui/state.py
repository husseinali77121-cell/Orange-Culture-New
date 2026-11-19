# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Streamlit session-state initialisation and per-patient reset."""
from datetime import date
import streamlit as st




# =========================================================
# Session State
# =========================================================
def init_session_state() -> None:
    defaults = {
        "authenticated":      False,
        "email":              "",
        "days_left":          None,
        "last_activity":      None,
        "logout_reason":      "",
        "ocr_data":           None,
        "last_file_hash":     "",
        "sir_map_edited":     {},
        "patient_name_ocr":   "",
        "patient_name_final": "",
        # ─── حقول المزرعة الجديدة ─────────────────────────────────────────
        "colony_count":       "≥ 10^5 CFU/mL",
        "date_in":            date.today(),
        "pus_cells_text":     "",
        "rbcs_text":          "",
        # اسم المعمل -- قابل للتعديل من الـ sidebar
        "lab_name":           "Your Lab Name",
        "lab_city":           "",
        # ─── Commercial Names ─────────────────────────────────────────────
        "show_commercial_names": False,
        # ─── Pathogenicity Assessment ─────────────────────────────────────
        "patho_culture_purity":   "Pure growth",
        "patho_symptoms":         [],
        "patho_urinalysis":       "مش معروف / مش مذكور",
        "patho_gram_stain":       "مش متعملة",
        "patho_host_factors":     [],
        "patho_collection":       "",
        "patho_sputum_pus":       "",
        "patho_sputum_epi":       "",
        "patho_sirs":             [],
        "patho_blood_source":     "",
        "patho_wound_type":       "",
        "patho_result":           None,
        # ─── Clinical Engines v4 ──────────────────────────────────────────
        "severity_level":          "moderate",  # overwritten by auto-suggest
        "last_patho_specimen":     "",   # tracks specimen that generated patho_result
        # Seeded to "C", not "A". analyze_antibiotics() documents that it
        # fail-closes to the worst grade when the caller does not know it, but
        # this seed was the caller, and it asserted the mildest grade. Because
        # the Child-Pugh selectbox renders BELOW the analysis call in script
        # order, the first run after ticking "Hepatic Impairment" always
        # evaluated as Child-Pugh A -- which is 0 hepatic bans instead of 7
        # (Amox-Clav/DILI, Azithromycin, Clarithromycin, Metronidazole, TMP-SMX,
        # Nitrofurantoin, Doxycycline). clinical_matrix also downgrades its
        # hepatic DENY to CAUTION on grade A, so both layers failed together and
        # there was no independent backstop. The grade is now asked for in the
        # sidebar, next to the flag, before anything is evaluated.
        "child_pugh_class":        "C",
        "days_on_iv":              3,
        "clinical_improving_48h":  True,
        "tolerating_oral":         True,
        "bacteremia_resolved":     True,
        "hours_on_treatment":      72,
        "de_clinical_improving":   True,
        # ─── PDF Report Options ───────────────────────────────────────────
        "pdf_include_combo":       True,
        "pdf_include_duration":    True,
        "pdf_include_patho":       True,
        # ─── New image/report fields ──────────────────────────────────────
        "referring_physician":     "",
        "culture_condition":       "Aerobic",
        "microbiologist":          "",
        # ─── Cached Computations (prevent regeneration on every widget) ────
        "_img_bytes":              None,
        "_img_hash":               "",
        "_img_error":              False,
        "_rpt_text":               "",
        "_rpt_hash":               "",
        "_pdf_bytes":              None,
        "_pdf_hash":               "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ── A new report is a new patient ───────────────────────────────────────────
# FIX 2026-11-11 (round 4). Uploading the next report reset only the S/I/R
# panel. Everything else the clinician had entered for the PREVIOUS patient
# stayed live and flowed into the new patient's analysis and report: the
# pregnancy, renal and hepatic flags, the creatinine, current medications,
# drug allergies, the carbapenemase class, the UTI syndrome, the colony count,
# pus cells and RBCs (whose OCR auto-fill then refused to overwrite them), the
# patient's name, and -- when the specimen type matched -- the previous
# pathogenicity verdict, printed in the new report. Widgets that hold patient
# facts are either keyed per file (and so recreated) or listed here and reset.
_PATIENT_WIDGET_KEYS = (
    "colony_count_input", "date_in_input", "pus_cells_input", "rbcs_input",
    "ref_phys_input", "culture_cond_sel",
    "patho_purity_sel", "patho_gram_sel", "patho_ua_sel", "patho_coll_sel",
    "patho_symp_urine", "patho_host_sel",
    "np_purity_sel", "np_gram_sel", "np_sirs_ms", "np_bsrc_sel", "np_spwbc",
    "np_spepi", "np_symp_gi", "np_wtype_sel", "np_symp_wound", "np_symp_resp",
    "np_host_sel",
    "sev_sel_ui", "sw_drug_sel", "sw_days_num", "sw_i_chk", "sw_o_chk", "sw_b_chk",
    "de_h_num", "de_i_chk",
)

_PATIENT_STATE_KEYS = (
    "patient_name_ocr", "patient_name_final", "colony_count", "date_in",
    "pus_cells_text", "rbcs_text", "referring_physician", "culture_condition",
    "patho_culture_purity", "patho_symptoms", "patho_urinalysis", "patho_gram_stain",
    "patho_host_factors", "patho_collection", "patho_sputum_pus", "patho_sputum_epi", "patho_sirs",
    "patho_blood_source", "patho_wound_type", "patho_result", "patho_pdf_ctx",
    "last_patho_specimen", "severity_level", "child_pugh_class", "carb_type_now",
    "days_on_iv", "clinical_improving_48h", "tolerating_oral", "bacteremia_resolved",
    "hours_on_treatment", "de_clinical_improving",
    "_img_bytes", "_img_hash", "_img_error", "_rpt_text", "_rpt_hash",
    "_pdf_bytes", "_pdf_hash", "_pdf_lang_used",
)

def reset_patient_state() -> None:
    """Forget every patient-specific input before a different report is read."""
    for _k in _PATIENT_WIDGET_KEYS + _PATIENT_STATE_KEYS:
        st.session_state.pop(_k, None)
    for _k in [k for k in list(st.session_state.keys())
               if str(k).startswith("severity_manual_")]:
        st.session_state.pop(_k, None)
    init_session_state()          # re-seed the data keys with their defaults
