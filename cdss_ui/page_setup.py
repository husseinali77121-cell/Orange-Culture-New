# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Page chrome: config, CSS, health banner, title, lab identity.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import os
import streamlit as st

from cdss.common.optional_deps import ARABIC_SUPPORT
from cdss.health import AST_QA_AVAILABLE
from cdss.health import AST_RULES_MODULES_AVAILABLE
from cdss.health import INTRINSIC_TABLE_OK
from cdss.health import MATRIX_VERSION
from cdss.health import PANEL_COMPLETENESS_AVAILABLE
from cdss.health import SAFETY_GATE_AVAILABLE
from cdss_ui.startup import get_startup_validation_issues


def configure_page(page):
    """Page config and the global CSS."""
    # =========================================================
    # ملاحظة: Ampicillin, Amoxicillin, Tetracycline, Cephradine
    # منقولة بالكامل إلى abx_guidelines.py
    # لا توجد بيانات مضادات حيوية في هذا الملف -- كل البيانات في abx_guidelines.py
    # =========================================================

    # =========================================================
    # إعداد الصفحة
    # =========================================================
    st.set_page_config(
        page_title="Microbiology CDSS",
        layout="wide",
        page_icon="🔬"
    )

    st.markdown("""
<style>
    .stActionButton {display: none !important;}
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header[data-testid="stHeader"] {display: none !important;}
    .app-card {
        padding: 1rem 1.2rem;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        background: rgba(255,255,255,0.02);
        margin-bottom: 1rem;
    }
    .muted-text { color: #9aa0a6; font-size: 0.92rem; }
    .orange-badge {
        display:inline-block; background:#ff8c00; color:white;
        padding:0.25rem 0.7rem; border-radius:999px;
        font-size:0.8rem; font-weight:600;
    }
</style>
""", unsafe_allow_html=True)


def render_health_and_title(page):
    """Module-health banner, start-up validation, title."""
    # ── Module health, shown before anything else ────────────────────────────────
    #  A missing clinical_data.py silently disables intrinsic-resistance filtering:
    #  inactive agents stop being routed to Avoid and stop being stripped before MDR
    #  counting. That is a degraded clinical mode, and it used to be reported only
    #  inside a COLLAPSED expander among ordinary data notes -- so the app could run
    #  for months giving weaker advice with nobody noticing. Anything that changes
    #  what the engine is capable of is now surfaced at the top, unmissable.
    _MODULE_HEALTH = [
        ("clinical_data.py  (intrinsic resistance table)", INTRINSIC_TABLE_OK, True),
        (f"safety_gate + clinical_matrix  (site/host safety map v{MATRIX_VERSION})",
         SAFETY_GATE_AVAILABLE, True),
        ("ast_reportability + ast_consistency  (QC panel)", AST_RULES_MODULES_AVAILABLE, False),
        ("ast_qa_engine.py  (AST quality check)", AST_QA_AVAILABLE, False),
        ("ast_panel_completeness.py  (Panel Completeness card)", PANEL_COMPLETENESS_AVAILABLE, False),
        ("Arabic shaping  (arabic-reshaper + python-bidi)", ARABIC_SUPPORT, False),
    ]
    _degraded = [(n, crit) for n, ok, crit in _MODULE_HEALTH if not ok]
    if any(crit for _, crit in _degraded):
        st.error(
            "🛑 **DEGRADED CLINICAL MODE — do not use for reporting.**  \n"
            + "  \n".join(f"❌ `{n}` is missing." for n, crit in _degraded if crit)
            + "  \n\nIntrinsically inactive antibiotics will NOT be filtered out of the "
              "recommendations and will NOT be excluded from MDR counting. "
              "Upload the missing file to its folder, then **Manage app → Reboot app**."
        )
    elif _degraded:
        st.warning("⚠️ Optional modules unavailable: "
                   + ", ".join(f"`{n}`" for n, _ in _degraded)
                   + ". Core recommendations are unaffected. "
                   "After uploading the missing file: **Manage app → Reboot app**.")

    # v7.8: a rule base that contradicts itself stops every report (V16) --
    # shown here, at the top, not only inside each case's validation
    try:
        from cdss.validation.case_validator import rule_base_integrity
        _rb = rule_base_integrity()
    except Exception as _exc:                       # the validator itself fails closed too
        _rb = [{"message": f"rule-base check failed to run: {_exc}"}]
    if _rb:
        st.error("🛑 **قواعد البرنامج متعارضة مع بعضها — كل التقارير موقوفة لحد ما تتصلح:**  \n"
                 + "  \n".join(f"• {v['message']}" for v in _rb[:8]))

    startup_issues = get_startup_validation_issues()
    if startup_issues:
        with st.expander(f"🧪 Data validation at startup ({len(startup_issues)})",
                         expanded=False):
            for issue in startup_issues:
                st.write(f"- {issue}")

    with st.expander("🧩 Module health", expanded=False):
        for _n, _ok, _crit in _MODULE_HEALTH:
            st.write(f"{'✅' if _ok else ('❌' if _crit else '⚠️')} {_n}")

    st.title("🔬 Microbiology CDSS")
    st.caption("AI-Assisted Antibiotic Decision Support -- Egyptian Market Edition")

    if os.environ.get("ORANGE_CDSS_OFFLINE_MODE") == "1":
        # Set by launcher.py only when actually running as the frozen desktop
        # exe (never in the cloud-deployed version) -- reassurance that this
        # build works with no internet connection, not a claim about what the
        # cloud-deployed version does.
        st.caption(
            "🟢 **Offline** — Clinical Engine: Local · AST QC: Local · "
            "OCR: Local · Guidelines: Local copy — no internet connection required"
        )


def render_lab_identity(page):
    """Lab name / city (from secrets or typed)."""
    # ── إعدادات المعمل -- قابلة للتغيير (النسخة التجارية) ─────────────────────
    # الأولوية: secrets (للنشر) -> session_state (تغيير مباشر) -> default
    #
    # 2026-08-22: hasattr(st, "secrets") only proves the ATTRIBUTE exists -- it
    # is always True, since `secrets` is a normal attribute of the streamlit
    # module regardless of whether a secrets.toml file is present anywhere.
    # Accessing it (even via .get()) is what can fail: if NO secrets.toml exists
    # at all (not even an empty one -- exactly the case in CI, where none is
    # ever committed), Streamlit raises StreamlitSecretNotFoundError. That is
    # not a KeyError, so .get()'s own internal exception handling does not catch
    # it -- every OTHER st.secrets call site in this file already wraps the
    # access in `try/except Exception`; this was the one bare call left, and it
    # crashed app startup the moment real streamlit (installed for the Windows
    # EXE build's test step) actually tried to import this file with no
    # secrets.toml deployed.
    try:
        _lab_from_secrets = bool(st.secrets.get("lab_name", ""))
    except Exception:
        _lab_from_secrets = False

    if _lab_from_secrets:
        # Deployed lab: name fixed via Streamlit secrets (no UI override needed)
        st.session_state.lab_name = st.secrets.get("lab_name", "Your Lab Name")
        st.session_state.lab_city = st.secrets.get("lab_city", "")
    else:
        # Commercial / demo mode: allow UI-based name change
        with st.expander("🏥 إعدادات المعمل", expanded=False):
            _c1, _c2 = st.columns([3, 2])
            with _c1:
                _lab_input = st.text_input(
                    "اسم المعمل",
                    value=st.session_state.get("lab_name", "Your Lab Name"),
                    placeholder="مثال: Nile Diagnostic Center",
                    key="lab_name_input_commercial",
                )
                if _lab_input.strip():
                    st.session_state.lab_name = _lab_input.strip()
            with _c2:
                _city_input = st.text_input(
                    "المدينة / العنوان (اختياري)",
                    value=st.session_state.get("lab_city", ""),
                    placeholder="مثال: Cairo",
                    key="lab_city_input_commercial",
                )
                st.session_state.lab_city = _city_input.strip()
            # Live preview
            _prev = st.session_state.lab_name
            if st.session_state.lab_city:
                _prev += f"  |  {st.session_state.lab_city}"
            st.caption(f"🔬 **معاينة الترويسة:** {_prev}")
            st.caption("ℹ️ هذا الاسم سيظهر في الصورة وتقرير PDF والتقرير النصي تلقائياً.")
