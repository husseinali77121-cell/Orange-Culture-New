# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Right column: the therapeutic recommendation lists.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
import streamlit as st

from cdss.common.catalog import AWARE_COLORS
from cdss.common.util import get_route_label
from cdss.stewardship.ranking import rank_sensitive_antibiotics
from cdss.stewardship.syndrome import get_infection_syndrome
from cdss.therapy.notes import warned_note_for
from cdss.therapy.tables import preg_status_of


def render_recommendations(page):
    """Ranking, syndrome, pregnancy cautions, banned / warned / allowed lists."""
    # ── Smart Antibiotic Ranking ──────────────────────────────────────
    if page.allowed:
        ranked = rank_sensitive_antibiotics(
            page.allowed, page.culture_type, page.organism_type, page.sir_map, page.phenotypes
        )
        with st.expander("🏆 Smart Antibiotic Ranking", expanded=False):
            st.caption("مرتب حسب: نتيجة المزرعة + WHO AWaRe + طريق الإعطاء + ملاءمة العينة")
            _aic = {"Access": "🟢", "Watch": "🟡", "Reserve": "🔴"}
            for i, item in enumerate(ranked[:8], 1):
                sir_badge  = item.get("_sir", "--")
                aware      = item.get("aware", "")
                route      = "💊 Oral" if item.get("high_po") else "💉 IV/IM"
                score      = item.get("_score", 0)
                aware_icon = _aic.get(aware, "⚪")
                st.markdown(
                    f"**{i}.** {item['name']} &nbsp; "
                    f"`{sir_badge}` &nbsp; {aware_icon} {aware} &nbsp; {route} &nbsp;"
                    f"<small style='color:gray'>score:{score}</small>",
                    unsafe_allow_html=True)

    # ── Infection Syndrome Module ─────────────────────────────────────
    page.syndrome_info = get_infection_syndrome(
        specimen=page.culture_type,
        organism=page.organism_type,
        age=page.age,
        is_preg=page.is_preg,
        is_cath=False,
        sex=page.sex,
    )
    if page.syndrome_info:
        with st.expander(f"🏥 Infection Syndrome: {page.syndrome_info['syndrome']}", expanded=False):
            s1, s2 = st.columns(2)
            with s1:
                st.markdown(f"**النوع:** {page.syndrome_info['sub_type']}")
                st.markdown(f"**مدة العلاج:** {page.syndrome_info['duration']}")
                st.markdown(f"**الخط الأول (guidelines):** {', '.join(page.syndrome_info['first_choice'])}")
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
                st.error(
                    f"💊 {item['name']}  [{cat_labels.get(_cat, _cat)}]\n"
                    f"{item.get('reason_short', '')}"
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
                    w['name'] + (f" [{page.sir_map[w['name']]}]" if page.sir_map and w['name'] in page.sir_map else "")
                    for w in _interm
                )
                st.warning(
                    f"⚠ Intermediate (I) on culture -- use only if no better option: **{_names}**"
                )
            for item in _others:
                sir_tag = (f" [{page.sir_map[item['name']]}]"
                           if page.sir_map and item['name'] in page.sir_map else "")
                # One resolver, not an if/else that fell through to
                # renal_note for every reason it did not name explicitly.
                _note = warned_note_for(item, "ar")
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
                        "النتيجة **I** — وتعريف EUCAST لها *Susceptible, "
                        "Increased exposure*: الدواء يعمل فقط بجرعة أعلى أو "
                        "تسريب ممتد. لكن حالة المريض تفرض **خفض** الجرعة. "
                        "لا تُعدّل الجرعة بناءً على أحد العاملين وحده — "
                        "اختر بديلاً حسّاساً (S) إن وُجد، أو استشر "
                        "الصيدلة الإكلينيكية لضبط الجرعة بمتابعة TDM."
                    )

    if page.allowed:
        st.success(f"🟢 {len(page.allowed)} Recommended Option(s)")
        for item in page.allowed:
            sir_badge = (f" [{page.sir_map[item['name']]}]"
                         if page.sir_map and item['name'] in page.sir_map else "")
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
                spec_note = (item.get("specimen_notes") or {}).get(page.culture_type, "")
                if spec_note:
                    st.info(f"**{page.culture_type} Note:** {spec_note}")
                if page.is_renal:
                    st.caption(f"Renal: {item.get('renal_note','-')}")
                if page.is_preg and preg_status_of(item) == "Warn":
                    pn = (item.get("preg_note") or "").splitlines()
                    if pn:
                        st.caption(f"🤰 {pn[0]}")
    elif not page.banned and not page.warned:
        st.info("اختر المضادات الحساسة أو المناسبة من القائمة أعلاه.")
