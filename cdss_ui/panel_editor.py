# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Right column: the editable S/I/R panel.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
from typing import Dict
import streamlit as st

from cdss.formulary.abx_guidelines import ABX_GUIDELINES


def render_panel_editor(page):
    """The editable S/I/R panel: OCR rows, quick add, deletions, summary."""
    # ══════════════════════════════════════════════════════
    # AST Input Panel -- OCR + Manual Entry موحّد
    # ══════════════════════════════════════════════════════
    ocr_sir_map = page.payload["sir_map"]
    sir_options = ["S", "I", "R"]

    st.markdown("**📊 نتائج المزرعة -- S / I / R**")
    st.caption("✅ من OCR تلقائياً -- عدّل أي قيمة خطأ أو أضف مضاد فاته الـ OCR")

    # ── Drugs detected by OCR WITH S/I/R ─────────────────────────
    all_known   = sorted(ABX_GUIDELINES.keys())
    ocr_drugs   = list(ocr_sir_map.keys())

    # Drugs OCR found by NAME but couldn't determine S/I/R for
    ocr_detected_no_sir = [d for d in page.drugs_from_ocr
                            if d not in ocr_sir_map and d]

    if ocr_detected_no_sir:
        st.markdown(
            f"**🔍 OCR اكتشف {len(ocr_detected_no_sir)} مضاد بدون نتيجة S/I/R واضحة:**",
            help="OCR وجد أسماء هذه الأدوية في الورقة لكن لم يتعرف على النتيجة -- حدد النتيجة يدوياً"
        )
        no_sir_cols = st.columns(min(len(ocr_detected_no_sir), 3))
        for idx_d, drug_no_sir in enumerate(ocr_detected_no_sir):
            col_d = no_sir_cols[idx_d % 3]
            assign = col_d.selectbox(
                f"⚠️ {drug_no_sir}",
                ["--", "S", "I", "R"],
                key=f"no_sir_{drug_no_sir}_{page.file_hash[:8]}",
                help=f"OCR وجد '{drug_no_sir}' في النص -- حدد النتيجة أو اتركها"
            )
            if assign != "--":
                if drug_no_sir not in ocr_drugs:
                    ocr_drugs.append(drug_no_sir)
                ocr_sir_map[drug_no_sir] = assign
        st.divider()

    # ── الأدوية المضافة يدوياً (فاتها OCR كلياً) ─────────────────
    manual_prev = [d for d in st.session_state.sir_map_edited.keys()
                   if d not in ocr_drugs]

    # ── إضافة سريعة: دواء + نتيجته مرة واحدة ──────────────────────
    # Requested 2026-08-22: adding a missing drug through the multiselect
    # below always lands it at "S" first (that selectbox's own default),
    # then needs a SEPARATE edit afterward to set the real result --
    # exactly the two-step flow that made the freshness bug upstream
    # confusing to reason about (which state was "saved"?). This widget
    # puts the drug picker and its S/I/R result side by side so one
    # click adds the drug WITH its actual result already correct --
    # nothing to go back and fix.
    _quick_add_pool = [d for d in all_known
                       if d not in ocr_drugs and d not in ocr_detected_no_sir
                       and d not in manual_prev]
    if _quick_add_pool:
        st.markdown("<small style='color:#1a6b3a'>⚡ إضافة سريعة -- دواء ونتيجته "
                    "مرة واحدة:</small>", unsafe_allow_html=True)
        _qa_c1, _qa_c2, _qa_c3 = st.columns([5, 2, 2])
        _quick_drug = _qa_c1.selectbox(
            "المضاد الناقص", options=[""] + sorted(_quick_add_pool),
            key=f"quick_add_drug_{page.file_hash[:8]}", label_visibility="collapsed",
            format_func=lambda d: "اختر المضاد الناقص..." if d == "" else d,
        )
        _quick_sir = _qa_c2.selectbox(
            "النتيجة", options=sir_options,
            key=f"quick_add_sir_{page.file_hash[:8]}", label_visibility="collapsed",
        )
        if _qa_c3.button("➕ إضافة", key=f"quick_add_btn_{page.file_hash[:8]}",
                         disabled=not _quick_drug, use_container_width=True):
            _mkey = f"manual_drugs_{page.file_hash[:8]}"
            _current_manual = list(st.session_state.get(_mkey, manual_prev))
            if _quick_drug not in _current_manual:
                _current_manual.append(_quick_drug)
            st.session_state[_mkey] = _current_manual
            # Set BOTH the aggregate map (what Panel Completeness/QC read)
            # and this specific drug's own selectbox key (so it renders
            # showing the chosen result, not "S", the instant it appears
            # below) -- same reasoning as the sir_map_edited freshness fix:
            # write before the rerun, not after, so the very next render
            # is already correct.
            _sir_now = dict(st.session_state.sir_map_edited)
            _sir_now[_quick_drug] = _quick_sir
            st.session_state.sir_map_edited = _sir_now
            st.session_state[f"sir_manual_{_quick_drug}_{page.file_hash[:8]}"] = _quick_sir
            st.rerun()

    manual_extra = st.multiselect(
        "➕ أو أضف عدة مضادات دفعة واحدة (كلها هتتحط S مبدئياً وتقدر تعدّلها تحت)",
        options=[d for d in all_known if d not in ocr_drugs and d not in ocr_detected_no_sir],
        default=manual_prev,
        key=f"manual_drugs_{page.file_hash[:8]}",
        help="اختر الأدوية التي ظهرت في التقرير لكن OCR لم يكتشفها على الإطلاق",
    )

    # ── بناء القائمة الكاملة: OCR + Manual ───────────────────────
    all_drugs_to_show = ocr_drugs + [d for d in manual_extra if d not in ocr_drugs]

    # ── عرض SIR dropdown لكل دواء ─────────────────────────────────
    edited_sir: Dict[str, str] = {}

    # ── Deleted drugs list (persisted in session) ─────────────────
    _del_key = f"deleted_drugs_{page.file_hash[:8]}"
    if _del_key not in st.session_state:
        st.session_state[_del_key] = set()

    if all_drugs_to_show:
        # OCR drugs أولاً
        if ocr_drugs:
            st.markdown("<small style='color:#555'>🔍 من OCR -- يمكنك حذف أي مضاد بالضغط على ❌:</small>",
                        unsafe_allow_html=True)
            for i in range(0, len(ocr_drugs), 3):
                row_drugs = ocr_drugs[i: i + 3]
                row_cols  = st.columns([3,3,3])
                for col, drug in zip(row_cols, row_drugs):
                    if drug in st.session_state[_del_key]:
                        # Show restore button
                        if col.button(f"↩️ {drug}", key=f"restore_{drug}_{page.file_hash[:8]}",
                                      help="استعادة المضاد"):
                            st.session_state[_del_key].discard(drug)
                            st.rerun()
                        continue
                    cur = st.session_state.sir_map_edited.get(drug, ocr_sir_map[drug])
                    if cur not in sir_options:
                        cur = "S"
                    label_icons = {"S": "🟢", "I": "🟡", "R": "🔴"}
                    # 4-column: icon+name | selectbox | delete btn
                    _c1, _c2, _c3 = col.columns([4, 3, 1])
                    _c1.markdown(f"<small>{label_icons.get(cur,'')} **{drug}**</small>",
                                 unsafe_allow_html=True)
                    new_val = _c2.selectbox(
                        "##",
                        options=sir_options,
                        index=sir_options.index(cur),
                        key=f"sir_{drug}_{page.file_hash[:8]}",
                        label_visibility="collapsed"
                    )
                    if _c3.button("❌", key=f"del_{drug}_{page.file_hash[:8]}",
                                  help=f"حذف {drug}"):
                        st.session_state[_del_key].add(drug)
                        st.rerun()
                    edited_sir[drug] = new_val

        # Manual drugs
        manual_new = [d for d in manual_extra if d not in ocr_drugs]
        if manual_new:
            st.markdown("<small style='color:#1a6b3a'>➕ مُضافة يدوياً:</small>",
                        unsafe_allow_html=True)
            for i in range(0, len(manual_new), 3):
                row_drugs = manual_new[i: i + 3]
                row_cols  = st.columns(3)
                for col, drug in zip(row_cols, row_drugs):
                    if drug in st.session_state[_del_key]:
                        if col.button(f"↩️ {drug}", key=f"restore_m_{drug}_{page.file_hash[:8]}"):
                            st.session_state[_del_key].discard(drug)
                            st.rerun()
                        continue
                    cur = st.session_state.sir_map_edited.get(drug, "S")
                    if cur not in sir_options:
                        cur = "S"
                    label_icons = {"S": "🟢", "I": "🟡", "R": "🔴"}
                    _c1, _c2, _c3 = col.columns([4, 3, 1])
                    _c1.markdown(f"<small>{label_icons.get(cur,'')} **{drug}**</small>",
                                 unsafe_allow_html=True)
                    new_val = _c2.selectbox(
                        "##",
                        options=sir_options,
                        index=sir_options.index(cur),
                        key=f"sir_manual_{drug}_{page.file_hash[:8]}",
                        label_visibility="collapsed"
                    )
                    if _c3.button("❌", key=f"del_m_{drug}_{page.file_hash[:8]}",
                                  help=f"حذف {drug}"):
                        st.session_state[_del_key].add(drug)
                        st.rerun()
                    edited_sir[drug] = new_val

    # ── Apply deletions to sir_map ────────────────────────────────
    _deleted = st.session_state.get(_del_key, set())
    edited_sir = {d: v for d, v in edited_sir.items() if d not in _deleted}

    # 2026-08-22: Resistance Profile / AST Quality Check / Panel
    # Completeness (above, ~line 6267/6355) render BEFORE this block in
    # script order, so on the run where the user just changed a result
    # they were reading st.session_state.sir_map_edited as it stood at
    # the END of the PREVIOUS run -- one edit behind. Each individual
    # st.selectbox's own session_state[key] is already fresh at this
    # point (Streamlit syncs those before the script starts), but the
    # AGGREGATE dict those QC sections actually read is only assembled
    # here. Rather than relocating ~150 lines of interdependent widget
    # code above this point (real risk of breaking the column/key/rerun
    # interactions elsewhere on this page), force one extra rerun exactly
    # when the aggregate changed -- the same st.rerun() idiom this block
    # already uses for delete/restore, just keyed off a value change
    # instead of a button click. sir_map_edited is written BEFORE the
    # rerun fires, so the follow-up run reads current data and converges
    # (no loop): a real Piperacillin+Tazobactam entry no longer shows as
    # missing the moment it's saved, not one edit later.
    _prev_sir_map_edited = st.session_state.get("sir_map_edited")
    st.session_state.sir_map_edited = edited_sir
    if edited_sir != _prev_sir_map_edited:
        st.rerun()

    # sir_map = كل الأدوية (OCR + manual) مع نتائجها -- بعد الحذف
    page.sir_map = dict(edited_sir)

    # final_drugs = كل الأدوية التي أُدخلت نتائجها
    page.final_drugs = list(page.sir_map.keys())

    # ── ملخص سريع ─────────────────────────────────────────────────
    if page.sir_map:
        s_count = sum(1 for v in page.sir_map.values() if v == "S")
        i_count = sum(1 for v in page.sir_map.values() if v == "I")
        r_count = sum(1 for v in page.sir_map.values() if v == "R")
        st.caption(
            f"📊 إجمالي: {len(page.sir_map)} مضاد &nbsp;|&nbsp; "
            f"🟢 Sensitive: {s_count} &nbsp;|&nbsp; "
            f"🟡 Intermediate: {i_count} &nbsp;|&nbsp; "
            f"🔴 Resistant: {r_count}"
        )


_AUX_NOT_DONE = "لم يُجرَ / Not done"
_AUX_CHOICES = [_AUX_NOT_DONE, "Negative", "Positive"]


def current_aux_tests(file_hash: str) -> dict:
    """The supplementary tests as currently selected, in panel form ({'D-test': 'Negative'}).

    Read from the widget state, so a section that renders BEFORE the panel
    editor (the left-column QA check) sees the value of this run, not the last.
    """
    out = {}
    for panel_key, widget in (("D-test", "d_test"), ("Penicillinase", "penicillinase")):
        choice = st.session_state.get(f"{widget}_{(file_hash or '')[:8]}")
        if choice in ("Negative", "Positive"):
            out[panel_key] = choice
    return out


def render_aux_tests(page):
    """D-test and penicillinase result -- asked only when the panel makes them decisive.

    Without these two inputs the engine could only ever answer "not confirmed":
    clindamycin stayed banned on every erythromycin-R isolate and penicillin-S
    staphylococci kept their caution, whatever the bench had found.
    """
    sir = page.sir_map
    fh = (page.file_hash or "")[:8]
    org_l = (page.organism_type or "").lower()
    if sir.get("Erythromycin") == "R" and sir.get("Clindamycin") == "S":
        st.selectbox(
            "🧪 D-test (Erythromycin R + Clindamycin S)", _AUX_CHOICES, key=f"d_test_{fh}",
            help="سالب: Clindamycin يُبلَّغ حسّاساً. موجب: مقاومة مستحثة (iMLSB) — يُبلَّغ مقاوماً. "
                 "CLSI M100 Ed36 · EUCAST v16.")
    if (("staph" in org_l or "mssa" in org_l)
            and any(sir.get(d) == "S" for d in ("Penicillin", "Ampicillin", "Amoxicillin"))):
        st.selectbox(
            "🧪 Penicillinase (zone-edge / nitrocefin / blaZ)", _AUX_CHOICES,
            key=f"penicillinase_{fh}",
            help="سالب: يمكن الاعتماد على Penicillin = S. موجب: يُبلَّغ مقاوماً. CLSI M100.")
    page.aux_tests = current_aux_tests(page.file_hash)
