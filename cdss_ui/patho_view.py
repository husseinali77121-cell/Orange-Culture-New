# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""On-screen rendering of the pathogenicity result."""
from datetime import datetime
import streamlit as st

from cdss.common.optional_deps import (
    WEASYPRINT_AVAILABLE,
)
from cdss.reports.patho_pdf import (
    generate_patho_report_pdf,
)


# =========================================================
# عرض نتيجة الـ Pathogenicity (مشترك بين البول وغير البول)
# =========================================================
def _render_patho_result(patho_result: dict) -> None:
    """Render a pathogenicity assessment result (score, verdict, factors, recs).
    Shared by the urine and non-urine pathogenicity panels (engine v3)."""
    sc    = patho_result["score"]
    color = patho_result["color"]
    flags = patho_result.get("special_flags", [])

    st.markdown(f"### Pathogenicity Score: **{sc}%**")
    st.progress(sc / 100)

    if color == "error":
        st.error(patho_result["verdict"])
    elif color == "warning":
        st.warning(patho_result["verdict"])
    else:
        st.success(patho_result["verdict"])

    _conf = patho_result.get("confidence")
    if _conf:
        _conf_ar = {"high": "عالية", "moderate": "متوسطة", "low": "منخفضة"}.get(_conf, _conf)
        st.caption(f"ثقة التقييم: **{_conf_ar}** · Engine v{patho_result.get('engine_version', '')}")
    if patho_result.get("threshold"):
        st.caption(f"📏 العتبة المطبّقة: {patho_result['threshold']}")
    if patho_result.get("missing_inputs"):
        st.warning("بيانات غير مُدخلة (لم تُحتسب ضد العدوى): "
                   + "، ".join(patho_result["missing_inputs"]))

    # Special-flag badges (specimen-specific)
    if patho_result.get("abu_detected"):
        st.info("🔵 **Asymptomatic Bacteriuria (ABU) Detected** -- راجع IDSA 2019")
    if "PEDIATRIC_UTI" in flags:
        st.info("👶 **Pediatric threshold applied** (Age < 2 yrs -- AAP: pyuria + ≥ 5×10⁴ CFU/mL; "
                "any count only for suprapubic aspirate)")
    if "SCI" in flags:
        st.info("♿ **Spinal cord injury context applied** -- neurogenic bladder / pressure ulcer / "
                "impaired cough rules")
    if "UNSPECIATED_ORGANISM" in flags:
        st.info("🔬 **Organism not identified to species level** -- التقييم على مستوى الجنس/الصبغة")
    if "GRAM_VARIABLE" in flags:
        st.info("🔬 **Gram-variable stain** -- راجع الملاحظة أسفل")
    if "GRAM_DISCORDANT" in flags:
        st.warning("🔬 **Gram stain / culture discordance** -- الصبغة لا تطابق العزلة")
    if "MW_REJECT" in flags:
        st.warning("🧪 **Specimen quality: REJECT** -- Murray-Washington (saliva contamination). أعِد العينة.")
    if "MW_ADEQUATE" in flags:
        st.success("🧪 **Specimen quality: Adequate** -- Murray-Washington (WBC≥25, Epi<10/LPF).")
    if "SIRS_HIGH" in flags:
        st.error("🌡️ **SIRS ≥3 criteria -- Sepsis probable**")
    if "CSF_ALWAYS_SIGNIFICANT" in flags:
        st.error("🧠 **Sterile site (CSF) -- growth of this organism is clinically significant**")
    if "CSF_SKIN_FLORA" in flags:
        st.warning("🧠 **CSF skin flora without a device** -- possible contaminant; correlate with CSF cells")
    if "GI_TRUE_PATHOGEN" in flags:
        st.error("🦠 **Enteric pathogen -- always significant**")
    if "BLOOD_CONTAMINANT_RISK" in flags and "MULTI_SET_SKIN_FLORA" not in flags:
        st.warning("🩸 **Possible blood-culture contaminant (CoNS / skin flora)** -- يتطلب نفس الكائن في ≥2 sets.")
    if "BLOOD_PENDING_ID" in flags:
        st.warning("🩸 **Identification pending** -- لا تعتبره ملوِّثاً قبل نفي S. aureus.")

    st.info(patho_result["interpretation"])

    col_pos, col_neg = st.columns(2)
    with col_pos:
        if patho_result["factors_pos"]:
            st.markdown("**✅ Supporting Factors**")
            for f in patho_result["factors_pos"]:
                st.write(f)
    with col_neg:
        if patho_result["factors_neg"]:
            st.markdown("**⚠️ Against Infection**")
            for f in patho_result["factors_neg"]:
                st.write(f)

    if patho_result.get("notes"):
        st.markdown("**🧭 ملاحظات تفسيرية:**")
        for _n in patho_result["notes"]:
            st.write(_n)

    st.markdown("**📋 التوصيات:**")
    for rec in patho_result["recommendations"]:
        st.write(f"• {rec}")

    if patho_result.get("references"):
        st.caption("المراجع: " + " · ".join(patho_result["references"]))

    # ── PDF of this assessment only (2026-11-11) ───────────────────────────
    st.divider()
    _ctx = st.session_state.get("patho_pdf_ctx") or {}
    _pl = st.radio("لغة ملف الـ PDF", ["العربية", "English"], horizontal=True,
                   key=f"patho_pdf_lang_{_ctx.get('panel', 'x')}")
    if WEASYPRINT_AVAILABLE:
        _pp = generate_patho_report_pdf(
            patho_result, _ctx.get("organism", ""), _ctx.get("specimen", ""),
            inputs=_ctx.get("inputs"),
            patient_ref=(st.session_state.get("patient_name_final", "")
                         or st.session_state.get("patient_name_ocr", "") or ""),
            lang="en" if _pl == "English" else "ar")
        if _pp:
            st.download_button(
                "⬇️ Download Pathogenicity Assessment (PDF)", data=_pp,
                file_name=f"Pathogenicity-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf",
                mime="application/pdf", key=f"patho_pdf_dl_{_ctx.get('panel', 'x')}")
        else:
            st.caption("⚠️ تعذر إنشاء PDF لتقييم الـ Pathogenicity.")
    else:
        st.caption("⚠️ WeasyPrint غير متاح في هذه البيئة — لا يمكن إنشاء PDF.")
