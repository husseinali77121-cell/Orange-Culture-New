# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Right column: the therapeutic recommendation lists.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.common.catalog import AWARE_COLORS
from cdss.common.util import get_route_label
from cdss.organisms.pathogenicity import gate_suppresses
from cdss_ui.state import treat_override_key
from cdss.stewardship.ranking import rank_sensitive_antibiotics
from cdss.stewardship.ranking import route_label
from cdss.stewardship.syndrome import get_infection_syndrome
from cdss.therapy.clsi_categories import result_label
from cdss.therapy.notes import warned_note_for
from cdss.therapy.tables import preg_status_of


def _sir_tag(page, name):
    """" [S]" / " [SDD]" / "" -- the result as entered (CLSI SDD shown as SDD)."""
    if not page.sir_map or name not in page.sir_map:
        return ""
    return f" [{result_label(name, page.sir_map[name], getattr(page, 'sdd_read', None) or getattr(page, 'sdd_drugs', ()))}]"


def render_treatment_gate(page) -> bool:
    """The no-treatment banner and the physician override (v7.2). True = lists withheld."""
    _gate = getattr(page, "treatment_gate", None)
    if not _gate:
        return False
    st.error(f"🚫 **لا يوجد داعٍ لمضاد حيوي — تقييم الـ Pathogenicity:** {_gate['verdict']}  \n"
             f"{_gate['reason_ar']}")
    st.checkbox("أنا الطبيب المعالج: اعرض الخيارات رغم ذلك (قرار إكلينيكي مختلف — يُطبع في "
                "التقرير)", key=treat_override_key(),
                help="الموافقة مرتبطة بهذا التقييم: أي تغيير في المدخلات أو تقييم جديد يلغيها.")
    if gate_suppresses(_gate):
        page.ranked = []
        st.caption(f"الخيارات المحسوبة مخفية ولا تُطبع في التقارير: {len(page.allowed)} مسموح · "
                   f"{len(page.warned)} بحذر · {len(page.banned)} ممنوع/غير فعّال. "
                   "نتيجة الحساسية نفسها تظل في التقرير للعلم.")
        return True
    st.warning("⚠️ الخيارات معروضة **بطلب الطبيب** رغم أن التقييم يقول: لا علاج — "
               "ويُطبع ذلك في التقرير.")
    return False


def render_recommendations(page):
    """Ranking, syndrome, pregnancy cautions, banned / warned / allowed lists."""
    # ── Infection Syndrome Module (computed first: later panels read it) ──
    page.syndrome_info = get_infection_syndrome(
        specimen=page.culture_type,
        organism=page.organism_type,
        age=page.age,
        is_preg=page.is_preg,
        # v7.0: a URINARY catheter from the case record. v7.1: for sputum the
        # ventilator / tracheostomy (HAP/VAP), for blood the central line (CRBSI).
        is_cath=bool(getattr(page, "case", None) is not None and page.case.syndrome_device()),
        sex=page.sex,
        uti_upper=(getattr(page, "_uti_syn_now", "") == "upper"),
        complicated=(getattr(page, "_uti_syn_now", "") == "cuti"),
    )
    # v7.2: a "do not treat" verdict withholds every treatment list.
    if render_treatment_gate(page):
        return

    # ── Smart Antibiotic Ranking ──────────────────────────────────────
    page.ranked = []
    if page.allowed:
        ranked = rank_sensitive_antibiotics(
            page.allowed, page.culture_type, page.organism_type, page.sir_map, page.phenotypes,
            carbapenemase_type=getattr(page, "_carb_type_now", None),
            uti_syndrome=getattr(page, "_uti_syn_now", None),
        )
        page.ranked = ranked          # v7.0: the duration panel reads the top agent's route
        with st.expander("🏆 Smart Antibiotic Ranking", expanded=False):
            # v7.4 (external case review): what the ranking was built for
            from cdss.resistance.esbl_status import esbl_status
            from cdss.stewardship.ranking import ranking_basis
            _basis = ranking_basis(
                page.culture_type, getattr(page, "_uti_syn_now", None), getattr(page, "case", None),
                esbl_status(getattr(page, "esbl_result", None), getattr(page, "aux_tests", None)),
                page.sir_map, getattr(page, "_carb_type_now", None))
            if _basis:
                st.info(f"🎯 Ranked for: {_basis} — لو المتلازمة أو الشدة مختلفة، الترتيب يتغيّر.")
            st.caption("مرتب حسب: نتيجة المزرعة ← المفضّل في الإرشادات للآلية والموقع (IDSA 2026؛ "
                       "التهاب المثانة: IDSA/ESCMID 2011؛ MSSA: β-lactam) "
                       "← WHO AWaRe ← طريق الإعطاء (لا أفضلية للفموي في الدم/السائل النخاعي) ← الأولوية. "
                       "⭐ = مفضّل في الإرشادات لهذه الآلية والموقع")
            _aic = {"Access": "🟢", "Watch": "🟡", "Reserve": "🔴"}
            for i, item in enumerate(ranked[:8], 1):
                sir_badge  = item.get("_sir", "--")
                aware      = item.get("aware", "")
                route      = "💊 Oral" if route_label(item, page.culture_type) == "PO" else "💉 IV/IM"
                score      = item.get("_score", 0)
                aware_icon = _aic.get(aware, "⚪")
                _guide = " ⭐" if item.get("_guideline_preferred") else ""
                st.markdown(
                    f"**{i}.** {item['name']}{_guide} &nbsp; "
                    f"`{sir_badge}` &nbsp; {aware_icon} {aware} &nbsp; {route} &nbsp;"
                    f"<small style='color:gray'>score:{score}</small>",
                    unsafe_allow_html=True)

    if page.syndrome_info:
        with st.expander(f"🏥 Infection Syndrome: {page.syndrome_info['syndrome']}", expanded=False):
            s1, s2 = st.columns(2)
            with s1:
                st.markdown(f"**النوع:** {page.syndrome_info['sub_type']}")
                st.markdown(f"**مدة العلاج:** {page.syndrome_info['duration']}")
                # v7.1: this list is EMPIRICAL (before the culture). Printed alone it
                # contradicted the result -- ceftriaxone "first line" for a VRE urine.
                st.markdown(f"**الخط الأول التجريبي (قبل المزرعة):** "
                            f"{', '.join(page.syndrome_info['first_choice'])}")
                _by_ast = [r.get("name", "") for r in (getattr(page, "ranked", None) or [])[:3]]
                if _by_ast:
                    st.markdown(f"**حسب نتيجة المزرعة:** {', '.join(_by_ast)}")
            with s2:
                st.info(f"**Escalation:** {page.syndrome_info['escalation']}")
                st.caption(f"📌 Culture threshold: {page.syndrome_info['threshold']}")

    if page.is_preg and page.preg_warn_items:
        st.markdown("---")
        st.markdown("### 🤰 Pregnancy -- Use With Caution")
        st.info(
            "الأدوية التالية **ليست محظورة تلقائيًا** لكنها تحتاج تقييمًا طبيًا دقيقًا.\n\n"
            "**القرار النهائي للطبيب المعالج حصراً.**"
        )
        for item in page.preg_warn_items:
            with st.expander(f"⚠️ {item['name']} -- تفاصيل التحذير"):
                for line in (item.get("preg_note") or "").splitlines():
                    st.write(line)

    if page.banned:
        with st.expander("🚫 Contraindicated / Ineffective", expanded=True):
            # Every category the engine and the gate emit (2026-11-11, round
            # 4): ten of them had no label and printed an empty "[]".
            cat_labels = {
                "resistant": "مقاوم في المزرعة",
                "renal":     "قصور كلوي",
                "pregnancy": "ممنوع في الحمل",
                "child":     "غير مناسب للعمر",
                "neonate":   "حديثو الولادة / الرضع",
                "hepatic":   "قصور كبدي",
                "allergy":   "حساسية دوائية",
                "organism":  "غير فعال للجرثومة",
                "cross_resistance": "مقاومة متصالبة",
                "no_breakpoint": "لا breakpoint / غير مُبلَّغ",
                "d_test_inducible": "مقاومة مستحثة (D-test)",
                "penicillinase_producer": "Penicillinase",
                "specimen":  "غير مناسب للعينة",
                "uti_upper": "لا يصلح للحويضة / cUTI",
                "safety_gate": "بوابة الأمان (الموقع / حالة المريض)",
                "unreadable": "نتيجة غير مقروءة",
                "other":     "موانع أخرى",
            }
            for item in page.banned:
                _cat = item.get("category", "")
                # v7.4 (external case review): AST status kept apart from suitability
                _s_tested = page.sir_map.get(item["name"]) == "S"
                st.error(
                    f"💊 {item['name']}  [{cat_labels.get(_cat, _cat)}]"
                    + ("  · **AST: S (tested) — غير مناسب هنا، النتيجة لم تتغير**" if _s_tested else "")
                    + f"\n{item.get('reason_short', '')}"
                )

    if page.warned:
        with st.expander("🟡 Warnings / Dose Adjustment Required", expanded=True):
            # `culture_intermediate` rather than warning_reason: an I that
            # also needs a renal or hepatic adjustment carries the OTHER
            # reason in that slot, and used to drop out of this banner
            # entirely. Both facts are now shown for the same agent.
            _interm = [w for w in page.warned
                       if w.get("warning_reason") == "intermediate_culture"
                       or w.get("culture_intermediate")]
            _others = [w for w in page.warned if w.get("warning_reason") != "intermediate_culture"]
            if _interm:
                _names = ", ".join(
                    w['name'] + _sir_tag(page, w['name'])
                    for w in _interm
                )
                st.warning(
                    f"⚠ Intermediate (I) / SDD on culture (CLSI M100) -- use only if no "
                    f"susceptible option fits: **{_names}**"
                )
                # v6.9: what the I / SDD is worth for THIS agent at THIS site
                # (CLSI: urine-concentrated, higher dose, or the SDD regimen).
                for w in _interm:
                    if w.get("warning_reason") == "intermediate_culture":
                        st.caption(f"**{w['name']}{_sir_tag(page, w['name'])}** -- "
                                   f"{warned_note_for(w, 'ar')}")
            for item in _others:
                sir_tag = _sir_tag(page, item['name'])
                # One resolver, not an if/else that fell through to
                # renal_note for every reason it did not name explicitly.
                _note = warned_note_for(item, "ar")
                # v6.9: a second caution (e.g. the AAP paediatric quinolone
                # note on a drug already warned for renal dosing) is shown too,
                # not lost behind the reason that won the slot.
                _extra = str(item.get("clinical_note") or "").strip()
                if _extra and _note and _extra not in _note:
                    _note = f"{_note}  \n🧭 {_extra}"
                if _note:
                    st.warning(f"**{item['name']}{sir_tag}** -- {_note}")
                else:
                    # An item with no explanation is a data defect, not a
                    # blank bullet: say so rather than rendering a bare name.
                    st.warning(
                        f"**{item['name']}{sir_tag}** -- ⚠️ تحذير بلا تفسير "
                        f"مسجَّل (reason={item.get('warning_reason') or '—'}). "
                        "راجِع النتيجة يدوياً وأبلغ عن العطل."
                    )
                # An I result that also needs a dose adjustment gives the
                # clinician two instructions pointing opposite ways. Say so
                # explicitly rather than printing only the one that happened
                # to win the warning_reason slot.
                if (item.get("culture_intermediate")
                        and item.get("warning_reason") in ("renal_adjustment",
                                                           "hepatic_adjustment")):
                    st.error(
                        f"⚠️ **{item['name']}: تعارض في اتجاه الجرعة.** "
                        + ("النتيجة **SDD** — حسب CLSI حسّاس فقط بنظام تعرّض أعلى "
                           if item.get("culture_sdd") else
                           "النتيجة **I** — حسب CLSI فعّال فقط حيث يتركّز الدواء (مثل "
                           "البول) أو بجرعة أعلى من المعتادة ")
                        + "، لكن حالة المريض تفرض **خفض** الجرعة. "
                        "لا تُعدّل الجرعة بناءً على أحد العاملين وحده — "
                        "اختر بديلاً حسّاساً (S) إن وُجد، أو استشر "
                        "الصيدلة الإكلينيكية لضبط الجرعة بمتابعة TDM."
                    )

    if page.allowed:
        st.success(f"🟢 {len(page.allowed)} Recommended Option(s)")
        for item in page.allowed:
            sir_badge = _sir_tag(page, item['name'])
            preg_flag = " 🤰" if (page.is_preg and preg_status_of(item) == "Warn") else ""
            aware_val = item.get("aware", "Unknown")
            color_val = AWARE_COLORS.get(aware_val, aware_val)
            with st.expander(
                f"{item['name']}{sir_badge}{preg_flag} -- {color_val}", expanded=False
            ):
                c1, c2 = st.columns(2)
                c1.write(f"**Class:** {item.get('class','-')}")
                c2.write(f"**Route:** {get_route_label(item)}")
                st.write(f"**Note:** {item.get('note','-')}")
                if item.get("clinical_note"):
                    st.info(f"🧭 {item['clinical_note']}")
                if item.get("gate_dose_note"):
                    st.info(f"💉 {item['gate_dose_note']}")
                spec_note = (item.get("specimen_notes") or {}).get(page.culture_type, "")
                if spec_note:
                    st.info(f"**{page.culture_type} Note:** {spec_note}")
                if page.is_renal:
                    st.caption(f"Renal: {item.get('renal_note','-')}")
                if page.is_preg and preg_status_of(item) == "Warn":
                    pn = (item.get("preg_note") or "").splitlines()
                    if pn:
                        st.caption(f"🤰 {pn[0]}")
    elif page.warned and page.is_renal:
        # v7.1: renal dose adjustment is a caution, never a ban.
        st.info("لا يوجد خيار بلا تحذير: الأدوية الفعّالة موجودة في قائمة الحذر أعلاه بجرعتها "
                "الكلوية المعدّلة — تُستخدم بهذه الجرعة.")
    elif not page.banned and not page.warned:
        st.info("اختر المضادات الحساسة أو المناسبة من القائمة أعلاه.")
