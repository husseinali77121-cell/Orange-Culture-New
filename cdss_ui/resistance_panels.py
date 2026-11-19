# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Resistance classification and AST quality panels (both columns).

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
from datetime import datetime
from typing import Dict
import streamlit as st

from cdss.astqc.confidence import compute_qa_confidence
from cdss.astqc.inline_qc import run_ast_qc
from cdss.common.optional_deps import WEASYPRINT_AVAILABLE
from cdss.health import AST_QA_AVAILABLE
from cdss.health import AST_RULES_MODULES_AVAILABLE
from cdss.health import PANEL_COMPLETENESS_AVAILABLE
from cdss.health import _check_panel_completeness_ext
from cdss.health import run_ast_qa_engine
from cdss.reports.qa_pdf import generate_qa_report_pdf
from cdss.resistance.mdr import MDR_INFO
from cdss.resistance.mdr import mdr_display_label
from cdss.resistance.mdr import classify_mdr
from cdss.resistance.mechanism import predict_esbl
from cdss.resistance.phenotypes import detect_resistance_phenotypes
from cdss.therapy.clsi_categories import canonical_panel
from cdss_ui.panel_editor import current_aux_tests


def render_resistance_profile(page):
    """Left column: MDR / mechanism / phenotype summary."""
    with st.expander("🧬 Resistance Profile (ESBL / MDR / Mechanisms)", expanded=True):
        st.caption(
            f"تحليل مقاومة الكائن **{page.organism_type}** في عينة **{page.culture_type}** -- "
            "تصنيف MDR/XDR/PDR + آليات المقاومة (ESBL / AmpC / Carbapenemase)"
        )

        # sir_map may not be defined yet at this render point — read from session_state
        _sir_map_now = canonical_panel(st.session_state.get("sir_map_edited") or {})
        _mdr_r  = classify_mdr(page.organism_type, _sir_map_now) if _sir_map_now else {"level": None}
        _esbl_r = predict_esbl(page.organism_type, _sir_map_now) if _sir_map_now else {"probability": None}
        _ph_r   = detect_resistance_phenotypes(page.organism_type, _sir_map_now) if _sir_map_now else []

        # ── MDR / XDR / PDR ────────────────────────────────────────────
        if _mdr_r.get("level"):
            _mi = MDR_INFO[_mdr_r["level"]]
            _rc = _mdr_r["resistant_count"]
            _rt = _mdr_r["total_tested"]
            _cats = ", ".join(_mdr_r["resistant_categories"])
            _gram = _mdr_r.get("gram", "")
            _msg = (f"{_mi['icon']} **{mdr_display_label(_mdr_r)}**  \n"
                    f"{_mi['detail']}  \n"
                    f"Resistant categories ({_rc}/{_rt}, Gram-{_gram}): {_cats}  \n"
                    f"🔹 {_mi['action']}")
            if _mdr_r["level"] == "MDR":
                st.warning(_msg)
            else:
                st.error(_msg)
            for _w in _mdr_r.get("warnings", []):
                st.caption(_w)
        else:
            if _sir_map_now:
                st.success("✅ لا يوجد تصنيف MDR/XDR/PDR -- الكائن حساس لمعظم الفئات.")
            else:
                st.info("ℹ️ أدخل نتائج المزرعة (S/I/R) لتحليل المقاومة.")

        # ── ESBL / AmpC / Carbapenemase ───────────────────────────────
        _prob = _esbl_r.get("probability")
        _conf = _esbl_r.get("confidence", 0)
        _mech = _esbl_r.get("mechanism", "")
        if _prob == "carbapenemase":
            st.error(
                f"🚨 **{_mech or 'Possible Carbapenemase (KPC/MBL/OXA)'}** "
                f"(confidence {_conf}%)  \n"
                f"{_esbl_r.get('detail','')}  \n🔹 {_esbl_r.get('action','')}"
            )
        elif _prob == "possible_carbapenemase":
            # Round 4 (2026-11-11): this tier, plasmid AmpC and CR-PA
            # were not rendered in this panel at all.
            st.warning(
                f"⚠️ **{_mech or 'Possible carbapenemase'}** (confidence {_conf}%)  \n"
                f"{_esbl_r.get('detail','')}  \n🔹 {_esbl_r.get('action','')}"
            )
        elif _prob in ("ampc", "ampc_plasmid"):
            st.error(
                f"⚠️ **{_mech if _prob == 'ampc_plasmid' else 'Possible AmpC β-Lactamase'}** "
                f"(confidence {_conf}%)  \n"
                f"{_esbl_r.get('detail','')}  \n🔹 {_esbl_r.get('action','')}"
            )
        elif _prob == "crpa":
            (st.error if _esbl_r.get("dtr") else st.warning)(
                f"{'🚨' if _esbl_r.get('dtr') else '⚠️'} **{_mech}** (confidence {_conf}%)  \n"
                f"{_esbl_r.get('detail','')}  \n🔹 {_esbl_r.get('action','')}"
            )
        elif _prob == "high":
            st.error(
                f"⚠️ **High Probability ESBL Producer** (confidence {_conf}%)  \n"
                f"{_esbl_r.get('detail','')}  \n🔹 {_esbl_r.get('action','')}"
            )
        elif _prob == "moderate":
            st.warning(
                f"🔶 **ESBL Confirmation Recommended** (confidence {_conf}%)  \n"
                f"{_esbl_r.get('detail','')}  \n🔹 {_esbl_r.get('action','')}"
            )

        # ── Resistance Phenotypes ─────────────────────────────────────
        if _ph_r:
            st.markdown("**🦠 Resistance Phenotypes Detected:**")
            for _ph in _ph_r:
                _iso = "  🚨 **عزل فوري مطلوب**" if _ph["isolation"] else ""
                _pmsg = (f"{_ph['icon']} **{_ph['label']}**{_iso}  \n"
                         f"{_ph['detail']}  \n"
                         f"🔹 {_ph['action']}")
                if _ph["isolation"]:
                    st.error(_pmsg)
                else:
                    st.warning(_pmsg)
                if _ph.get("matched_markers"):
                    st.caption(f"Evidence: {', '.join(_ph['matched_markers'])}")

        # ── Summary stats ──────────────────────────────────────────────
        if _sir_map_now:
            _s = sum(1 for v in _sir_map_now.values() if v == "S")
            _i = sum(1 for v in _sir_map_now.values() if v == "I")
            _r = sum(1 for v in _sir_map_now.values() if v == "R")
            _sc1, _sc2, _sc3, _sc4 = st.columns(4)
            _sc1.metric("Total Tested", len(_sir_map_now))
            _sc2.metric("Sensitive", _s)
            _sc3.metric("Intermediate", _i)
            _sc4.metric("Resistant", _r)


def render_ast_quality_check(page):
    """Left column: AST quality check (QA engine)."""
    # ── AST Quality Check (QC Engine) ────────────────────────────
    with st.expander("🔬 AST Quality Check -- فحص جودة نتائج الحساسية", expanded=True):
        st.caption(
            "فحص آلي لاتساق نتائج الـ AST: intrinsic resistance · phenotype "
            "consistency · cross-resistance · biological plausibility · QC rules"
        )
        _qc_sir = canonical_panel(st.session_state.get("sir_map_edited") or {})
        if not _qc_sir:
            st.info("أدخل نتائج S/I/R أولاً لتشغيل فحص الجودة.")
        else:
            # ── AST Quality Check (QC Engine) -- needs ast_qa_engine.py ──
            if not AST_QA_AVAILABLE:
                st.caption("⚠️ الملف `ast_qa_engine.py` غير موجود -- ارفعه بجانب "
                           "`streamlit_app.py` لتفعيل فحص الجودة.")
            else:
                _qc_mdr  = classify_mdr(page.organism_type, _qc_sir)
                _qc_esbl = predict_esbl(page.organism_type, _qc_sir)
                # De-duplication: the AST Quality CONTROL panel below runs
                # ast_reportability (intrinsic resistance / no-breakpoints)
                # and the specimen-appropriateness pass. Asking the QA
                # engine for the same two categories printed every one of
                # those findings twice on the same screen, so they are
                # suppressed here whenever the shared modules are loaded.
                _qa_skip = ({"Intrinsic Resistance", "Clinical Context"}
                            if AST_RULES_MODULES_AVAILABLE else set())
                # Already shown as its own card below (with
                # expected/tested/missing counts) -- don't also list
                # each missing drug a second time in this mixed
                # findings list.
                if PANEL_COMPLETENESS_AVAILABLE:
                    _qa_skip = _qa_skip | {"Panel Completeness"}
                _qc_issues = run_ast_qa_engine(
                    organism=page.organism_type, specimen=page.culture_type,
                    # a recorded D-test answers the QA engine's "D-test required" finding
                    sir_map={**_qc_sir, **current_aux_tests(page.file_hash)},
                    esbl_result=_qc_esbl, mdr_result=_qc_mdr,
                    skip_categories=_qa_skip,
                    sdd=getattr(page, "sdd_drugs", None),
                )
                if not _qc_issues:
                    st.success("✅ لا توجد تعارضات -- النتائج متسقة داخلياً "
                               "(لم يُكتشف خطأ منطقي في ملف الحساسية).")
                else:
                    _sev_counts: Dict[str, int] = {}
                    for _iss in _qc_issues:
                        _sev_counts[_iss.severity] = _sev_counts.get(_iss.severity, 0) + 1
                    _order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                    _summ = " · ".join(f"{k}: {_sev_counts[k]}"
                                       for k in _order if k in _sev_counts)
                    st.markdown(f"**تم اكتشاف {len(_qc_issues)} ملاحظة** -- {_summ}")
                    _sev_render = {"CRITICAL": st.error, "HIGH": st.warning,
                                   "MEDIUM": st.warning, "LOW": st.info}
                    _sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠",
                                 "MEDIUM": "🟡", "LOW": "🔵"}
                    for _iss in _qc_issues:
                        _render = _sev_render.get(_iss.severity, st.info)
                        _msg = (f"{_sev_icon.get(_iss.severity, '•')} "
                                f"**[{_iss.severity}] {_iss.category}**  \n{_iss.message}")
                        if _iss.drug:
                            _msg += f"  \n🧪 {_iss.drug}"
                        _render(_msg)
                        if _iss.detail:
                            st.caption(_iss.detail)
                        if _iss.reference:
                            st.caption(f"📖 {_iss.reference}")

            # ── AST Panel Completeness -- renders AFTER AST QA, ──
            # ── per request 2026-08-22 ───────────────────────────
            # Answers a different question from everything above:
            # "ينقص هذه المزرعة إيه من المضادات؟" -- what is this
            # specific culture's panel missing. Shown as its own
            # card, separate from the mixed findings list above (see
            # _qa_skip there): the same missing drug listed twice,
            # once here and once buried in that mixed list, is
            # noise, not thoroughness.
            #
            # Independent of AST_QA_AVAILABLE on purpose: this card
            # calls ast_panel_completeness.py directly, never through
            # run_ast_qa_engine(), so it has zero real dependency on
            # that module. It used to sit inside
            # `if AST_QA_AVAILABLE: ...` purely by accident of where
            # it got inserted -- an unrelated ast_qa_engine.py
            # problem could take it down with zero trace anywhere.
            # Visibility now depends on nothing but its OWN import
            # (PANEL_COMPLETENESS_AVAILABLE, tracked in Module Health
            # above) and having sir data -- checked independently of
            # whether the AST QA block above even ran.
            if PANEL_COMPLETENESS_AVAILABLE:
                _pc = _check_panel_completeness_ext(
                    page.organism_type, page.culture_type, _qc_sir
                )
                if _pc.status != "not_evaluated":
                    _pc_missing = _pc.missing_primary + _pc.missing_supplemental
                    st.divider()
                    st.markdown("**🧫 AST Panel Completeness**")
                    st.caption(f"الكائن: {_pc.organism_group}")
                    _c1, _c2, _c3 = st.columns(3)
                    _c1.metric("Expected", _pc.expected_total)
                    _c2.metric("Tested", _pc.tested_count)
                    _c3.metric("Missing", len(_pc_missing))
                    if not _pc_missing:
                        st.success("✅ Panel adequate -- كل المضادات "
                                   "المتوقعة لهذا الكائن تم اختبارها.")
                    else:
                        if _pc.status == "critical":
                            st.error(
                                "🔴 كل المضادات الأساسية اللي اتعملت كانت "
                                "Resistant، ومضادات أساسية متوقعة لسه معملتش "
                                "-- ممكن يكون فيه خيار علاجي في اللي ناقص. "
                                "متقولش 'مفيش خيارات' من لوحة ناقصة."
                            )
                        else:
                            st.warning(
                                f"⚠️ Panel incomplete -- "
                                f"{len(_pc_missing)} مضاد متوقع غير مُختبَر"
                            )
                        _pc_reflex = getattr(_pc, "reflex_missing", {}) or {}
                        if _pc_reflex:
                            st.error(
                                "🔴 **ناقص (حرج — نتيجة أخرى تستلزمه):** " +
                                " · ".join(f"{d} ({why})" for d, why in _pc_reflex.items())
                            )
                        if _pc.missing_primary:
                            st.markdown(
                                "**ناقص (أساسي):** " +
                                " · ".join(f"⚠️ {d}" for d in _pc.missing_primary
                                           if d not in _pc_reflex)
                            )
                        if _pc.missing_supplemental:
                            st.markdown(
                                "**ناقص (تكميلي/اختياري):** " +
                                " · ".join(f"🔵 {d}" for d in _pc.missing_supplemental)
                            )
                        if _pc.rule_id:
                            from cdss.guidelines.guideline_registry import citation_line as _pc_cite
                            _pc_ref = _pc_cite(_pc.rule_id)
                            if _pc_ref:
                                st.caption(f"📖 {_pc_ref} -- قيد مراجعة د. طارق")


def render_resistance(page):
    """Right column: resistance classification and phenotypes."""
    if page.mdr_result["level"] or (page.esbl_result.get("probability") and page.esbl_result["probability"] not in ("low", None)):
        with st.expander("🧬 Resistance Classification", expanded=True):

            # MDR/XDR/PDR
            if page.mdr_result["level"]:
                info = MDR_INFO[page.mdr_result["level"]]
                _rc  = page.mdr_result["resistant_count"]
                _rt  = page.mdr_result["total_tested"]
                _cats = ", ".join(page.mdr_result["resistant_categories"])
                _gram = page.mdr_result.get("gram", "")
                _msg = (f"{info['icon']} **{mdr_display_label(page.mdr_result)}**  \n"
                        f"{info['detail']}  \n"
                        f"Resistant categories ({_rc}/{_rt}, Gram-{_gram}): {_cats}  \n"
                        f"🔹 {info['action']}")
                if page.mdr_result["level"] == "MDR":
                    st.warning(_msg)
                else:
                    st.error(_msg)
                # Reliability warnings
                for _w in page.mdr_result.get("warnings", []):
                    st.caption(_w)

            # ESBL Predictor
            prob = page.esbl_result.get("probability")
            _conf = page.esbl_result.get("confidence", 0)
            _mech = page.esbl_result.get("mechanism", "")
            if prob == "carbapenemase":
                _em = (f"[!!] {_mech or 'Possible Carbapenemase (KPC/MBL/OXA)'} "
                       f"(confidence {_conf}%)\n"
                       + page.esbl_result["detail"] + "  \n🔹 " + page.esbl_result["action"])
                st.error(_em)
            elif prob == "possible_carbapenemase":
                # FIX 2026-11-11 (round 4): this tier (one carbapenem R, an
                # isolated ertapenem R, or meropenem I) opened this expander
                # and then printed nothing -- its mCIM / PCR instruction
                # never reached the screen.
                _em = (f"[!] {_mech or 'Possible carbapenemase'} (confidence {_conf}%)\n"
                       + page.esbl_result.get("detail", "") + "  \n🔹 " + page.esbl_result.get("action", ""))
                st.warning(_em)
            elif prob in ("ampc", "ampc_plasmid"):
                _em = (f"[!] Possible AmpC β-Lactamase (confidence {_conf}%)\n"
                       + page.esbl_result["detail"] + "  \n🔹 " + page.esbl_result["action"])
                st.error(_em)
            elif prob == "high":
                _em = (f"[!] High Probability ESBL Producer (confidence {_conf}%)\n"
                       + page.esbl_result["detail"] + "  \n🔹 " + page.esbl_result["action"])
                st.error(_em)
            elif prob == "crpa":
                _em = (f"[{'!!' if page.esbl_result.get('dtr') else '!'}] "
                       f"{_mech} (confidence {_conf}%)\n"
                       + page.esbl_result["detail"] + "  \n🔹 " + page.esbl_result["action"])
                if page.esbl_result.get("dtr"):
                    st.error(_em)
                else:
                    st.warning(_em)
            elif prob == "moderate":
                _em = (f"[~] ESBL Confirmation Recommended (confidence {_conf}%)\n"
                       + page.esbl_result["detail"] + "  \n🔹 " + page.esbl_result["action"])
                st.warning(_em)

    # ── Resistance Phenotype Engine ──────────────────────────────────
    page.phenotypes = detect_resistance_phenotypes(page.organism_type, page.sir_map)
    if page.phenotypes:
        with st.expander("🦠 Resistance Phenotypes Detected", expanded=True):
            for ph in page.phenotypes:
                isolation_tag = "  🚨 **عزل فوري مطلوب**" if ph["isolation"] else ""
                msg = (f"{ph['icon']} **{ph['label']}**{isolation_tag}  \n"
                       f"{ph['detail']}  \n"
                       f"🔹 {ph['action']}")
                if ph["isolation"]:
                    st.error(msg)
                else:
                    st.warning(msg)
                if ph.get("matched_markers"):
                    st.caption(f"Evidence: {', '.join(ph['matched_markers'])}")


def render_ast_qc(page):
    """Right column: AST quality control and its PDF."""
    # ── AST Quality Control Checker ───────────────────────────────────
    if page.sir_map:
        qc_issues    = run_ast_qc(page.organism_type, page.sir_map, specimen=page.culture_type,
                               sdd=getattr(page, "sdd_drugs", None))
        qa_confidence = compute_qa_confidence(qc_issues, page.sir_map, page.organism_type)

        with st.expander(
            f"{qa_confidence['icon']} AST Quality Control -- "
            f"{qa_confidence['level']} ({qa_confidence['score']}/100)"
            + (f" -- {len(qc_issues)} Issue(s)" if qc_issues else ""),
            expanded=bool(qc_issues)
        ):
            st.caption("تحقق تلقائي من منطقية نتائج المزرعة وفق CLSI M100 Ed36 و EUCAST Expert Rules")

            # Confidence score box
            st.markdown(
                f"<div style='padding:2mm 3mm;border-radius:2mm;"
                f"background:{qa_confidence['color']}15;"
                f"border:1px solid {qa_confidence['color']};margin-bottom:4px'>"
                f"<b style='color:{qa_confidence['color']}'>"
                f"{qa_confidence['icon']} {qa_confidence['level']} — {qa_confidence['score']}/100</b>"
                f"<ul style='margin:4px 0 0 16px;padding:0;font-size:0.85em'>"
                + "".join(f"<li>{r}</li>" for r in qa_confidence["reasons"])
                + "</ul></div>",
                unsafe_allow_html=True,
            )

            if qc_issues:
                for issue in qc_issues:
                    icon = "❌" if issue["severity"] == "error" else "⚠️"
                    if issue["severity"] == "error":
                        st.error(f"{issue['message']}  \n✏️ {issue['fix']}")
                    else:
                        st.warning(f"{issue['message']}  \n✏️ {issue['fix']}")
            else:
                st.success("✅ All AST consistency checks passed. No issues detected.")

            # ── AST Panel Completeness ──────────────────────────────
            # Added HERE 2026-08-22: this is the "AST Quality Control"
            # expander (run_ast_qc(), EUCAST-based) -- a completely
            # separate, independent rendering pipeline from the
            # ast_qa_engine.py-based "🔬 AST Quality Check" expander
            # elsewhere on this page. Panel Completeness had only been
            # wired into the LATTER, which meant it never appeared here
            # at all, no matter how correctly it worked on its own --
            # this repo has carried two parallel QC systems since before
            # this feature existed (flagged, not caused, by this work).
            # Independent of qc_issues/AST_QA_AVAILABLE on purpose, same
            # reasoning as the other integration point: this card calls
            # ast_panel_completeness.py directly and has no dependency on
            # run_ast_qc() succeeding or failing.
            if PANEL_COMPLETENESS_AVAILABLE:
                _pc2 = _check_panel_completeness_ext(
                    page.organism_type, page.culture_type, page.sir_map
                )
                if _pc2.status != "not_evaluated":
                    _pc2_missing = _pc2.missing_primary + _pc2.missing_supplemental
                    st.divider()
                    st.markdown("**🧫 AST Panel Completeness**")
                    st.caption(f"الكائن: {_pc2.organism_group}")
                    _pc2c1, _pc2c2, _pc2c3 = st.columns(3)
                    _pc2c1.metric("Expected", _pc2.expected_total)
                    _pc2c2.metric("Tested", _pc2.tested_count)
                    _pc2c3.metric("Missing", len(_pc2_missing))
                    if not _pc2_missing:
                        st.success("✅ Panel adequate -- كل المضادات "
                                   "المتوقعة لهذا الكائن تم اختبارها.")
                    else:
                        if _pc2.status == "critical":
                            st.error(
                                "🔴 كل المضادات الأساسية اللي اتعملت كانت "
                                "Resistant، ومضادات أساسية متوقعة لسه معملتش "
                                "-- ممكن يكون فيه خيار علاجي في اللي ناقص. "
                                "متقولش 'مفيش خيارات' من لوحة ناقصة."
                            )
                        else:
                            st.warning(
                                f"⚠️ Panel incomplete -- "
                                f"{len(_pc2_missing)} مضاد متوقع غير مُختبَر"
                            )
                        if _pc2.missing_primary:
                            st.markdown(
                                "**ناقص (أساسي):** " +
                                " · ".join(f"⚠️ {d}" for d in _pc2.missing_primary)
                            )
                        if _pc2.missing_supplemental:
                            st.markdown(
                                "**ناقص (تكميلي/اختياري):** " +
                                " · ".join(f"🔵 {d}" for d in _pc2.missing_supplemental)
                            )
                        if _pc2.rule_id:
                            from cdss.guidelines.guideline_registry import citation_line as _pc2_cite
                            _pc2_ref = _pc2_cite(_pc2.rule_id)
                            if _pc2_ref:
                                st.caption(f"📖 {_pc2_ref}")

            # QA Report PDF — for microbiologist internal archive only
            st.divider()
            st.caption("📄 تقرير الجودة الداخلي (للميكروبيولوجي فقط — لا يُرسل للطبيب)")
            if WEASYPRINT_AVAILABLE:
                _qa_pdf = generate_qa_report_pdf(
                    organism=page.organism_type,
                    specimen=page.culture_type,
                    sir_map=page.sir_map,
                    qc_issues=qc_issues,
                    confidence=qa_confidence,
                    microbiologist=st.session_state.get("microbiologist", ""),
                    # FIX 2026-08-03. This read "patient_name", a key NOTHING
                    # in this file ever writes — the name is stored under
                    # patient_name_final (the confirmed value) and
                    # patient_name_ocr (what the scan read). So the patient
                    # reference on every internal QA report has been blank
                    # since the field was added, and a QA document with no
                    # patient reference cannot be tied back to the isolate
                    # it audits, which is the only thing it is for.
                    #
                    # Found by a static session_state audit: 4 keys were
                    # READ that are never WRITTEN, and this was the one that
                    # mattered. Same shape as the safety-gate "why" versus
                    # "reason_ar" mismatch — a producer and a consumer
                    # naming the same fact differently.
                    patient_ref=(st.session_state.get("patient_name_final", "")
                                 or st.session_state.get("patient_name_ocr", "")
                                 or ""),
                    sdd=getattr(page, "sdd_drugs", None),
                )
                if _qa_pdf:
                    st.download_button(
                        "⬇️ Download AST-QA Report (PDF)",
                        data=_qa_pdf,
                        file_name=f"AST-QA-Report-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf",
                        mime="application/pdf",
                        key="qa_report_pdf_dl",
                    )
                else:
                    st.caption("⚠️ تعذر إنشاء PDF لتقرير الجودة.")
            else:
                st.caption("⚠️ WeasyPrint غير متاح في هذه البيئة.")
