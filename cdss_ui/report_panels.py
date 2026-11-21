# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Right column: checklist, text report, PDF, summary image.

Each function renders one section of the page.  `page` is the per-run state
shared between sections (see cdss_ui.app.main).
"""
from datetime import datetime
from typing import List
import hashlib
import streamlit as st

from cdss.astqc.final_checklist import ICON as CHECK_ICON
from cdss.astqc.final_checklist import build_final_checklist
from cdss.astqc.final_checklist import summarize as summarize_checklist
from cdss.astqc.inline_qc import run_ast_qc
from cdss.common.optional_deps import PIL_AVAILABLE
from cdss.common.optional_deps import WEASYPRINT_AVAILABLE
from cdss.common.renal import crcl_label
from cdss.common.specimen import classify_specimen
from cdss.common.util import uniq_keep_order
from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.formulary.commercial_names import COMMERCIAL_NAMES
from cdss.health import PANEL_COMPLETENESS_AVAILABLE
from cdss.health import _check_panel_completeness_ext
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.organisms.pathogenicity import gate_suppresses
from cdss.reports.report_service import generate_decision_tree_image
from cdss.reports.report_service import pdf_html_to_bytes
from cdss.reports.html_utils import caution_label, top_option_line
from cdss_ui.release_gate import reports_blocked
from cdss.stewardship.ranking import rank_sensitive_antibiotics, route_label
from cdss_ui.state import current_patho_result


def prepare_report_inputs(page):
    """Lists and labels shared by the text report, the PDF and the image."""
    st.divider()

    # مصدر الترتيب الموحّد — يُحسب هنا لضمان توفره بغضّ النظر عن أي
    # حساب سابق مشروط (كان يُعرّف داخل expander منفصل → NameError محتمل).
    ranked = rank_sensitive_antibiotics(
        page.allowed, page.culture_type, page.organism_type, page.sir_map, page.phenotypes,
        carbapenemase_type=getattr(page, "_carb_type_now", None),
        uti_syndrome=getattr(page, "_uti_syn_now", None),
    )
    # v7.2 (second external review): a "do not treat" verdict withholds the
    # treatment lists from the image too (the AST and the "avoid" list stay).
    _gate = getattr(page, "treatment_gate", None)
    _withheld = gate_suppresses(_gate)
    if _withheld:
        ranked = []

    # بناء قوائم الصورة
    page.reserve_names = uniq_keep_order([
        item['name'] for item in (page.allowed + page.warned)
        if item.get("aware") == "Reserve"
    ])
    # مصدر ترتيب واحد موحّد: نفس ترتيب rank_sensitive_antibiotics
    # (الحساسية أولاً ثم العينة ثم AWaRe ثم الطريق) — نستبعد الـ Reserve
    # من قائمة الـ PREFERRED فقط (تظهر منفصلة كـ Reserve).
    preferred_sorted = [
        item for item in ranked if item.get("aware") != "Reserve"
    ]
    preferred_names = [item['name'] for item in preferred_sorted]
    # للصورة: نضيف badge [A] أو [W] بجانب الاسم
    # v7.0 (review 2026-11-19): the column was titled "Preferred oral options"
    # and listed gentamicin IV/IM. It is the ranked list for this site; each
    # entry now carries its route next to the AWaRe tag.
    def _img_pref(item):
        _aw = {"Access": "A", "Watch": "W", "Not Recommended": "NR"}.get(item.get("aware"), "")
        _rt = "PO" if route_label(item, page.culture_type) == "PO" else "IV"
        return f"{item['name']} [{_aw + ' · ' if _aw else ''}{_rt}]"
    page.preferred_with_badge = [_img_pref(item) for item in preferred_sorted]
    # النقطة ٣: use_caution يشمل warned + preg_warn
    preg_caution_names = [item['name'] for item in page.preg_warn_items]
    # v7.0: each caution carries WHY (the column was a bare list of names).
    # v7.9: the labels live in cdss.reports.html_utils (tested without the UI).
    def _caution(item):
        return caution_label(item, page.organism_type, page.sir_map,
                             getattr(page, "sdd_drugs", None) or ())
    page.use_caution_names  = uniq_keep_order(
        [_caution(item) for item in page.warned if item['name'] not in page.reserve_names]
        + preg_caution_names
    )
    if _withheld:
        page.reserve_names = []
        page.use_caution_names = []
    # Build banned names WITH reason tag for the image (same logic as PDF)
    _esbl_prob_img    = page.esbl_result.get("probability","low") if page.esbl_result else "low"
    _img_esbl_like    = _esbl_prob_img in ("high","ampc")
    _img_carbapenemase= _esbl_prob_img == "carbapenemase"
    _img_mrsa         = any("MRSA" in str(p.get("phenotype","")).upper() for p in (page.phenotypes or [])) \
                        or "mrsa" in page.organism_type.lower()
    def _img_ban_tag(bd):
        cat = bd.get("category",""); nm = bd.get("name","")
        _s = page.sir_map.get(nm,"")
        _cl = (ABX_GUIDELINES.get(nm,{}).get("class","") or "").lower()
        if cat == "resistant" or _s == "R":         return "(R)"
        if cat == "pregnancy":                       return "(Pregnancy)"
        if cat in ("child","pediatric"):             return "(Pediatric)"
        if cat == "renal":                           return "(Renal)"
        if cat == "organism":
            # v7.0: aztreonam (a monobactam) is hydrolysed by ESBLs -- it was
            # tagged "(Intrinsic R)" for an ESBL Klebsiella.
            _bl = any(k in _cl for k in ("penicillin","cephalosporin","carbapenem","monobactam",
                                         "beta-lactam","β-lactam"))
            if _img_mrsa and _bl:          return "(MRSA)"
            if _img_carbapenemase and _bl: return "(Carbapenemase)"
            if _img_esbl_like and _bl:     return "(ESBL)"
            if "intrinsic" in str(bd.get("reason_short","") + bd.get("reason_detail","")).lower():
                return "(Intrinsic R)"
            return "(Organism)"
        return {"uti_upper": "(Cystitis only)", "no_breakpoint": "(No breakpoint)",
                "specimen": "(Site)", "safety_gate": "(Site / host)", "hepatic": "(Hepatic)",
                "allergy": "(Allergy)", "neonate": "(Neonate)", "cross_resistance": "(Cross-R)",
                "interaction": "(Interaction)", "intrinsic": "(Intrinsic R)"}.get(cat, "(Avoid)")
    _seen_ban = set()
    page.banned_names = []
    # v7.4 (case review): a tested-S agent not appropriate here keeps its S and comes first.
    _ban_sorted = sorted(page.banned, key=lambda b: 0 if page.sir_map.get(b.get("name", "")) == "S" else 1)
    for item in _ban_sorted:
        nm = item.get("name","")
        if nm and nm not in _seen_ban:
            _seen_ban.add(nm)
            _tg = _img_ban_tag(item)
            if page.sir_map.get(nm) == "S" and _tg.startswith("("):
                _tg = "(S · " + _tg[1:]
            page.banned_names.append(f"{nm} {_tg}")
    org_profile    = ORGANISM_PROFILE.get(page.organism_type, {})
    # الـ first-line في ORGANISM_PROFILE قائمة عامة للميكروب وغير مفلترة
    # بنتيجة المزرعة — قد تحتوي دواءً مقاوماً في هذه العينة. نُبقي فقط
    # الأدوية التي اجتازت فلتر الحساسية فعلاً (موجودة في allowed غير الـ R)،
    # وبنفس ترتيب rank_sensitive_antibiotics. إن لم يتبقَّ شيء نترك القائمة
    # فارغة (لا نعرض first-line مقاوماً).
    _profile_fl    = org_profile.get("first_line", []) or []
    _allowed_names = {it.get("name", "") for it in page.allowed}
    _ranked_names  = [it.get("name", "") for it in ranked]
    page.first_line_l   = [
        d for d in _ranked_names
        if d in _profile_fl and d in _allowed_names
    ]
    # v6.6: a guideline order for this mechanism and site outranks the organism's
    # generic first-line list (same rule as the PDF's FIRST-LINE tier).
    _guide_fl = [it.get("name", "") for it in ranked if it.get("_guideline_preferred")]
    if _guide_fl:
        page.first_line_l = _guide_fl
    # v7.0 (review 2026-11-19): the CLINICAL STRATEGY box printed "--" whenever
    # no generic first-line agent survived. It now says what to DO: the agent
    # (and whether it is a guideline alternative), the tests another result
    # requires, and the case facts that change management.
    page.strategy_l = [f"First-line: {', '.join(page.first_line_l[:2])}"] if page.first_line_l else []
    if _withheld:
        page.strategy_l = [f"NO ANTIBIOTIC: {_gate['short_en']}"]
    elif _gate:
        page.strategy_l.insert(0, "Physician override: treat despite " + _gate["short_en"])
    if not page.first_line_l and ranked:
        _top = ranked[0]
        _rt = "PO" if route_label(_top, page.culture_type) == "PO" else "IV"
        page.strategy_l.append(top_option_line(
            _top.get('name', ''), _rt,
            guideline_alternative=bool(_top.get('_guideline_alternative'))))
    try:
        from cdss.astqc.phenotype_plausibility import check_plausibility as _cp
        _pl = _cp(page.organism_type, page.sir_map, getattr(page, "sdd_drugs", None))
    except Exception:
        _pl = []
    if any(f["id"].startswith("PL1") for f in _pl):
        page.strategy_l.append("Verify ID + AST (implausible phenotype)")
    _reflex = [r for f in _pl for r in (f.get("reflex") or [])
               if not r.startswith("MIC:") and r not in (page.sir_map or {})]
    if _reflex:
        _short = {"Carbapenemase test (mCIM / eCIM)": "mCIM/eCIM",
                  "Species ID test (MALDI-TOF / biochemical)": "species ID"}
        page.strategy_l.append("Test now: " + ", ".join(dict.fromkeys(_short.get(r, r) for r in _reflex)))
    _case = getattr(page, "case", None)
    if _case is not None and _case.is_urine and _case.is_cath:
        page.strategy_l.append("Replace catheter (>= 2 wk) + re-culture")
    if (_case is not None and _case.low_muscle_mass and not page.is_renal
            and any(it.get("tdm_note") for it in page.allowed + page.warned)):
        page.strategy_l.append("Low muscle mass: eGFR may overestimate - cystatin C / "
                               "measured GFR; TDM for aminoglycoside dosing")

    page.notes: List[str] = []
    from cdss.common.data_consistency import report_lines_en      # v7.4: report vs case
    page.notes.extend(report_lines_en(getattr(page, "data_issues", None)))
    if getattr(page, "uti_note", ""):
        page.notes.append(page.uti_note)
    if _withheld:
        page.notes.append(f"No antibiotic treatment indicated -- {_gate['reason_en']}")
    elif _gate:
        page.notes.append(f"Shown at the physician's request although: {_gate['reason_en']}")
    if page.is_renal:
        page.notes.append(f"Renal impairment: CrCl {crcl_label(page.cl_cr, page.is_renal)} "
                     f"-- dose adjustment required.")
    if page.is_preg:
        page.notes.append("Pregnancy: use with caution; consult specialist.")
    if page.age < 18:
        page.notes.append("Pediatric age: verify age-specific suitability.")
    if page.banned:
        page.notes.append(f"{len(page.banned)} contraindicated / ineffective antibiotics.")
    if page.warned:
        page.notes.append(f"{len(page.warned)} antibiotics need caution or dose adjustment.")
    if not _withheld:
        page.notes.append("Treatment guided by severity and local resistance patterns.")
        page.notes.append("De-escalate based on culture & sensitivity.")


def render_final_checklist(page):
    """Final verification checklist."""
    # ── Final verification checklist (2026-11-11) ───────────────────
    # One line per question a reviewer asks before release. Nothing
    # here decides anything new -- it re-checks what the engine did.
    st.markdown("### ✅ قائمة المراجعة النهائية")
    _is_urine_ck = classify_specimen(page.culture_type) == "urine"
    _gram_ck = st.session_state.get("patho_gram_sel" if _is_urine_ck else "np_gram_sel", "")
    _panel_ck = None
    if PANEL_COMPLETENESS_AVAILABLE and _check_panel_completeness_ext and page.sir_map:
        try:
            _panel_ck = _check_panel_completeness_ext(page.organism_type, page.culture_type, page.sir_map)
        except Exception:
            _panel_ck = None
    _ck_items = build_final_checklist(
        page.organism_type, page.culture_type, page.sir_map,
        allowed=page.allowed, warned=page.warned, banned=page.banned,
        qc_issues=(run_ast_qc(page.organism_type, page.sir_map, specimen=page.culture_type,
                               sdd=getattr(page, "sdd_drugs", None))
                   if page.sir_map else []),
        gram_stain=_gram_ck,
        patho_result=current_patho_result(),
        panel_result=_panel_ck,
        preg_warn=page.preg_warn_items,
    )
    # v7.6: the whole-case validation (analysis + text + PDF + image) was done by
    # prepare_release() before this checklist; it is shown here, not recomputed.
    from cdss.validation.case_validator import checklist_item
    # None = did not run; [] = ran clean (v7.6 sweep: "x or [V00]" read a clean [] as "did not run")
    _ck_items.append(checklist_item(getattr(page, "validation", None)))
    _ck_sum = summarize_checklist(_ck_items)
    for _ck in _ck_items:
        _line = f"{CHECK_ICON[_ck['status']]} **{_ck['title']}** — {_ck['detail']}"
        if _ck["status"] == "fail":
            st.error(_line)
        elif _ck["status"] == "warn":
            st.warning(_line)
        elif _ck["status"] == "pass":
            st.success(_line)
        else:
            st.caption(_line)
    if _ck_sum["overall"] == "fail":
        st.error(f"❌ {_ck_sum['counts']['fail']} بند يحتاج مراجعة قبل إصدار التقرير.")
    elif _ck_sum["overall"] == "warn":
        st.warning(f"⚠️ لا أخطاء — {_ck_sum['counts']['warn']} بند يحتاج انتباه.")
    else:
        st.success("✅ كل بنود المراجعة سليمة.")
    st.divider()


def render_text_report(page):
    """Clinical text report."""
    if reports_blocked(page, "التقرير النصي"):
        return
    # ── Commercial Names Toggle ────────────────────────────────────────
    page.show_commercial = st.checkbox(
        "📋 إضافة الأسماء التجارية (Commercial Names) في التقرير؟",
        value=st.session_state.get("show_commercial_names", False),
        key="show_commercial_chk",
        help="يضيف أسماء العلامات التجارية بجانب كل مضاد حيوي في ملف TXT فقط"
    )
    st.session_state.show_commercial_names = page.show_commercial
    if page.show_commercial and not COMMERCIAL_NAMES:
        st.warning("⚠️ ملف `commercial_names.txt` غير موجود في مجلد البرنامج.")
    elif page.show_commercial:
        st.caption(f"✅ {len(COMMERCIAL_NAMES)} دواء مسجّل في قاموس الأسماء التجارية")

    # ── التقرير النصي -- cached to prevent lag on every keystroke ──────
    st.markdown("### 📋 التقرير السريري")

    # v7.6: built and validated with every other export by prepare_release()
    auto_report = (getattr(page, "release", None) or {}).get("text", "")

    # معاينة للقراءة فقط
    if auto_report:
        st.text_area(
            "نص التقرير",
            value=auto_report,
            height=300,
            disabled=True,
            label_visibility="collapsed",
            key=f"rpt_{page._rpt_input_hash}"
        )
        st.download_button(
            "📥 تنزيل التقرير (TXT)",
            data=auto_report,
            file_name=(f"CDSS_{page.organism_type.replace(' ','_')}_"
                       f"{page._pt.replace(' ','_')[:12]}_"
                       f"{datetime.now().strftime('%Y%m%d_%H%M')}.txt"),
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )


def render_pdf_export(page):
    """PDF report."""
    if reports_blocked(page, "تقرير الـ PDF"):
        return
    # ── PDF Report ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📄 PDF Clinical Report")

    _pdf_lang_col, _popt1, _popt2, _popt3 = st.columns([2,1,1,1])
    _pdf_lang  = _pdf_lang_col.radio(
        "Report Language",
        options=["ar", "en"],
        format_func=lambda x: "🌐 Arabic + English (Bilingual)" if x == "ar"
                              else "🇬🇧 English Only",
        index=["ar","en"].index(st.session_state.get("pdf_lang","ar")),
        horizontal=True,
        key="pdf_lang_radio",
    )
    st.session_state.pdf_lang = _pdf_lang
    _pdf_combo = _popt1.checkbox("Combination",
        value=st.session_state.get("pdf_include_combo",True), key="pdf_cb_combo")
    _pdf_dur   = _popt2.checkbox("Duration",
        value=st.session_state.get("pdf_include_duration",True), key="pdf_cb_dur")
    _pdf_patho = _popt3.checkbox("Pathogenicity",
        value=st.session_state.get("pdf_include_patho",True), key="pdf_cb_patho")
    st.session_state.pdf_include_combo    = _pdf_combo
    st.session_state.pdf_include_duration = _pdf_dur
    st.session_state.pdf_include_patho    = _pdf_patho

    if WEASYPRINT_AVAILABLE:
        _cp_pdf  = st.session_state.get("child_pugh_class", "A")
        _sev_pdf = st.session_state.get("severity_level", "moderate")
        _lang_lbl = "English Only" if _pdf_lang == "en" else "Arabic + English"

        # FIX (#R2): input signature for the PDF so a stale PDF is never
        # offered for download after inputs change. Reuses the report hash
        # (identical clinical inputs) + PDF-specific toggles/options. The
        # '_pdf_hash' session slot existed but was never wired -> a PDF
        # generated for one patient/organism could be downloaded after the
        # inputs (and thus the filename) had already changed.
        _pdf_sig = (f"{page._rpt_input_hash}|{_pdf_lang}|{_pdf_combo}|{_pdf_dur}"
                    f"|{_pdf_patho}|{_cp_pdf}|{_sev_pdf}")

        if st.button(f"🔄 Generate PDF ({_lang_lbl})", key="gen_pdf_btn",
                     use_container_width=True,
                     help="Click to generate report -- takes a few seconds"):
            # v7.6: the file is made from the HTML prepare_release() validated
            # for these exact options -- never from a second, unchecked build.
            _rel = getattr(page, "release", None) or {}
            if _rel.get("pdf_sig") != _pdf_sig:
                st.error("🛑 خيارات الـ PDF اتغيّرت بعد الفحص — أعد المحاولة.")
                return
            with st.spinner("جاري توليد التقرير PDF..."):
                try:
                    _new_pdf = _rel.get("pdf_html") or None
                    _new_pdf = pdf_html_to_bytes(_new_pdf) if _new_pdf else None
                    if _new_pdf:
                        st.session_state._pdf_bytes = _new_pdf
                        st.session_state._pdf_lang_used = _pdf_lang
                        st.session_state._pdf_hash = _pdf_sig
                        st.success("✅ PDF ready -- click download below")
                    else:
                        st.error("فشل توليد PDF -- تحقق من تثبيت weasyprint")
                except Exception as _pdf_err:
                    st.error(f"خطأ في توليد PDF: {_pdf_err}")

        # Download button -- only when the cached PDF matches current inputs
        if (st.session_state.get("_pdf_bytes")
                and st.session_state.get("_pdf_hash") == _pdf_sig):
            _lang_suffix = "EN" if st.session_state.get("_pdf_lang_used") == "en" else "AR_EN"
            st.download_button(
                f"📄 Download PDF ({_lang_suffix})",
                data=st.session_state._pdf_bytes,
                file_name=(f"CDSS_{page.organism_type.replace(' ','_')}_"
                           f"{page._pt.replace(' ','_')[:12]}_"
                           f"{_lang_suffix}_"
                           f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"),
                mime="application/pdf",
                use_container_width=True,
                type="secondary",
            )
        elif st.session_state.get("_pdf_bytes"):
            st.info("🔄 تغيّرت البيانات بعد آخر توليد للـ PDF — اضغط "
                    "**Generate PDF** لإصدار نسخة محدّثة مطابقة للبيانات الحالية.")
    else:
        st.info("أضف `weasyprint` إلى requirements.txt لتفعيل تصدير PDF")


def render_summary_image(page):
    """Summary image (decision tree)."""
    if reports_blocked(page, "صورة الملخص"):
        return
    # ── صورة الملخص ──────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🖼️ صورة ملخص الحالة")
    st.caption("تتحدث فوراً عند أي تغيير في البيانات")

    if PIL_AVAILABLE:
        # Hash-based cache: only regenerate when the DRAWN content changes.
        # Signatures below use actual content, not counts / wrong keys:
        #   • mdr_result -> 'level' (classify_mdr never returns
        #     'classification', so the old key was always empty),
        #   • phenotypes & esbl -> by content, not len,
        #   • the drug lists -> by content, not len (two different lists of
        #     equal length must produce different hashes),
        #   • referring physician / culture condition / microbiologist are
        #     drawn on the image but were previously absent from the hash.
        # weight is intentionally NOT hashed: it is passed to the drawing
        # function but never rendered, so hashing it would regenerate the
        # image on every weight keystroke for zero visual change.
        _ph_sig    = "/".join(sorted(p.get("phenotype", "") for p in (page.phenotypes or [])))
        _esbl_sig  = (f"{(page.esbl_result or {}).get('probability','')}"
                      f":{(page.esbl_result or {}).get('mechanism','')}")
        _lists_sig = "|".join([
            ",".join(page.first_line_l), ",".join(page.strategy_l),
            ",".join(page.preferred_with_badge),
            ",".join(page.use_caution_names),
            ",".join(page.banned_names),
            ",".join(page.reserve_names),
            ",".join(page.notes),
        ])
        _img_input_hash = hashlib.md5(
            f"{page.patient_name}|{page.age}|{page.age_months}|{page.sex}|{page.weight}|{page.cl_cr}|{page.is_renal}|{page.is_preg}"
            f"|{page.organism_type}|{page.culture_type}|{page.colony_count}|{page.date_in}"
            f"|{page.pus_cells_text}|{page.rbcs_text}|{str(sorted(page.sir_map.items()))}"
            f"|{_lists_sig}"
            f"|{page.mdr_result.get('level','')}|{_ph_sig}|{_esbl_sig}"
            f"|{getattr(page, '_carb_type_now', None)}"
            f"|{st.session_state.get('lab_name','')}|{st.session_state.get('lab_city','')}"
            f"|{st.session_state.get('referring_physician','')}"
            f"|{st.session_state.get('culture_condition','Aerobic')}"
            f"|{st.session_state.get('microbiologist','')}"
            f"|{page.is_hepatic}|{getattr(page, 'case', None)!r}"
            f"|{page.mdr_result.get('provisional', False)}"
            f"|{sorted((getattr(page, 'aux_tests', None) or {}).items())}"
            .encode()
        ).hexdigest()[:16]

        if (st.session_state.get("_img_hash") != _img_input_hash
                or not st.session_state.get("_img_bytes")
                or st.session_state.get("_img_error")):
            try:
                _new_img = generate_decision_tree_image(
                    patient_name=page.patient_name.strip() or "غير محدد",
                    age=page.age, age_months=page.age_months, sex=page.sex, weight=page.weight,
                    cl_cr=page.cl_cr, is_renal=page.is_renal, is_preg=page.is_preg,
                    organism=page.organism_type, specimen=page.culture_type,
                    first_line=page.strategy_l or page.first_line_l,
                    preferred=page.preferred_with_badge,
                    use_caution=page.use_caution_names,
                    contraindicated=page.banned_names,
                    reserve=page.reserve_names,
                    notes=page.notes,
                    colony_count=page.colony_count,
                    date_in=str(page.date_in),
                    pus_cells=page.pus_cells_text,
                    rbcs=page.rbcs_text,
                    lab_name=st.session_state.get("lab_name", "Your Lab Name"),
                    lab_city=st.session_state.get("lab_city", ""),
                    mdr_result=page.mdr_result,
                    esbl_result=page.esbl_result,
                    phenotypes=page.phenotypes,
                    referring_physician=st.session_state.get("referring_physician",""),
                    culture_condition=st.session_state.get("culture_condition","Aerobic"),
                    microbiologist=st.session_state.get("microbiologist",""),
                    sir_map=page.sir_map, is_hepatic=page.is_hepatic,
                    case=getattr(page, "case", None),
                    carbapenemase_type=getattr(page, "_carb_type_now", None),
                    aux_tests=getattr(page, "aux_tests", None),
                )
                st.session_state._img_bytes = _new_img
                st.session_state._img_hash  = _img_input_hash
                st.session_state._img_error = False
            except Exception as _img_err:
                st.error(f"خطأ في توليد الصورة: {_img_err}")
                st.session_state._img_error = True

        img_bytes = st.session_state.get("_img_bytes")
        if img_bytes:
            st.image(img_bytes,
                     caption=f"Microbiology CDSS | {page.patient_name.strip() or page.organism_type} | {str(page.date_in)}",
                     use_container_width=True)

            # أزرار التنزيل والطباعة
            dl_col, pr_col = st.columns(2)
            with dl_col:
                st.download_button(
                    "📥 تنزيل الصورة (PNG -- Ultra HD)",
                    data=img_bytes,
                    file_name=f"Orange_ClinicalTree_{page.organism_type.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with pr_col:
                # زر الطباعة: يفتح الصورة في tab جديد -> Ctrl+P للطباعة
                import base64 as _b64
                b64 = _b64.b64encode(img_bytes).decode()
                # نستخدم <a> بدل button لأن Streamlit يحجب onclick
                print_html = f'<a href="data:image/png;base64,{b64}" target="_blank" style="display:block;text-align:center;padding:0.45rem 1rem;background:#1B4F9E;color:white;border-radius:8px;font-size:0.95rem;font-weight:600;text-decoration:none;line-height:2;">🖨️ فتح للطباعة (Ctrl+P)</a>' 
                st.markdown(print_html, unsafe_allow_html=True)
                st.caption("افتح الرابط ← Ctrl+P أو ⌘+P للطباعة")

    else:
        st.warning("⚠️ أضف `Pillow` لـ requirements.txt لتفعيل صورة الملخص.")
