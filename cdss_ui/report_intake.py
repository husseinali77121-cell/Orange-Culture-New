# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Uploaded image -> OCR payload.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.ocr.ocr_parsing import ocr_name_warnings

from cdss.common.util import make_file_hash
from cdss.ocr.extract import extract_all_data_cached
from cdss_ui.state import reset_patient_state


def load_report(page):
    """Read the uploaded image once (OCR), keep the payload, show the preview."""
    file_bytes = page.uploaded.getvalue()
    page.file_hash  = make_file_hash(file_bytes)
    is_new     = (st.session_state.ocr_data is None or
                  st.session_state.last_file_hash != page.file_hash)

    if is_new:
        # Clean up old session keys when loading a new image
        old_hash = st.session_state.get("last_file_hash", "")
        if old_hash and old_hash != page.file_hash:
            keys_to_delete = [k for k in st.session_state if old_hash[:8] in str(k)]
            for key in keys_to_delete:
                del st.session_state[key]
            # A different report = a different patient (round 4, 2026-11-11).
            reset_patient_state()

        with st.spinner("🔍 جاري تحليل صورة التقرير..."):
            try:
                page.payload = extract_all_data_cached(file_bytes)
                st.session_state.ocr_data           = page.payload
                st.session_state.last_file_hash     = page.file_hash
                st.session_state.sir_map_edited     = dict(page.payload["sir_map"])
                # الاسم يُدخل يدوياً -- لا نغير ما أدخله المستخدم عند تحميل صورة جديدة
                st.session_state.patient_name_ocr   = ""
                # patient_name_final محفوظ من الجلسة السابقة (لا نمسحه)
            except Exception as e:
                st.error(f"تعذر تحليل الصورة: {e}")
                st.stop()

    page.payload        = st.session_state.ocr_data
    page.patient        = page.payload["patient"]
    page.drugs_from_ocr = page.payload["drugs"]
    raw_text       = page.payload["raw_text"]

    if not st.session_state.sir_map_edited and page.payload["sir_map"]:
        st.session_state.sir_map_edited = dict(page.payload["sir_map"])

    st.image(file_bytes, caption="Preview", use_container_width=True)
    # v7.0: misnamed drugs in the laboratory template (e.g. "Sulphamethazone")
    for _nw in (page.payload.get("name_warnings")
                or ocr_name_warnings(raw_text or "")):
        st.warning(f"✏️ {_nw}")

    with st.expander("📝 النص المستخرج من التقرير (OCR)", expanded=False):
        st.text_area("Extracted Text", raw_text, height=220, label_visibility="collapsed")
