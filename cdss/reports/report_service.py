# -*- coding: utf-8 -*-
# © Dr. Hussein Ali — Orange Lab, 6 October City, Egypt
# Microbiology CDSS — All Rights Reserved
"""report_service.py — the three renderers: PDF, decision-tree image, text report.

WHY THIS FILE EXISTS
1,852 lines — a fifth of streamlit_app.py — spent on turning a finished analysis
into something a clinician can hold. It is presentation code with no clinical
decisions in it, and it was sitting in the same file as the decision engine,
which is how the render-layer defects of 2026-08-03 survived so long: every
safety-gate move printing a BLANK reason, and every hepatic or neonatal warning
printing RENAL dosing text instead of its own.

WHY IT IS WIRED RATHER THAN IMPORTED
These renderers need thirty-seven names from the monolith — classify_mdr,
predict_esbl, rank_sensitive_antibiotics, the AWaRe tables, the PIL and
WeasyPrint availability flags, the Arabic reshaper. A plain
`from streamlit_app import ...` would be circular: streamlit_app imports this
module, so this module cannot import it at load time.

The alternative was to rewrite 1,852 lines to reference an accessor object, and
rewriting that much working presentation code to achieve a tidier import graph
is a bad trade — the last time a bulk text edit ran across this codebase it put
a keyword argument on a function that did not accept it and no suite noticed.

So the dependency is INJECTED once, explicitly, by bind() below. The moved code
is byte-for-byte what it was. If a name is missing, bind() raises immediately at
import time with the name in the message, rather than failing later inside a PDF
render where the traceback would be forty frames deep.

WHAT LIVES HERE
    generate_pdf_html_report()      the full clinical PDF (WeasyPrint)
    generate_decision_tree_image()  the decision-tree PNG (Pillow)
    generate_report()               the plain-text report

SPLIT v6.7 (2026-11-14)
    The PDF function was 1,000 lines in which every section shared every
    local. Its sections are now functions in pdf_sections.py (each takes, by
    keyword, exactly what it reads), its style / fixed strings / helpers are in
    pdf_parts.py, the English translation tables in i18n_en.py, and the image's
    palette and drawing helpers in image_parts.py. The bodies moved verbatim;
    tests/test_report_split.py holds the output to the pre-split bytes.

None of them decides anything. They receive `allowed`, `warned`, `banned` and
the rest already computed by run_analysis(), and they must never re-derive a
clinical verdict — if a renderer disagrees with the engine, the renderer is
wrong by construction.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from cdss.common.optional_deps import (
    Image,
    ImageDraw,
    PIL_AVAILABLE,
    WEASYPRINT_AVAILABLE,
    _wp,
)
from cdss.common.renal import (
    crcl_label,
    get_renal_severity,
    resolve_crcl,
)
from cdss.formulary.commercial_names import (
    get_commercial_name,
)
from cdss.reports.image_parts import (  # noqa: F401 -- the image's palette and drawing helpers
    ALERT_BD,
    ALERT_BG,
    ALERT_TXT,
    AMBER_BD,
    AMBER_BG,
    AMBER_TXT,
    AWARE_NAME_COLORS,
    BG,
    BLUE_BD,
    BLUE_BG,
    BLUE_TXT,
    DARK,
    FL_BD,
    FL_BG,
    FOOT_BD,
    FOOT_BG,
    GRAY,
    GREEN_BD,
    GREEN_BG,
    GREEN_TXT,
    LIGHT_GRAY,
    MICRO_BD,
    MICRO_BG,
    NAVY,
    PURPLE_BD,
    PURPLE_BG,
    RED_BD,
    RED_BG,
    RED_TXT,
    SPEC_BD,
    SPEC_BG,
    WHITE,
    _fix_arabic,
    guard_draw,
    fh,
    gf,
    rbox,
    section_box,
    text_wrap,
    tw,
    S as _IMG_S,
)
from cdss.reports.pdf_parts import (
    AWARE_CARD,
    AWARE_CLR,
    AWARE_PILL,
    PDF_CSS,
    SPECIMEN_SHORT,
    clip,
    header_html,
    join_more,
    pdf_strings,
    pill,
    renal_note_text,
    xlate_patho,
    xlate_preg_note,
)
from cdss.reports.pdf_sections import (
    section_avoid,
    section_columns,
    section_combo_hepatic_footer,
    section_interactions,
    section_pregnancy,
    section_ranked,
    section_warned,
)
from cdss.reports.pdf_parts import section_treatment_gate
from cdss.reports.fonts import with_bundled_fonts
from cdss.reports.html_utils import (
    _esc,
    pdf_glyph_guard,
)
from cdss.resistance.mdr import (
    MDR_INFO,
    mdr_display_label,
    physician_mdr_categories,
    physician_mdr_label,
    physician_mdr_level,
    classify_mdr,
)
from cdss.resistance.mechanism import (
    predict_esbl,
)
from cdss.stewardship.ranking import (
    rank_sensitive_antibiotics,
)
from cdss.therapy.notes import (
    warned_note_for,
)
from cdss.therapy.panel_filters import (
    _drop_tested_ns,
    _hide_urine_only,
)
from cdss.therapy.tables import (
    RENAL_BAN_REASONS,
    preg_status_of,
)
from cdss.common.case_context import LOW_MUSCLE_CRCL_NOTE_EN, TDM_AGENTS  # noqa: F401
from cdss.organisms.pathogenicity import gate_suppresses
from cdss.organisms.organism_profile import ORGANISM_PROFILE

# AST Panel Completeness -- a standalone module (like ast_reportability.py),
# not part of the monolith, so it is imported directly rather than through
# bind() below. Optional: absence must never break report generation, only
# silently drop this one section.
try:
    from cdss.astqc.ast_panel_completeness import check_panel_completeness as _check_panel_completeness_ext
    _PANEL_COMPLETENESS_AVAILABLE = True
except Exception:
    _check_panel_completeness_ext = None
    _PANEL_COMPLETENESS_AVAILABLE = False


def generate_pdf_html_report(
    patient_name: str, age: int, sex: str, weight: float,
    cl_cr: float, is_renal: bool, is_preg: bool, is_hepatic: bool,
    allowed: List[Dict], warned: List[Dict], banned: List[Dict],
    preg_warn_items: List[Dict], organism: str, specimen: str,
    sir_map: Dict[str, str], interactions: List[str],
    mdr_result: Dict, esbl_result: Dict, phenotypes: List[Dict],
    colony_count: str = "", date_in: str = "", pus_cells: str = "",
    rbcs: str = "", lab_name: str = "Your Lab Name", lab_city: str = "",
    patho_assessment: dict = None, duration_data: dict = None,
    combo_suggestions: list = None, show_commercial_names: bool = False,
    child_pugh: str = "", hepatic_recs: list = None,
    lang: str = "ar",
    return_html: bool = False,
    carbapenemase_type: Optional[str] = None,
    uti_syndrome: Optional[str] = None,
    treatment_gate: Optional[Dict[str, Any]] = None,
) -> Optional[bytes]:
    # `return_html` exists so this document can be INSPECTED without WeasyPrint.
    # Added 2026-08-03: the function returns rendered bytes, so in any
    # environment without the renderer it returned None and the entire PDF
    # layer — 1,000 lines of it — was untestable. That is how the wrong-note
    # defect survived here after being fixed on screen the same day: no test
    # could read what the PDF actually said.
    if return_html:
        WEASYPRINT_REQUIRED = False
    elif not WEASYPRINT_AVAILABLE:
        return None

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Language helpers ─────────────────────────────────────────────────
    _EN = lang == "en"

    _T = pdf_strings(_EN)

    def _xlate_preg_note(note: str) -> str:
        return xlate_preg_note(note, _EN)

    def _xlate_patho(text: str) -> str:
        return xlate_patho(text, _EN)

    # المصدر الموحّد للترتيب — نفس منطق الشاشة والصورة (الحساسية أولاً ثم
    # العينة ثم AWaRe ثم الطريق)، بدلاً من ترتيب AWaRe منفصل كان يعطي ترتيباً
    # مختلفاً عن الشاشة.
    # Same order as the screen: the guideline step needs the carbapenemase class and
    # the UTI syndrome too (v6.6), or the PDF would list a different first choice.
    ranked   = rank_sensitive_antibiotics(allowed, specimen, organism, sir_map, phenotypes,
                                          carbapenemase_type=carbapenemase_type,
                                          uti_syndrome=uti_syndrome)
    mdr_class = mdr_result.get("level","") if mdr_result else ""
    ph_labels = [p.get("phenotype","") for p in phenotypes]
    esbl_prob = esbl_result.get("probability","low")
    esbl_conf = esbl_result.get("confidence", 0) if esbl_result else 0
    # Header pills must reflect only confirmed/high-confidence findings —
    # weak/fallback inferences (e.g. "Possible MRSA" without Oxacillin/Cefoxitin
    # confirmation) stay in the body detail, not the prominent header badge.
    _WEAK_HEADER_PHENOTYPES = {"Possible MRSA"}
    _hdr_ph_labels = [p for p in ph_labels if p not in _WEAK_HEADER_PHENOTYPES]
    # Flags for Avoid-reason tagging (derived from passed-in results)
    _is_esbl_like     = esbl_prob in ("high", "ampc", "ampc_plasmid")
    _is_carbapenemase = esbl_prob in ("carbapenemase", "possible_carbapenemase")
    _is_mrsa          = any("MRSA" in str(p).upper() for p in ph_labels) \
                        or "mrsa" in str(organism).lower()

    def _rnote(d):
        return renal_note_text(d, is_renal, _EN)

    _join_more = join_more
    _clip = clip
    CSS = PDF_CSS

    specimen_short = SPECIMEN_SHORT.get(specimen, f"{specimen} C/S" if specimen else "")

    def hdr_html(page_lbl: str) -> str:
        return header_html(page_lbl, mdr_class=mdr_class, mdr_result=mdr_result,
                           _hdr_ph_labels=_hdr_ph_labels, esbl_conf=esbl_conf,
                           esbl_prob=esbl_prob, esbl_result=esbl_result, lab_name=lab_name,
                           lab_city=lab_city, specimen_short=specimen_short, date_in=date_in,
                           now_str=now_str, organism=organism)

    # Resolve the footer lab-name token (see P1) -- quotes stripped so the
    # value cannot break out of the CSS content string.
    CSS = CSS.replace(
        "@@LABFOOT@@",
        (lab_name or "").replace('"', "").replace("\\", "")
    )

    H = []
    _doc_title = (
        f"{specimen_short or 'Culture'} Clinical Advisory"
        f" -- {organism or 'isolate'} -- {lab_name or 'Lab'}"
    )
    H.append(f"<!DOCTYPE html><html lang='en' dir='ltr'><head><meta charset='UTF-8'>"
             f"<title>{_esc(_doc_title)}</title>"
             f"<style>{CSS}</style></head><body>")

    # ════════════════════════════════════════════════════════════════
    # SINGLE PAGE: Clinical Decision Support
    # (Page 1 Patient/Culture/AST removed -- CDS only)
    # ════════════════════════════════════════════════════════════════
    H.append(hdr_html("CLINICAL ADVISORY"))
    H.append('<div class="content">')

    # v7.2 (second external review): "do not treat" reaches the PDF.
    _withheld = gate_suppresses(treatment_gate)
    if treatment_gate:
        section_treatment_gate(H=H, _EN=_EN, gate=treatment_gate)
    if _withheld:
        ranked, warned, preg_warn_items = [], [], []
        duration_data, combo_suggestions = None, None

    if not _withheld:
        section_ranked(
            H=H,
            AWARE_CARD=AWARE_CARD,
            AWARE_CLR=AWARE_CLR,
            AWARE_PILL=AWARE_PILL,
            _T=_T,
            _rnote=_rnote,
            is_preg=is_preg,
            is_renal=is_renal,
            lang=lang,
            organism=organism,
            pill=pill,
            preg_warn_items=preg_warn_items,
            ranked=ranked,
            sir_map=sir_map,
            specimen=specimen)

    section_avoid(
        H=H,
        _T=_T,
        _is_carbapenemase=_is_carbapenemase,
        _is_esbl_like=_is_esbl_like,
        _is_mrsa=_is_mrsa,
        banned=banned,
        is_preg=is_preg,
        sir_map=sir_map)

    section_warned(
        H=H,
        _EN=_EN,
        _T=_T,
        _rnote=_rnote,
        cl_cr=cl_cr,
        is_renal=is_renal,
        warned=warned)

    section_interactions(H=H, _EN=_EN, _T=_T, interactions=interactions)

    section_columns(
        H=H,
        _EN=_EN,
        _T=_T,
        _clip=_clip,
        _join_more=_join_more,
        _xlate_patho=_xlate_patho,
        allowed=allowed,
        duration_data=duration_data,
        esbl_result=esbl_result,
        lang=lang,
        mdr_result=mdr_result,
        patho_assessment=patho_assessment,
        phenotypes=phenotypes,
        sir_map=sir_map,
        specimen=specimen,
        treatment_withheld=_withheld)

    section_pregnancy(
        H=H,
        _EN=_EN,
        _T=_T,
        _xlate_preg_note=_xlate_preg_note,
        is_preg=is_preg,
        preg_warn_items=preg_warn_items)

    section_combo_hepatic_footer(
        H=H,
        child_pugh=child_pugh,
        combo_suggestions=combo_suggestions,
        hepatic_recs=hepatic_recs,
        is_hepatic=is_hepatic)

    _full_html = "".join(H)
    if _EN:
        # Final safety net: guarantee a pure-English report by removing any Arabic
        # that escaped phrase-translation (e.g. an organism's Arabic parenthetical
        # like "Anaerobes (لاهوائيات)"), then tidy the artifacts left behind. HTML
        # tags/attributes are ASCII, so only visible text is affected.
        # Arabic ranges, deliberately excluding U+FE00-FE0F: those are emoji
        # variation selectors, not Arabic, and a range like FB50-FEFF swallows
        # them.
        _AR = r'\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF'
        # 1. Parenthetical glosses -- purely Arabic inside brackets. Safe to
        #    drop; this is the case the original net was written for.
        _full_html = re.sub(r'\s*\(\s*[' + _AR + r'\s\u060C\u061B\u061F.,\-]+\s*\)',
                            '', _full_html)
        # 2. Anything still Arabic is running clinical text. Leave it visible
        #    rather than amputating words from a dose instruction. Record it so
        #    QA can see the leak instead of the patient inheriting it.
        _ar_leaks = re.findall(r'[' + _AR + r']+(?:[\s\u060C][' + _AR + r']+)*',
                               _full_html)
        if _ar_leaks:
            try:
                _uniq = sorted(set(t.strip() for t in _ar_leaks if t.strip()))
                logging.warning(
                    "EN report: %d Arabic fragment(s) reached render; "
                    "add an _en field for these: %s",
                    len(_uniq), " | ".join(_uniq[:12])
                )
            except Exception:
                pass
        # 3. 2026-11-11: the guarantee. Steps 1-2 only REPORT a leak; the user
        #    requirement is that an English report never carries an Arabic
        #    word. Any text node that still holds Arabic is replaced whole by
        #    one English sentence -- never trimmed word by word, which is how
        #    "risk of ... less than thought" lost its noun. The leak is still
        #    logged above so the missing _en field gets written.
        _full_html = re.sub(
            r'>([^<>]*[' + _AR + r'][^<>]*)<',
            '>A clinical note for this item is available in the Arabic report.<',
            _full_html)
        _full_html = re.sub(r'\(\s*\)', '', _full_html)      # empty () left by stripping
        _full_html = re.sub(r'[ \t]{2,}', ' ', _full_html)   # collapse doubled spaces
    # Restore the patient name AFTER the Arabic strip: the name is a patient
    # identifier, not clinical prose, so the pure-English rule must not apply to
    # it -- a report with no name is a misidentification hazard, which is worse
    # than an Arabic word on an English page. The placeholder is ASCII, so it
    # survives the strip above unharmed.
    _full_html = _full_html.replace("@@PTNAME@@", _esc(patient_name or "—"))
    try:
        if return_html:
            return pdf_glyph_guard(_full_html)
        # v6.8: the shipped fonts (fonts/) are registered on the way in, so the
        # EXE draws with the same Noto / Amiri / DejaVu files as the online app.
        return _wp.HTML(string=with_bundled_fonts(pdf_glyph_guard(_full_html))).write_pdf()
    except Exception:
        return None



def generate_decision_tree_image(
    patient_name:    str,
    age:             int,
    sex:             str,
    weight:          float,
    cl_cr:           float,
    is_renal:        bool,
    is_preg:         bool,
    organism:        str,
    specimen:        str,
    first_line:      List[str],
    preferred:       List[str],
    use_caution:     List[str],
    contraindicated: List[str],
    reserve:         List[str],
    notes:           List[str],
    colony_count:    str = "",
    date_in:         str = "",
    pus_cells:       str = "",
    rbcs:            str = "",
    lab_name:        str = "Your Lab Name",
    lab_city:        str = "",
    mdr_result:          Optional[Dict] = None,
    esbl_result:         Optional[Dict] = None,
    phenotypes:          Optional[List] = None,
    referring_physician: str = "",
    culture_condition:   str = "Aerobic",
    microbiologist:      str = "",
    age_months:          Optional[int] = None,
    sir_map:             Optional[Dict[str, str]] = None,
    is_hepatic:          bool = False,
    case:                Any = None,
    carbapenemase_type:  Optional[str] = None,
) -> bytes:
    # v7.0: `case` is the one record of the case facts (cdss.common.case_context):
    # collection method and host factors reach the image instead of a
    # hard-coded "Mid-Stream" and an unconditional "Renal: Normal".
    sir_map = sir_map or {}
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow غير متاح -- أضف Pillow لـ requirements.txt")

    # ── Scale & Canvas ────────────────────────────────────────────────────────
    # A4 landscape = 297mm × 210mm  @ 200 DPI = 2339 × 1654 px
    # نطرح 10mm من كل جهة -> 277mm × 190mm = 2181 × 1496 px
    # أصغر من A4 بـ ~20mm -> يُطبع بدون قص
    S  = 2                       # 2× scale -> جودة طباعة جيدة
    W  = 2181                    # 277mm @ 200 DPI  (أصغر من A4 بـ 20mm)
    H  = 1496                    # 190mm @ 200 DPI  (أصغر من A4 بـ 20mm)
    P  = 14   * S                # padding
    G  = 8    * S                # gap

    assert S == _IMG_S, "image_parts draws at a different scale"

    F_HEADER  = gf(20, True)
    F_TITLE   = gf(15, True)
    F_SUBTITL = gf(12, True)
    F_TEXT    = gf(12)
    F_SMALL   = gf(10)
    F_ORG     = gf(26, True)
    F_SUMNUM  = gf(20, True)
    F_BADGE   = gf(9,  True)

    # ── Build Image ───────────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), BG)
    draw = guard_draw(ImageDraw.Draw(img))     # v6.8: no empty boxes for emoji

    # ── 1. HEADER ─────────────────────────────────────────────────────────────
    rbox(draw, (P, 6*S, W-P, 62*S), NAVY, NAVY, radius=12, width=1)
    htxt = f"🔬  {lab_name.upper()} – MICROBIOLOGY DEPARTMENT"
    hw   = tw(draw, htxt, F_HEADER)
    draw.text(((W - hw)//2, 16*S), _fix_arabic(htxt), fill=WHITE, font=F_HEADER)

    # ── 2. CULTURE BOX (center) ───────────────────────────────────────────────
    CB = (368*S, 72*S, 870*S, 198*S)
    rbox(draw, CB, WHITE, NAVY, radius=14, width=2)

    ctype = "Culture/ Growth"
    ctw_  = tw(draw, ctype, F_SUBTITL)
    draw.text(((CB[0]+CB[2]-ctw_)//2, CB[1]+12*S), _fix_arabic(ctype), fill=DARK, font=F_SUBTITL)

    ow = tw(draw, organism, F_ORG)
    draw.text(((CB[0]+CB[2]-ow)//2, CB[1]+38*S), _fix_arabic(organism), fill=NAVY, font=F_ORG)

    # Colony count under organism -- Date In inline
    cc_parts = []
    if colony_count:
        cc_parts.append(f"Colony Count: {colony_count}")
    if date_in:
        cc_parts.append(f"Date In: {date_in}")
    if cc_parts:
        cc_txt = "   |   ".join(cc_parts)
        cctw   = tw(draw, cc_txt, F_TEXT)
        draw.text(((CB[0]+CB[2]-cctw)//2, CB[1]+38*S+fh(F_ORG)+6*S),
                  cc_txt, fill=(90, 90, 140), font=F_TEXT)

    # ── 3. PATIENT BOX (left) ─────────────────────────────────────────────────
    PB = (P, 72*S, 358*S, 198*S)
    rbox(draw, PB, PURPLE_BG, PURPLE_BD, radius=14, width=3)
    # No "PATIENT DETAILS" header -- direct fields
    p_lines = []
    if patient_name:
        p_lines.append(f"Patient Name:  {patient_name}")
    _age_lbl = f"{age_months} months" if age_months is not None else f"{age} yrs"
    p_lines.append(f"Sex / Age:     {'Male' if sex == 'Male' else 'Female'}, {_age_lbl}")
    if referring_physician:
        p_lines.append(f"Referred by:   {referring_physician if str(referring_physician).lower().startswith(('dr', 'د')) else 'Dr/ ' + str(referring_physician)}")
    if is_renal:
        _eff, _meas = resolve_crcl(cl_cr, is_renal)
        p_lines.append(
            f"Renal:         IMPAIRED  CrCl:{_eff:.0f}"
            f"{'' if _meas else ' (assumed)'}" if _eff is not None
            else "Renal:         IMPAIRED  CrCl:not measured")
    elif getattr(case, "low_muscle_mass", False):
        # creatinine overestimates GFR in low muscle mass: never a bare "Normal"
        p_lines.append("Renal:         Cr normal* (low muscle mass: use TDM)")
    else:
        p_lines.append("Renal:         Normal")
    p_lines.append(f"Hepatic:       {'IMPAIRED' if is_hepatic else 'Normal'}")
    if sex == "Female" and 12 <= age <= 55:
        p_lines.append(f"Pregnancy:     {'Yes' if is_preg else 'No'}")

    py = 78*S
    for ln in p_lines[:7]:
        draw.text((P+14*S, py), _fix_arabic(f"• {ln}"), fill=DARK, font=F_TEXT)
        py += fh(F_TEXT) + 5*S

    # ── 4. ALERT BOX (right) -- يشمل MDR/ESBL/Phenotype ──────────────────────
    AB = (885*S, 72*S, W-P, 198*S)

    # لون المربع حسب خطورة الـ phenotype
    _ph_names   = [p.get("phenotype","") for p in (phenotypes or [])]
    _has_cre    = any(p in _ph_names for p in ["CRE","CRAB","CRPA"])
    _has_mdr    = (mdr_result or {}).get("level") in ("XDR","PDR")
    _esbl_prob  = (esbl_result or {}).get("probability")
    _esbl_conf_img = int((esbl_result or {}).get("confidence") or 0)
    _has_esbl   = _esbl_prob in ("high", "carbapenemase", "ampc",
                                 "ampc_plasmid", "possible_carbapenemase",
                                 "crpa")

    if _has_cre or _has_mdr:
        AB_BG = (255, 237, 234);  AB_BD = (183, 52, 52);   AB_TXT = (148, 30, 30)
    elif _has_esbl:
        AB_BG = (255, 248, 232);  AB_BD = (205,115, 50);   AB_TXT = (130, 60,  5)
    else:
        AB_BG = ALERT_BG;         AB_BD = ALERT_BD;         AB_TXT = ALERT_TXT

    rbox(draw, AB, AB_BG, AB_BD, radius=14, width=3)

    # عنوان ديناميكي
    if _has_cre:
        alert_title = "🚨 CRE / XDR ALERT"
    elif _has_mdr:
        alert_title = "🔴 MDR/XDR ALERT"
    elif _esbl_prob in ("ampc", "ampc_plasmid"):
        alert_title = "⚠  AmpC ALERT"
    # 2026-11-11 (round 4): these two fell into "ESBL ALERT" -- a P. aeruginosa
    # (never an ESBL call in this engine) with meropenem I, and an isolated
    # ertapenem R, were both headed ESBL on the summary image.
    elif _esbl_prob == "crpa":
        alert_title = "⚠  CR-P. aeruginosa ALERT"
    elif _esbl_prob == "possible_carbapenemase":
        alert_title = "⚠  CARBAPENEMASE SUSPECTED"
    elif _has_esbl:
        alert_title = "⚠  ESBL ALERT"
    else:
        alert_title = "⚠  IMPORTANT ALERT"

    draw.text((AB[0]+12*S, 72*S+12*S), _fix_arabic(alert_title), fill=AB_TXT, font=F_SUBTITL)
    alerts: List[str] = []

    # ── MDR/XDR/PDR ──────────────────────────────────────────────────────────
    mdr_lvl = (mdr_result or {}).get("level")
    if mdr_lvl:
        mdr_cats = (mdr_result or {}).get("resistant_categories", [])
        rc = (mdr_result or {}).get("resistant_count", 0)
        rt = (mdr_result or {}).get("total_tested", 0)
        # v7.0: physician-facing -- provisional XDR prints as MDR; categories
        # name the agents in them that are still S.
        _lvl_txt = physician_mdr_level(mdr_result) or mdr_lvl
        alerts.append(f"{_lvl_txt}: non-susceptible {rc}/{rt} categories")
        if mdr_cats:
            _usable_img = {str(x).split(" [")[0].split(" (")[0] for x in (preferred or []) + (use_caution or [])}
            alerts.append(f"NS-cats: {', '.join(physician_mdr_categories(mdr_result, sir_map, _usable_img)[:3])}")

    # ── ESBL / AmpC / Carbapenemase ────────────────────────────────────────────
    _esbl_mech = (esbl_result or {}).get("mechanism", "")
    if carbapenemase_type:
        # v7.1: a laboratory-confirmed enzyme is stated as such, not as "possible".
        alerts.append(f"Carbapenemase CONFIRMED by the laboratory: {carbapenemase_type}")
        alerts.append("Treat by the enzyme (IDSA AMR Guidance 2026)")
    elif _esbl_prob in ("carbapenemase", "possible_carbapenemase"):
        if "OXA-48" in _esbl_mech:
            alerts.append("Possible OXA-48 carbapenemase")
        else:
            alerts.append("Carbapenemase (KPC/MBL/OXA) possible!")
        alerts.append("Send to reference lab immediately.")
    elif _esbl_prob in ("ampc", "ampc_plasmid"):
        alerts.append("Possible AmpC β-lactamase")
        alerts.append("Avoid 3rd-gen cephalosporins; use Cefepime/Carbapenem")
    elif _esbl_prob == "high":
        alerts.append("ESBL phenotype " + ("highly suggestive" if _esbl_conf_img >= 85 else "suspected")
                      + " (predicted, not confirmed)")
        alerts.append("Use Carbapenems for severe cases")
    elif _esbl_prob == "moderate":
        alerts.append("ESBL confirmation recommended")
        alerts.append("Double Disk Synergy Test")
    elif _esbl_prob == "crpa":
        if (esbl_result or {}).get("dtr_possible"):
            alerts.append("POSSIBLE DTR P. aeruginosa - incomplete panel: test "
                          + ", ".join((esbl_result or {}).get("dtr_untested") or []))
            alerts.append("Ceftolozane-Tazo / Ceftazidime-Avi / Imipenem-Rel / Cefiderocol")
        elif (esbl_result or {}).get("dtr"):
            alerts.append("DTR P. aeruginosa - all first-line agents non-susceptible")
            alerts.append("Ceftolozane-Tazo / Ceftazidime-Avi / Imipenem-Rel / Cefiderocol")
        else:
            alerts.append("Carbapenem-resistant P. aeruginosa - mechanism not determined")
            _abl = (esbl_result or {}).get("active_betalactams") or []
            alerts.append(f"Still susceptible: {', '.join(_abl)} - high-dose extended infusion"
                          if _abl else "Check Ceftazidime / Cefepime / Pip-Tazo before escalating")

    # ── Phenotypes ────────────────────────────────────────────────────────────
    for ph in (phenotypes or [])[:2]:
        ph_name = ph.get("phenotype","")
        if ph_name not in ("Possible MRSA",):
            alerts.append(f"Phenotype: {ph_name}")

    # ── Organism-specific baseline alerts ────────────────────────────────────
    org_l = organism.lower()
    if not alerts:  # فقط لو مفيش MDR/ESBL
        if "aerogenes" in org_l:
            # v6.9: K. aerogenes is an AmpC organism, not a K. pneumoniae.
            alerts += ["Chromosomal AmpC (IDSA 2026)",
                       "Invasive: cefepime, not 3rd-gen ceph."]
        elif "klebsiella" in org_l:
            alerts += ["Consider ESBL screening",
                       "Natural resistance: Ampicillin"]
        elif "e. coli" in org_l or "coli" in org_l:
            alerts += ["Most common UTI pathogen",
                       "Verify with culture sensitivity"]
        elif "pseudomonas" in org_l:
            alerts += ["High intrinsic resistance",
                       "Anti-pseudomonal agent required"]
        elif "mrsa" in org_l or "staphylococcus" in org_l:
            alerts += ["Check MRSA status",
                       "Vancomycin/Linezolid if MRSA"]
        elif "acinetobacter" in org_l:
            alerts += ["MDR risk -- check Carbapenem S/I/R"]
        else:
            alerts = ["Verify sensitivity results."]

    if is_renal:
        _eff, _meas = resolve_crcl(cl_cr, is_renal)
        alerts.append(f"Renal adj. (CrCl {_eff:.0f} ml/min"
                      f"{'' if _meas else ', assumed'})" if _eff is not None
                      else "Renal adj. (CrCl not measured)")
    if is_preg and age >= 18:
        alerts.append("Pregnancy: verify fetal safety")

    ay = 72*S + 12*S + fh(F_SUBTITL) + 8*S
    alert_max_w = AB[2] - AB[0] - 22*S
    for al in alerts[:6]:
        if ay + fh(F_SMALL) + 4*S > AB[3] - 6*S:
            break
        ay = text_wrap(draw, AB[0]+12*S, ay, f"• {al}",
                       F_SMALL, AB_TXT, alert_max_w, gap=4, max_y=AB[3]-6*S)
        ay += 2*S

    # ── 5. ROW 2: Specimen | Microscopic Exam | First-Line ────────────────────
    R2_Y1 = 210*S
    R2_Y2 = 310*S
    r2w   = (W - 2*P - 2*G) // 3

    # Specimen box -- no title, direct fields
    # Specimen label -- add collection method for Urine
    # v7.0: the collection method the user entered (case record) -- this was a
    # hard-coded "Mid-Stream" even for a Foley specimen.
    _spec_label = specimen
    _coll = getattr(case, "collection_label", "") if case is not None else ""
    if _coll:
        _spec_label = f"{specimen} / {_coll}"
    spec_items = [
        f"Specimen:      {_spec_label}",
        "Method:        Culture & Sensitivity",
        f"Condition:     {culture_condition}",
    ]
    if microbiologist:
        spec_items.append(f"Microbiologist: {microbiologist if str(microbiologist).lower().startswith(('dr', 'د')) else 'Dr/ ' + str(microbiologist)}")
    micro_items = [
        f"Pus Cells: {pus_cells if pus_cells else chr(8212)} /HPF",
        f"RBCs:      {rbcs if rbcs else chr(8212)} /HPF",
    ]
    fl_items = first_line[:5] or ["--"]

    r2_data = [
    ("",                   spec_items,  SPEC_BD,  SPEC_BG,  ""),
    ("MICROSCOPIC EXAM",   micro_items, MICRO_BD, MICRO_BG, "🔬"),
    ("CLINICAL STRATEGY",  fl_items,    FL_BD,    FL_BG,    "📋"),
    ]
    for i, (title, items, bd, bg, icon) in enumerate(r2_data):
        bx1 = P + i*(r2w+G)
        bx2 = bx1 + r2w
        rbox(draw, (bx1, R2_Y1, bx2, R2_Y2), bg, bd, radius=12, width=2)
        if title:
            draw.text((bx1+12*S, R2_Y1+9*S), _fix_arabic(f"{icon} {title}"), fill=bd, font=F_SUBTITL)
            iy = R2_Y1 + 32*S
        else:
            iy = R2_Y1 + 11*S  # start higher when no title
        for it in items[:5]:
            iy = text_wrap(draw, bx1+14*S, iy, f"• {it}",
                           F_SMALL, DARK, bx2-bx1-24*S, gap=4, max_y=R2_Y2-6*S)

    # ── 6. FOUR MAIN COLUMNS ──────────────────────────────────────────────────
    COL_Y1 = 323*S
    COL_Y2 = H - 115*S
    cw     = (W - 2*P - 3*G) // 4

    # Dynamic column titles based on pregnancy
    avoid_title    = "🚫 AVOID IN PREGNANCY" if is_preg else "🚫 AVOID / CONTRAINDICT."
    avoid_subtitle = "Contraindicated / Not recommended" if is_preg else "Due to other factors"

    columns = [
        ("✅ PREFERRED (SAFE)",  "Ranked for this site · route shown",  preferred,  GREEN_BD, GREEN_BG, GREEN_TXT),
        ("⚠️  USE WITH CAUTION", "Use with caution",         use_caution,     AMBER_BD, AMBER_BG, AMBER_TXT),
        (avoid_title,            avoid_subtitle,             contraindicated,  RED_BD,   RED_BG,   RED_TXT),
        ("🛡️  RESERVE (WHO)",     "Last-resort agents (MDR/XDR)", reserve,      BLUE_BD,  BLUE_BG,  BLUE_TXT),
    ]
    for i, (title, subtitle, items, bd, bg, tc) in enumerate(columns):
        bx1 = P + i*(cw+G)
        bx2 = bx1 + cw
        section_box(draw, (bx1, COL_Y1, bx2, COL_Y2),
                    title, tc, subtitle, items or ["--"],
                    bg, bd, F_TITLE, F_SMALL, F_TEXT)

    # ── 7. FOOTER -- 4 مربعات متساوية ─────────────────────────────────────────
    FY1 = H - 116*S
    FY2 = H - 8*S
    fw4 = (W - 2*P - 3*G) // 4

    # ① WHO AWaRe
    fx1 = P;  fx2 = fx1 + fw4
    rbox(draw, (fx1, FY1, fx2, FY2), FOOT_BG, FOOT_BD, radius=12, width=2)
    draw.text((fx1+10*S, FY1+10*S), "WHO AWaRe", fill=DARK, font=F_SUBTITL)
    bx = fx1 + 10*S
    by = FY1 + 30*S
    for label, color in [("ACCESS", GREEN_TXT), ("WATCH", AMBER_TXT), ("RESERVE", RED_TXT)]:
        lw      = tw(draw, label, F_BADGE)
        badge_w = int(lw) + 10*S
        rbox(draw, (bx-2*S, by-2*S, bx+badge_w, by+fh(F_BADGE)+4*S),
             color, color, radius=5, width=1)
        draw.text((bx+3*S, by), label, fill=WHITE, font=F_BADGE)
        bx += badge_w + 5*S
    draw.text((fx1+10*S, by+fh(F_BADGE)+7*S),
              "1st/2nd | Caution | Last resort", fill=GRAY, font=F_SMALL)

    # ② SUMMARY
    fx1 = P + fw4 + G;  fx2 = fx1 + fw4
    rbox(draw, (fx1, FY1, fx2, FY2), FOOT_BG, FOOT_BD, radius=12, width=2)
    draw.text((fx1+10*S, FY1+10*S), "SUMMARY", fill=DARK, font=F_SUBTITL)
    sum_items = [
        (f"{len(preferred)}",        "Preferred",   GREEN_TXT),
        (f"{len(use_caution)}",      "Caution",     AMBER_TXT),
        (f"{len(contraindicated)}",  "Avoided",     RED_TXT),
        (f"{len(reserve)}",          "Reserve",     BLUE_TXT),
    ]
    sw = (fx2 - fx1 - 16*S) // 4
    for j, (num, lbl, clr) in enumerate(sum_items):
        sx = fx1 + 10*S + j * sw
        draw.text((sx, FY1+28*S), num, fill=clr,  font=F_SUMNUM)
        draw.text((sx, FY1+62*S), lbl, fill=GRAY, font=F_SMALL)

    # ③ NOTES
    fx1 = P + 2*(fw4+G);  fx2 = fx1 + fw4
    rbox(draw, (fx1, FY1, fx2, FY2), FOOT_BG, FOOT_BD, radius=12, width=2)
    draw.text((fx1+10*S, FY1+10*S), "NOTES", fill=DARK, font=F_SUBTITL)
    ny = FY1 + 30*S
    for note in (notes or [])[:5]:
        if ny + fh(F_SMALL) + 3*S > FY2 - 6*S:
            break
        ny = text_wrap(draw, fx1+10*S, ny, f"• {note}",
                       F_SMALL, DARK, fx2-fx1-18*S, gap=3, max_y=FY2-6*S)

    # ④ REFERENCES
    fx1 = P + 3*(fw4+G);  fx2 = W - P
    rbox(draw, (fx1, FY1, fx2, FY2), FOOT_BG, FOOT_BD, radius=12, width=2)
    draw.text((fx1+10*S, FY1+10*S), "REFERENCES", fill=DARK, font=F_SUBTITL)
    refs = ["CLSI M100 Ed36", "IDSA AMR Guidance 2026", "EUCAST Intrinsic Resistance",
            "WHO AWaRe 2025", "Egypt Nat. Guidelines", "BNF 2025 | FDA Labels"]
    ry = FY1 + 30*S
    for ref in refs:
        if ry + fh(F_SMALL) + 3*S > FY2 - 6*S:
            break
        ry = text_wrap(draw, fx1+10*S, ry, f"• {ref}",
                       F_SMALL, DARK, fx2-fx1-18*S, gap=3, max_y=FY2-6*S)
    # ── Export Ultra HD ───────────────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(200, 200), optimize=False)
    return buf.getvalue()


def _text_pathogenicity(*, L, patho_assessment, sep2):
    """Text report: the pathogenicity block."""
    # ── Pathogenicity Assessment ──────────────────────────────────────
    if patho_assessment:
        sc    = patho_assessment.get("score", 0)
        verd  = patho_assessment.get("verdict", "")
        interp = patho_assessment.get("interpretation", "")
        recs  = patho_assessment.get("recommendations", [])
        flags = patho_assessment.get("special_flags", [])
        L += ["", "PATHOGENICITY ASSESSMENT", sep2,
              f"Evidence : {sc}/100 (strength of evidence, not a probability) -- {verd}"]
        if "ABU_DETECTED" in flags:
            L.append("FLAG     : Asymptomatic Bacteriuria (ABU) Detected")
        if "MW_REJECT" in flags:
            L.append("FLAG     : Murray-Washington -- Specimen REJECTED")
        elif "MW_ADEQUATE" in flags:
            L.append("FLAG     : Murray-Washington -- Adequate Sputum Quality")
        if "SIRS_HIGH" in flags:
            L.append("FLAG     : SIRS >=3 -- marked systemic inflammatory response; "
                     "assess organ dysfunction (Sepsis-3)")
        if interp:
            L.append(f"Interp   : {interp}")
        if recs:
            L.append("Recs     :")
            for r in recs:
                L.append(f"  • {r}")
    return L


def _text_banned(*, L, banned, organism, sep, sep2, specimen):
    """Text report: contraindicated agents with their reasons."""
    if banned:
        L += ["\nCONTRAINDICATED / INEFFECTIVE", sep]
        grouped: Dict[str, list] = {
            "resistant": [], "renal": [], "pregnancy": [],
            "child": [], "organism": [], "specimen": [], "other": [],
        }
        for item in banned:
            grouped.setdefault(item["category"], []).append(item)
        labels = [
            ("resistant", "[A] RESISTANT IN CULTURE"),
            ("renal",     "[B] CONTRAINDICATED -- RENAL IMPAIRMENT"),
            ("pregnancy", "[C] CONTRAINDICATED -- PREGNANCY"),
            ("child",     "[D] NOT SUITABLE FOR AGE"),
            ("organism",  f"[E] INEFFECTIVE FOR {organism}"),
            ("specimen",  f"[F] INAPPROPRIATE FOR {specimen.upper()} SPECIMEN"),
            ("no_breakpoint", "[F2] NO CLSI BREAKPOINT -- RESULT NOT INTERPRETABLE"),
            ("other",     "[G] OTHER CONTRAINDICATIONS"),
        ]
        _rendered_cats = set()
        for cat, heading in labels:
            if grouped.get(cat):
                _rendered_cats.add(cat)
                L += [f"\n{heading}", sep2]
                for b in grouped[cat]:
                    L.append(f"- {b['name']} -- {b.get('reason_short', '')}")
                    if cat == "renal":
                        dk       = b["name"].lower().replace(" ", "")
                        rendered = False
                        for k, v in RENAL_BAN_REASONS.items():
                            if k in dk:
                                L.extend([f"  {ln}" for ln in v.splitlines()])
                                rendered = True
                                break
                        if not rendered:
                            L.extend([f"  {ln}" for ln in (b.get("reason_detail") or "").splitlines()])
                    else:
                        L.extend([f"  {ln}" for ln in (b.get("reason_detail") or "").splitlines()])
                    L.append("")
        # Safety net -- never silently drop a banned drug whose category is not
        # listed above (e.g. a future/unknown category).
        for cat, items in grouped.items():
            if cat in _rendered_cats or not items:
                continue
            L += [f"\n[+] OTHER -- {cat.upper()}", sep2]
            for b in items:
                L.append(f"- {b['name']} -- {b.get('reason_short', '')}")
                L.extend([f"  {ln}" for ln in (b.get("reason_detail") or "").splitlines()])
                L.append("")


def _text_warned(*, L, cl_cr, is_renal, sep, sep2, show_commercial_names, sir_map, warned):
    """Text report: agents to use with caution, with the note that belongs to each."""
    if warned:
        L += ["\nDOSE ADJUSTMENT / USE WITH CAUTION", sep]
        if is_renal:
            L.append(f"Patient CrCl = {crcl_label(cl_cr, is_renal)}\n")
        for item in warned:
            sir_tag = (f" [Culture: {'SDD' if item.get('culture_sdd') else sir_map[item['name']]}]"
                       if sir_map and item['name'] in sir_map else "")
            L += [f"{item['name']}{sir_tag}", sep2, f"WHO AWaRe : {item.get('aware','-')}"]
            # Printed BEFORE the reason branch, not inside it: an Intermediate
            # agent that also needs a renal or hepatic adjustment carries the
            # other reason in warning_reason, and the I used to disappear from
            # this report entirely.
            if (item.get("culture_intermediate")
                    and item.get("warning_reason") != "intermediate_culture"):
                L.append("!! CONFLICT : culture is "
                         + ("SDD (CLSI: susceptible only at a higher-exposure regimen)"
                            if item.get("culture_sdd") else
                            "INTERMEDIATE (CLSI: efficacy only where the drug is concentrated, "
                            "e.g. urine, or at a higher-than-normal dose)")
                         + " while the host requires a REDUCED dose. "
                         "Prefer a fully susceptible agent; if unavoidable, dose with TDM.")
            if item.get("warning_reason") == "intermediate_culture":
                L.append("Reason    : " + ("SDD" if item.get("culture_sdd") else "Intermediate (I)")
                         + " on culture result (CLSI M100)")
                _inote = str(item.get("intermediate_note_en") or "").strip()
                if _inote:
                    L.append("            " + _inote)
            elif item.get("esbl_note") or item.get("esbl_note_en"):
                # Mechanism warnings (ESBL BLI-in-UTI, suspected carbapenemase)
                # carry their reason in esbl_note; without this branch they fell
                # through to renal_note and printed an empty reason.
                L.append("Reason    : " + (item.get("esbl_note_en")
                                           or item.get("esbl_note", "-")))
            elif item.get("warning_reason") in ("renal_adjustment", "", None):
                L += [f"Renal note: {item.get('renal_note','-')}",
                      f"Limit CrCl: <= {item.get('renal_limit','-')} ml/min"]
            else:
                # FIX 2026-11-12 (round 5). Every other reason -- hepatic,
                # safety gate, neonate, possible MRSA, allergy, organism
                # caution -- fell through to the RENAL note above: a Child-Pugh
                # caution or a CSF gate caution printed renal dosing and no
                # reason at all. The PDF and the screen were moved to the one
                # resolver on 2026-08-03; the text report was left behind.
                _why = (warned_note_for(item, "en") if warned_note_for else "") or \
                    str(item.get("note") or "Caution recorded with no explanation — review manually.")
                _wl = [x for x in str(_why).splitlines() if x.strip()]
                L.append("Reason    : " + (_wl[0].strip() if _wl else "-"))
                L.extend("            " + x.strip() for x in _wl[1:])
            if show_commercial_names:
                _brands = get_commercial_name(item["name"])
                if _brands:
                    L.append(f"Brands    : {_brands}")
            L.append("")
    return L


def _text_allowed(
    *, L,
    allowed,
    is_preg,
    is_renal,
    sep2,
    show_commercial_names,
    sir_map,
    specimen,
):
    """Text report: recommended agents in the screen's order."""
    if allowed:
        for item in allowed:
            sir_tag  = f" [Culture: {sir_map[item['name']]}]" if sir_map and item['name'] in sir_map else ""
            preg_tag = " [Pregnancy: caution]" if (is_preg and preg_status_of(item) == "Warn") else ""
            L += [f"\n{item['name']}{sir_tag}{preg_tag}", sep2,
                  f"WHO AWaRe : {item.get('aware','-')}",
                  f"Class     : {item.get('class','-')}",
                  f"Route     : {'Oral/PO-friendly' if item.get('high_po') else 'IV/IM only'}"]
            spec_note = (item.get("specimen_notes") or {}).get(specimen, "")
            if spec_note:
                L += [f"Note      : {item.get('note','')}", f"{specimen}   : {spec_note}"]
            else:
                L.append(f"Note      : {item.get('note','')}")
            if item.get("gate_dose_note_en"):
                L.append(f"Dose      : {item['gate_dose_note_en']}")
            if is_renal:
                L.append(f"Renal     : {item.get('renal_note','-')}")
            if is_preg and preg_status_of(item) == "Warn":
                pn = (item.get("preg_note") or "").splitlines()
                if pn:
                    L.append(f"Pregnancy : {pn[0]}")
            if show_commercial_names:
                _brands = get_commercial_name(item["name"])
                if _brands:
                    L.append(f"Brands    : {_brands}")
    elif is_renal:
        # v7.1: renal dose adjustment is a caution, never a ban -- the agents are
        # listed under CAUTION with their dose; "no options" read as "none usable".
        L.append("No option without a caution: the active agents are listed under CAUTION "
                 "below with their renal dose adjustment - they can be used at that dose.")
    else:
        L.append("No recommended options after applying all restrictions.")


def _text_panel_completeness(*, L, organism, sep2, sir_map, specimen):
    """Text report: AST panel completeness for this organism and specimen."""
    # AST PANEL COMPLETENESS -- added 2026-08-22, request: this belongs in
    # the internal report, not just the interactive Streamlit page. Same
    # question as the UI card: was enough tested at all, not just "was what
    # WAS tested interpreted correctly". Silently absent (not an empty
    # section header) when the module isn't available or the organism has
    # no expected-panel group -- see ast_panel_completeness.py for why
    # staying silent beats guessing for an organism this module doesn't
    # cover confidently.
    if sir_map and _PANEL_COMPLETENESS_AVAILABLE and _check_panel_completeness_ext:
        _pc_report = _check_panel_completeness_ext(organism, specimen, sir_map)
        if _pc_report.status != "not_evaluated":
            L += ["\nAST PANEL COMPLETENESS", sep2,
                  f"Organism : {_pc_report.organism_group}",
                  f"Expected : {_pc_report.expected_total}    "
                  f"Tested: {_pc_report.tested_count}    "
                  f"Missing: {len(_pc_report.missing_primary) + len(_pc_report.missing_supplemental)}"]
            if not (_pc_report.missing_primary or _pc_report.missing_supplemental):
                L.append("Panel adequate -- all expected agents for this organism were tested.")
            else:
                if _pc_report.status == "critical":
                    L.append("!! CRITICAL: every primary agent tested came back Resistant, "
                             "and expected primary agent(s) were never tested. A therapeutic "
                             "option may exist among the untested agents -- this panel cannot "
                             "rule that out. Do not report 'no susceptible options' from an "
                             "incomplete panel.")
                if _pc_report.missing_primary:
                    L.append("Missing (primary)     : " + ", ".join(_pc_report.missing_primary))
                if _pc_report.missing_supplemental:
                    L.append("Missing (supplemental): " + ", ".join(_pc_report.missing_supplemental))
            if _pc_report.rule_id:
                try:
                    from cdss.guidelines.guideline_registry import citation_line as _pc_report_cite
                    _pc_report_ref = _pc_report_cite(_pc_report.rule_id)
                    if _pc_report_ref:
                        L.append(f"Reference: {_pc_report_ref} -- see guideline_registry.py "
                                 f"for verification status")
                except Exception:
                    pass
    return L


def generate_report(
    patient_name:    str,
    age:             int,
    sex:             str,
    weight:          float,
    cl_cr:           float,
    is_renal:        bool,
    is_preg:         bool,
    is_hepatic:      bool,
    allowed:         List[Dict],
    warned:          List[Dict],
    banned:          List[Dict],
    preg_warn_items: List[Dict],
    organism:        str,
    specimen:        str,
    interactions:    List[str],
    sir_map:         Dict[str, str],
    colony_count:    str = "",
    date_in:         str = "",
    pus_cells:       str = "",
    rbcs:            str = "",
    lab_name:              str = "Your Lab Name",
    lab_city:              str = "",
    patho_assessment:      dict = None,
    show_commercial_names: bool = False,
    age_months:            Optional[int] = None,
    case:                  Any = None,
    treatment_gate:        Optional[Dict[str, Any]] = None,
    uti_note:              str = "",
) -> str:
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    sep  = "=" * 60
    sep2 = "-" * 60
    L:   List[str] = []

    lab_hdr = lab_name.upper() if lab_name else "ORANGE LAB"
    L += [sep, f"{lab_hdr} -- CLINICAL DECISION REPORT", sep, f"Date     : {now}"]
    if patient_name:
        L.append(f"Patient  : {patient_name}")
    L.append(sep)

    L += ["\nPATIENT DETAILS", sep2,
          (f"Age      : {age_months} months" if age_months is not None
         else f"Age      : {age} years"),
          f"Gender   : {sex}",
          f"Weight   : {weight} kg",
          f"Renal    : {'IMPAIRED' if is_renal else ('Creatinine normal*' if getattr(case, 'low_muscle_mass', False) else 'Normal')}"]
    if is_renal:
        _eff, _ = resolve_crcl(cl_cr, is_renal)
        L.append(f"CrCl     : {crcl_label(cl_cr, is_renal)} "
                 f"({get_renal_severity(_eff)})")
    if not is_renal and getattr(case, "low_muscle_mass", False):
        # v7.0: creatinine overestimates GFR in low muscle mass
        L.append(f"           * {LOW_MUSCLE_CRCL_NOTE_EN}")
    if getattr(case, "host_factors", None):
        L.append(f"Host     : {', '.join(case.host_factors)}")
    L.append(f"Hepatic  : {'IMPAIRED' if is_hepatic else 'Normal'}")
    if sex == "Female" and age >= 18:
        L.append(f"Pregnant : {'Yes' if is_preg else 'No'}")

    _coll_t = getattr(case, "collection_label", "") if case is not None else ""
    L += ["\nCULTURE & MICROSCOPY", sep2,
          f"Specimen : {specimen}" + (f" / {_coll_t}" if _coll_t else "")]
    if uti_note:
        L.append(f"UTI      : {uti_note}")      # v7.3: a manual syndrome vs the symptoms
    if date_in:
        L.append(f"Date In  : {date_in}")
    L.append(f"Organism : {organism}")
    if colony_count:
        L.append(f"Colony   : {colony_count}")
    if pus_cells:
        L.append(f"Pus Cells: {pus_cells} /HPF")
    if rbcs:
        L.append(f"RBCs     : {rbcs} /HPF")

    if organism in ORGANISM_PROFILE:
        op = ORGANISM_PROFILE[organism]
        if op.get("note"):
            L.append(f"Note       : {op['note']}")
        spec_ctx = (op.get("specimen_context") or {}).get(specimen, "")
        if spec_ctx:
            L.append(f"Context    : {spec_ctx}")
        _fl_gen = (_hide_urine_only(op.get("first_line"), specimen)
                   if not gate_suppresses(treatment_gate) else [])
        # v7.0: agree with the AST -- generic first-line agents this isolate is
        # R / I to are not printed as first line under its own results.
        _fl_disp = _drop_tested_ns(_fl_gen, sir_map)
        _banned_nm = {str(b.get("name", "")).lower() for b in (banned or [])}
        _fl_disp = [d for d in _fl_disp if d.lower() not in _banned_nm]
        if _fl_disp:
            L.append(f"First-line : {', '.join(_fl_disp)}  (organism default, AST-filtered)")
        elif _fl_gen:
            L.append("First-line : none of the organism's default agents is usable for this "
                     "isolate -- see RECOMMENDED below")
        if op.get("avoid"):
            L.append(f"Avoid      : {', '.join(op['avoid'])}")

    if sir_map:
        L += ["\nSENSITIVITY RESULTS", sep2]
        for drug, result in sorted(sir_map.items()):
            label = {"S": "Sensitive", "R": "Resistant", "I": "Intermediate"}.get(result, result)
            L.append(f"{drug:<40} {label}")

    L = _text_panel_completeness(
        L=L, organism=organism, sep2=sep2, sir_map=sir_map, specimen=specimen
    )

    if interactions:
        L += ["\nINTERACTIONS / WARNINGS", sep2]
        for item in sorted(set(interactions)):
            L.append(f"- {item}")

    # MDR/XDR/PDR + ESBL في التقرير
    if sir_map:
        mdr_r = classify_mdr(organism, sir_map)
        if mdr_r["level"]:
            info = MDR_INFO[physician_mdr_level(mdr_r)]
            L += [f"\n{info['icon']} RESISTANCE CLASSIFICATION: {physician_mdr_label(mdr_r)}", sep2,
                  info["detail"],
                  f"Non-susceptible ({mdr_r['resistant_count']}/{mdr_r['total_tested']}): "
                  + ", ".join(physician_mdr_categories(
                      mdr_r, sir_map, {d.get("name") for d in (allowed or []) + (warned or [])})),
                  f"Action: {info['action']}", ""]
        esbl_r = predict_esbl(organism, sir_map)
        prob   = esbl_r.get("probability")
        if prob == "carbapenemase":
            L += [f"\n🚨 {esbl_r.get('mechanism','POSSIBLE CARBAPENEMASE PRODUCER').upper()}", sep2,
                  esbl_r["detail"], f"Action: {esbl_r['action']}", ""]
        elif prob == "possible_carbapenemase":
            # 2026-11-11 (round 4): this tier was the one mechanism the text
            # report never printed, so its "confirm with mCIM / PCR" was lost.
            L += [f"\n⚠️  {esbl_r.get('mechanism','POSSIBLE CARBAPENEMASE').upper()}", sep2,
                  esbl_r.get("detail", ""), f"Action: {esbl_r.get('action', '')}", ""]
        elif prob in ("ampc", "ampc_plasmid"):
            L += ["\n⚠️  POSSIBLE AmpC β-LACTAMASE PRODUCER", sep2,
                  esbl_r["detail"], f"Action: {esbl_r['action']}", ""]
        elif prob == "high":
            L += ["\n⚠️  HIGH PROBABILITY ESBL PRODUCER", sep2,
                  esbl_r["detail"], f"Action: {esbl_r['action']}", ""]
        elif prob == "crpa":
            L += [f"\n{'🚨' if esbl_r.get('dtr') else '⚠️ '} "
                  f"{esbl_r.get('mechanism','CARBAPENEM-RESISTANT P. AERUGINOSA').upper()}", sep2,
                  esbl_r["detail"], f"Action: {esbl_r['action']}", ""]
        elif prob == "moderate":
            L += ["\n🔶 ESBL CONFIRMATION RECOMMENDED", sep2,
                  esbl_r["detail"], f"Action: {esbl_r['action']}", ""]

    # v7.2 (second external review): a "do not treat" pathogenicity verdict
    # replaces the treatment lists; a physician override is printed with them.
    if gate_suppresses(treatment_gate):
        L += ["\nNO ANTIBIOTIC TREATMENT INDICATED", sep,
              f"Pathogenicity: {treatment_gate.get('verdict', '')}",
              treatment_gate.get("reason_en", ""),
              "The susceptibility results above are reported for information only;",
              "treatment options were withheld (the physician can choose to show them).", ""]
    else:
        L += ["\nRECOMMENDED ANTIBIOTICS", sep]
        if treatment_gate:
            L += ["!! Shown at the physician's request although the pathogenicity assessment",
                  f"!! says: {treatment_gate.get('verdict', '')}", ""]
        _text_allowed(
            L=L, allowed=allowed, is_preg=is_preg, is_renal=is_renal, sep2=sep2,
            show_commercial_names=show_commercial_names, sir_map=sir_map, specimen=specimen
        )

        L = _text_warned(
            L=L, cl_cr=cl_cr, is_renal=is_renal, sep=sep, sep2=sep2,
            show_commercial_names=show_commercial_names, sir_map=sir_map, warned=warned
        )

    if is_preg and preg_warn_items and not gate_suppresses(treatment_gate):
        L += ["\nPREGNANCY -- USE WITH CAUTION", sep]
        for item in preg_warn_items:
            L += [item['name'], sep2]
            L.extend((item.get("preg_note") or "").splitlines())
            L.append("")

    _text_banned(
        L=L, banned=banned, organism=organism, sep=sep, sep2=sep2, specimen=specimen
    )

    L = _text_pathogenicity(
        L=L, patho_assessment=patho_assessment, sep2=sep2
    )

    L += ["\nDISCLAIMER", sep,
          "هذا التقرير أداة مساعدة للقرار الطبي وليس بديلاً عن التقييم السريري.",
          "القرار النهائي للوصف العلاجي يعود للطبيب المعالج.", sep,
          "Guidelines: CLSI M100 Ed36 (breakpoints) | IDSA AMR Guidance 2026 | "
          "EUCAST Expected Resistant Phenotypes | Egypt National",
          "Route info: BNF 2025 | FDA Labels | WHO AWaRe 2025",
          "WHO AWaRe : Access | Watch | Reserve", sep,
          f"Developed by Dr / Hussein Ali | {lab_name}{(' | ' + lab_city) if lab_city else ''}", sep]
    return "\n".join(L)
