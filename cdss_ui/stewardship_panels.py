# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Right column: stewardship advisors.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.pipeline import duration_syndrome_key
from cdss.stewardship.combination import get_combination_therapy
from cdss.stewardship.deescalation import evaluate_deescalation
from cdss.stewardship.duration import annotate_regimen_note
from cdss.stewardship.duration import get_treatment_duration
from cdss.stewardship.hepatic import get_hepatic_recommendations
from cdss.stewardship.iv_po import evaluate_iv_po_switch
from cdss.stewardship.severity import suggest_severity


def render_stewardship(page):
    """Duration, combination therapy, IV-to-PO, hepatic dosing, de-escalation."""
    # Use syndrome_info directly
    # syndrome_info is already defined

    # ════════════════════════════════════════════════════════════
    # CLINICAL ENGINES UI -- v4.0
    # ════════════════════════════════════════════════════════════
    st.divider()

    # ── ① Treatment Duration ─────────────────────────────────
    with st.expander("⏱️ Treatment Duration", expanded=False):
        st.caption("Evidence-based duration -- IDSA AMR Guidance 2026 | Sanford 2025")

        # ── Auto-suggest severity from patient factors ─────────────
        _auto = suggest_severity(
            specimen=page.culture_type, age=page.age, sex=page.sex,
            is_preg=page.is_preg, is_renal=page.is_renal, cl_cr=page.cl_cr,
            host_factors=st.session_state.get("patho_host_factors", []),
            symptoms=st.session_state.get("patho_symptoms", []),
        )
        _suggested   = _auto["suggested"]
        _auto_reasons = _auto["reasons"]

        # Only auto-set on first load or when user hasn't overridden
        _sev_key = f"severity_manual_{page.culture_type}_{page.organism_type}"
        if not st.session_state.get(_sev_key):
            st.session_state.severity_level = _suggested

        # Show auto-suggestion chip
        _chip_color = {"mild": "#f39c12", "moderate": "#e67e22",
                       "severe": "#c0392b"}[_suggested]
        st.markdown(
            f"**🤖 Auto-suggested:** "
            f"<span style='background:{_chip_color};color:white;"
            f"padding:1px 8px;border-radius:8px;font-size:0.85em'>"
            f"{_suggested.upper()}</span> "
            f"<small style='color:gray'>-- {_auto_reasons[0] if _auto_reasons else ''}</small>",
            unsafe_allow_html=True,
        )

        _sev = st.selectbox(
            "Case Severity (يمكنك التعديل يدوياً)",
            ["mild", "moderate", "severe"],
            index=["mild","moderate","severe"].index(
                st.session_state.get("severity_level","moderate")),
            format_func=lambda x:{"mild":"🟡 Mild","moderate":"🟠 Moderate","severe":"🔴 Severe"}[x],
            key="sev_sel_ui")

        # Mark as manually overridden if changed
        if _sev != _suggested:
            st.session_state[_sev_key] = True
            if _sev != st.session_state.get("severity_level"):
                st.caption(f"ℹ️ تم تعديل الشدة يدوياً من {_suggested} -> {_sev}")
        else:
            st.session_state[_sev_key] = False

        st.session_state.severity_level = _sev
        _syn_lbl = duration_syndrome_key(page.syndrome_info, page._uti_syn_now, page.culture_type)
        _dur = get_treatment_duration(
            specimen=page.culture_type, organism=page.organism_type,
            syndrome=_syn_lbl, age=page.age, sex=page.sex,
            is_renal=page.is_renal, phenotypes=page.phenotypes, severity=_sev,
            is_cath=bool(getattr(getattr(page, "case", None), "is_cath", False)
                         and getattr(page.case, "is_urine", False)),
            primary=(getattr(page, "ranked", None) or [None])[0])
        _d1, _d2, _d3 = st.columns(3)
        _d1.metric("Standard", f"{_dur.get('standard_days',_dur.get('standard','?'))}d")
        _d2.metric("Range", f"{_dur.get('min_days','?')}–{_dur.get('max_days','?')}d")
        _d3.metric("IV / PO", f"IV:{_dur.get('iv_days',0)}d · PO:{_dur.get('po_days',0)}d")
        _dur_note = annotate_regimen_note(_dur.get('notes', ''), page.sir_map, lang="ar")
        if _dur_note:
            st.info(f"📋 {_dur_note}")
        if _dur.get("follow_up_culture"):
            st.warning("🔄 Follow-up culture recommended after treatment completion")
        st.caption(f"📚 {_dur.get('ref','')}")

    # ── ② Combination Therapy (auto if MDR phenotype) ────────
    # organism= restored 2026-08-21: without it, get_combination_therapy()'s
    # own intrinsic-resistance annotation block (`if organism and results:`)
    # never runs on THIS call site, even though run_analysis() passes it
    # correctly. Same defect class as the 2026-08-06 fix documented inside
    # that function -- a Colistin+Meropenem option could render for
    # Proteus/Providencia/Morganella/Serratia (intrinsically colistin-
    # resistant) with no annotation, on the exact screen a clinician reads.
    # test_pipeline.py never caught it because it exercises run_analysis()
    # directly, not this inline UI call -- see test_ui_combination_path.py.
    _combos = get_combination_therapy(
        page.phenotypes,
        is_pregnant=page.is_preg, age_years=page.age, age_months=page.age_months,
        is_renal=page.is_renal, cl_cr=page.cl_cr, is_hepatic=page.is_hepatic,
        organism=page.organism_type,
        carbapenemase_type=st.session_state.get("carb_type_now"),
    )
    if _combos:
        with st.expander(f"🔬 Combination Therapy ({len(_combos)} phenotype)", expanded=True):
            st.caption("MDR/XDR combination therapy -- IDSA AMR Guidance 2026")
            for _cs in _combos:
                _pd = _cs["data"]
                _urg = _pd["urgency"]
                (st.error if _urg=="CRITICAL" else st.warning)(f"**{_urg}** -- {_pd['title']}")
                for _op in _pd["options"]:
                    _avoid = "AVOID" in _op.get("evidence","") or "AVOID" in _op["combo"].upper()
                    if _avoid:
                        st.error(f"🚫 **{_op['combo']}** | {_op.get('caution','')}")
                    else:
                        with st.container(border=True):
                            _ca, _cb = st.columns([3,1])
                            with _ca:
                                _hf = "  ⚠️" if _op.get("host_flagged") else ""
                                st.markdown(f"**{_op['combo']}** -- {_op['evidence']}{_hf}")
                                st.caption(_op["indication"])
                                # A host contraindication is an error,
                                # not a caption: these are the only
                                # agents in the app that reach the
                                # screen without passing the safety
                                # gate, so the warning has to carry the
                                # weight the gate would have.
                                if _op.get("host_flagged"):
                                    st.error(_op.get("caution",""))
                                elif _op.get("caution"):
                                    st.warning(_op["caution"])
                            with _cb:
                                st.caption(_op["ref"])

    # ── ③ IV -> PO Switch ──────────────────────────────────────
    with st.expander("💊 IV -> PO Switch Evaluation", expanded=False):
        st.caption("OPAT switch criteria -- IDSA 2019 | BNF 2025")
        _sw1, _sw2 = st.columns(2)
        with _sw1:
            _sw_drug = st.selectbox("Current IV drug",
                [""] + [d["name"] for d in page.allowed], key="sw_drug_sel")
            _sw_days = st.number_input("Days on IV", min_value=0, max_value=30,
                value=st.session_state.get("days_on_iv",3), key="sw_days_num")
            st.session_state.days_on_iv = _sw_days
        with _sw2:
            _sw_i = st.checkbox("Clinical improvement documented",
                value=st.session_state.get("clinical_improving_48h",True), key="sw_i_chk")
            _sw_o = st.checkbox("Tolerating oral medications",
                value=st.session_state.get("tolerating_oral",True), key="sw_o_chk")
            _sw_b = st.checkbox("No active bacteremia",
                value=st.session_state.get("bacteremia_resolved",True), key="sw_b_chk")
            st.session_state.clinical_improving_48h = _sw_i
            st.session_state.tolerating_oral        = _sw_o
            st.session_state.bacteremia_resolved    = _sw_b
        if _sw_drug:
            _swr = evaluate_iv_po_switch(
                drug_name=_sw_drug,
                syndrome=page.syndrome_info["syndrome"] if page.syndrome_info else "",
                clinical_improving=_sw_i, tolerating_oral=_sw_o,
                bacteremia_resolved=_sw_b, days_on_iv=_sw_days,
                organism=page.organism_type)
            (st.success if _swr["can_switch"] else st.warning)(_swr["verdict"])
            _sc1, _sc2 = st.columns(2)
            with _sc1:
                st.markdown("**✅ Supporting factors:**")
                for _s in _swr["supporters"]: st.write(f"• {_s}")
            with _sc2:
                st.markdown("**⚠️ Blocking factors:**")
                for _b in _swr["blockers"]: st.write(f"• {_b}")
            st.caption(f"📚 {_swr['ref']}")
        else:
            st.info("Select the current IV drug to evaluate switch criteria")

    # ── ④ Hepatic Dosing -- Child-Pugh ─────────────────────────
    if page.is_hepatic:
        with st.expander("🟡 Hepatic Dosing -- Child-Pugh", expanded=True):
            st.caption("Dose adjustments in hepatic impairment -- BNF 2025 | Lexicomp 2025")
            # The grade is read, not asked for again. A second selectbox
            # writing the same session key from below the analysis call is
            # the stale-state race that made this panel and the engine
            # disagree on the same screen: the panel showed grade A advice
            # while the engine had already banned on grade C, or the
            # reverse. One widget, in the sidebar, before the analysis.
            _cp = st.session_state.get("child_pugh_class", "C")
            st.info(f"Evaluated as **Child-Pugh {_cp}** — change it in the "
                    f"sidebar, next to the Hepatic Impairment flag.")
            _hr = get_hepatic_recommendations(page.allowed, _cp)
            _act = [r for r in _hr if r["requires_action"]]
            _nrm = [r for r in _hr if not r["requires_action"]]
            if _act:
                st.markdown("**⚠️ Adjustments required:**")
                for _r in _act:
                    (st.error if "Avoid" in _r["level"] else st.warning)(
                        f"{'❌' if 'Avoid' in _r['level'] else '⚠️'} "
                        f"**{_r['name']}**: {_r['recommendation']} -- _{_r['note']}_")
            if _nrm:
                with st.expander(f"✅ {len(_nrm)} drugs: no hepatic adjustment needed"):
                    for _r in _nrm: st.caption(f"✅ {_r['name']}: {_r['recommendation']}")
            if not _hr:
                st.success("✅ No hepatic dose adjustments needed for current recommendations")
            st.caption("📚 BNF 2025 | Lexicomp 2025 | UpToDate 2025")

    # ── ⑤ De-escalation Advisor ───────────────────────────────
    with st.expander("📉 De-escalation Advisor", expanded=False):
        st.caption("Antibiotic stewardship -- WHO AWaRe 2025 | IDSA Stewardship 2025")
        _de1, _de2 = st.columns(2)
        with _de1:
            _de_h = st.number_input("Hours on current therapy",
                min_value=0, max_value=336, step=12,
                value=st.session_state.get("hours_on_treatment",72), key="de_h_num")
            st.session_state.hours_on_treatment = _de_h
        with _de2:
            _de_i = st.checkbox("Clinical improvement documented",
                value=st.session_state.get("de_clinical_improving",True), key="de_i_chk")
            st.session_state.de_clinical_improving = _de_i
        _der = evaluate_deescalation(
            allowed=page.allowed, phenotypes=page.phenotypes,
            hours_on_treatment=_de_h, clinical_improving=_de_i,
            mdr_level=(page.mdr_result or {}).get("level"))
        if _der["can_deescalate"]: st.success("✅ De-escalation recommended")
        elif _de_h < 48: st.info("ℹ️ Complete 48h course before reassessment")
        else: st.warning("⚠️ Review required before de-escalation")
        for _rec in _der["recommendations"]: st.write(_rec)
        st.caption(f"📚 {_der['ref']}")

    st.divider()
