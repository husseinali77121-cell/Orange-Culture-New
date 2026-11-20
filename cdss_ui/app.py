# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""The Streamlit page: main() wires the sections together, top to bottom.

Nothing clinical is decided here -- the sections collect inputs, call
cdss.pipeline.run_analysis() and render what it returns.
"""
from types import SimpleNamespace
import streamlit as st
import time

from cdss_ui.analysis import run_case_analysis
from cdss_ui.auth import check_subscription
from cdss_ui.auth import refresh_secrets
from cdss_ui.auth import handle_session_timeout
from cdss_ui.auth import render_top_bar
from cdss_ui.auth import show_login_page
from cdss_ui.inputs import render_lab_fields
from cdss_ui.inputs import render_microscopy
from cdss_ui.inputs import render_patient
from cdss_ui.inputs import render_specimen_and_organism
from cdss_ui.page_setup import configure_page
from cdss_ui.page_setup import render_health_and_title
from cdss_ui.page_setup import render_lab_identity
from cdss_ui.panel_editor import render_aux_tests
from cdss_ui.panel_editor import render_ocr_review
from cdss_ui.panel_editor import render_panel_editor
from cdss_ui.pathogenicity_panel import render_pathogenicity
from cdss_ui.resistance_panels import render_ast_quality_check
from cdss_ui.recommendations import render_recommendations
from cdss_ui.report_intake import load_report
from cdss_ui.release import prepare_release
from cdss_ui.report_panels import prepare_report_inputs
from cdss_ui.report_panels import render_final_checklist
from cdss_ui.report_panels import render_pdf_export
from cdss_ui.report_panels import render_summary_image
from cdss_ui.report_panels import render_text_report
from cdss_ui.resistance_panels import render_ast_qc
from cdss_ui.resistance_panels import render_resistance
from cdss_ui.state import init_session_state
from cdss_ui.stewardship_panels import render_stewardship


def main():
    page = SimpleNamespace()    # per-run state shared between the sections
    configure_page(page)

    init_session_state()
    refresh_secrets()







    # =========================================================
    # واجهة التطبيق الرئيسية
    # =========================================================
    if not st.session_state.authenticated:
        _login = show_login_page()
        if _login:
            email_input, password_input = _login
            if check_subscription(email_input, password_input):
                st.session_state.authenticated = True
                st.session_state.last_activity = time.time()
                st.rerun()
        st.stop()

    handle_session_timeout()
    render_top_bar()

    render_health_and_title(page)

    render_lab_identity(page)



    page.uploaded = st.file_uploader(
        "📷 Upload Culture Report Image",
        type=["jpg", "jpeg", "png"]
    )

    if page.uploaded:
        load_report(page)

        col1, col2 = st.columns([1.05, 1.55], gap="large")

        # ─── العمود الأيسر ────────────────────────────────────────────────────────
        with col1:
            render_specimen_and_organism(page)

            render_microscopy(page)

            render_patient(page)

            render_lab_fields(page)

            render_pathogenicity(page)

            # The QA engine (cross-resistance, D-test, MRSA / ESBL consistency) used
            # to sit inside the NON-urine branch above, so a urine culture -- the
            # commonest specimen -- never got it. It is specimen-independent.
            render_ast_quality_check(page)


        # ─── العمود الأيمن ────────────────────────────────────────────────────────
        with col2:
            st.subheader("💊 Antibiotic Analysis")

            render_panel_editor(page)

            render_ocr_review(page)

            render_aux_tests(page)

            run_case_analysis(page)

            render_resistance(page)

            render_ast_qc(page)

            render_recommendations(page)

            # ── التقرير والصورة ──────────────────────────────────────────────────
            if page.final_drugs:
                prepare_report_inputs(page)

                render_stewardship(page)

                # v7.6: every export is built and validated BEFORE the first
                # download button can appear (one release decision for all).
                prepare_release(page)

                render_final_checklist(page)

                render_text_report(page)

                render_pdf_export(page)

                render_summary_image(page)

    st.divider()
    st.markdown("""
<div style="text-align:center;color:gray;font-size:0.9rem;">
  <strong>Developed by Dr / Hussein Ali | Orange Lab</strong><br>
  CLSI M100 Ed36 | IDSA AMR Guidance 2026 | EUCAST Expected Resistant Phenotypes | BNF 2025 | Egypt National Guidelines
</div>
""", unsafe_allow_html=True)
