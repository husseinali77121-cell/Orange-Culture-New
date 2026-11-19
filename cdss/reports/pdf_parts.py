# -*- coding: utf-8 -*-
# © Dr. Hussein Ali — Orange Lab, 6 October City, Egypt
# Microbiology CDSS — All Rights Reserved
"""Building blocks of the clinical PDF: style, fixed strings, small helpers.

Split out of report_service.generate_pdf_html_report() (v6.7, 2026-11-14),
where they were closures over the function's locals. Each now takes what it
used to capture (`_EN`, `is_renal`) as an argument; the code is otherwise
byte-for-byte what it was, held to the pre-split output by
tests/test_report_split.py.
"""
import logging
import re
from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from typing import Dict

from cdss.reports.html_utils import _esc
from cdss.reports.i18n_en import PATHO_AR_EN
from cdss.reports.i18n_en import PREG_NOTE_AR_EN

# Same logger name as before the split, so existing log filters still match.
logger = logging.getLogger("cdss.reports.report_service")


# All bilingual strings used in this PDF
def pdf_strings(_EN: bool) -> Dict[str, str]:
    """The fixed section titles and notes, in the report's language."""
    return {
        # Section headers
        "recommended":   "Recommended Therapy -- Ranked"       if _EN else "Recommended Therapy -- Ranked",
        "avoid":         "Avoid / Contraindicated"            if _EN else "⊘ Avoid / Contraindicated",
        "dose_adj":      "⚠ Dose Adjustment / Use with Caution",
        "interactions":  "⊕ Drug Interactions",
        "pregnancy":     "⚠ Pregnancy -- Use with Caution",
        "preg_sub":      "(Physician decision required for all items below)",
        "treatment":     "Treatment Duration",
        "pathogenicity": "Pathogenicity Assessment",
        # Pregnancy inline notes
        "preg_extra":    "Additional options require caution in pregnancy -- see Pregnancy section below."
                         if _EN else "⚠ خيارات إضافية بحذر في الحمل -- راجع قسم Pregnancy بالأسفل.",
        "preg_only":     "All sensitive agents require caution in pregnancy -- see Pregnancy -- Use with Caution below."
                         if _EN else "⚠ جميع الخيارات الحساسة تتطلب حذراً في الحمل -- راجع قسم Pregnancy -- Use with Caution بالأسفل لاتخاذ القرار.",
        # Renal
        "renal_label":   "Patient CrCl" if _EN else "Patient CrCl",
        "renal_thresh":  "Threshold: CrCl ≤",
        "renal_adj":     "⚠ Renal dose adjustment required  |  Threshold: CrCl ≤",
        "intermediate":  "⚠ Intermediate (I) / SDD in culture result (CLSI M100) -- use only if no susceptible option fits",
        # Patho
        "supporting":    "Supporting:",
        "against":       "Against:",
        "recs":          "Recommendations:",
        # Duration
        "protocol":      "Protocol",
        "standard":      "Standard",
        "range":         "Range",
        "iv_po":         "IV/PO Split",
        "follow_up":     "▣ Follow-up culture recommended after treatment",
        # Footer
        "disclaimer":    "Disclaimer: Clinical decision support only. Treatment decisions are the sole responsibility of the treating physician.",
        "references":    "References",
    }


def xlate_preg_note(note: str, _EN: bool) -> str:
    """Translate Arabic preg_note to English for EN mode."""
    if not _EN or not note:
        return note
    import re as _re
    _arabic_re = _re.compile(r'[؀-ۿ]+')
    if not _arabic_re.search(note):
        return note   # already English

    # Known translations map
    _AR_EN = PREG_NOTE_AR_EN

    result = note
    for ar, en in _AR_EN.items():
        result = result.replace(ar, en)
    return result

def xlate_patho(text: str, _EN: bool) -> str:
    """Translate Arabic pathogenicity text to English."""
    if not _EN or not text:
        return text
    import re as _re
    if not _re.compile(r'[؀-ۿ]').search(text):
        return text
    _PATHO_EN = PATHO_AR_EN
    result = text
    for ar, en in _PATHO_EN.items():
        result = result.replace(ar, en)

    # Word-level fallback for any remaining Arabic fragments
    # NOTE: a word-level Arabic->English dictionary (_WORD_EN) used to sit
    # here but was never wired in -- the regex strip below always ran instead.
    # It has been deleted rather than connected, because partial word
    # substitution produced half-translated "franco" text that is harder to
    # read than clean removal. What IS unsafe is deleting a clinical
    # recommendation with no trace, so the strip now logs what it dropped.
    # Safety net: strip any residual Arabic so the English report is
    # guaranteed to contain ZERO Arabic (and never franco-garbage from
    # partial word substitution). Complete phrases above are fully
    # translated; this only catches anything not yet mapped.
    if re.compile(r'[؀-ۿ]').search(result):
        _dropped = re.findall(r'[؀-ۿ\uFB50-\uFEFF]+(?:\s+[؀-ۿ\uFB50-\uFEFF]+)*', result)
        if _dropped:
            logger.warning(
                "EN report: %d Arabic fragment(s) had no translation and were "
                "removed -- add them to _PATHO_EN: %s",
                len(_dropped), " | ".join(f[:60] for f in _dropped[:5]))
        result = re.sub(r'[؀-ۿ\uFB50-\uFEFF]+', '', result)
        result = re.sub(r'\(\s*\)', '', result)            # drop empty parens
        result = re.sub(r'\s+([.,;:،])', r'\1', result)     # tidy space before punct
        result = re.sub(r'\s{2,}', ' ', result).strip()
    return result

# ── AWaRe helpers ────────────────────────────────────────────────────
AWARE_CLR  = {"Access": "#1e8449", "Watch": "#b7770d", "Reserve": "#922b21",
              "Not Recommended": "#555555"}
AWARE_PILL = {"Access": "background:#1e8449;color:#fff",
              "Watch":  "background:#b7770d;color:#fff",
              "Reserve":"background:#922b21;color:#fff",
              "Not Recommended": "background:#555555;color:#fff"}
AWARE_CARD = {"Access": "background:#eafaf1;border:0.8pt solid #1e8449",
              "Watch":  "background:#fef9e7;border:0.8pt solid #b7770d",
              "Reserve":"background:#fdf2f2;border:0.8pt solid #922b21",
              "Not Recommended": "background:#f2f2f2;border:0.8pt solid #555555"}
# NOTE: AWaRe class is NOT used as the therapy "line" anymore (see ranked loop
# below) — Access!=first-line for a given site. Line labels come from the syndrome.

def pill(txt, style):
    return f'<span style="padding:0.35mm 2.6mm;border-radius:2mm;font-size:8.5pt;font-weight:bold;{style}">{_esc(txt)}</span>'

def renal_note_text(d, is_renal: bool, _EN: bool) -> str:
    """Renal note in the report's language.

    EN reports must never fall back to the Arabic renal_note: the
    downstream Arabic strip would delete words like "تجنّب" (avoid) and
    "بعد" (after) mid-sentence, turning "(avoid 875mg)" into "(875mg)"
    and "+ dose after dialysis" into "+ dose dialysis".

    The two entries this used to hold back (Cefotaxime, Norfloxacin) held
    another drug's dose band and had renal_note_en blanked as a stopgap.
    That protected the English report only -- the ARABIC report, which is
    the one this lab issues, kept printing pip-tazo doses under Cefotaxime
    and co-amoxiclav doses under Norfloxacin. Both bands are now corrected
    at source, so the hold below is dormant. It stays as a net: any future
    entry with a deliberately blank renal_note_en shows an explicit hold
    rather than a silent gap or the wrong drug's dosing.
    """
    # ── Dose detail is withheld unless the patient is FLAGGED RENAL ─────
    # Requested 2026-08-03. A PDF is an issued document: it leaves the lab,
    # gets photographed, forwarded, and read weeks later by someone who
    # never saw the patient. Specific milligrams and intervals printed on a
    # report for a patient with NORMAL renal function are an invitation to
    # apply them to a different patient, or to the same patient after their
    # function has changed.
    #
    # What is withheld is the NUMBERS, not the fact. The reader is still
    # told the agent carries a renal threshold and what that threshold is,
    # so nobody concludes from a short line that no adjustment exists — the
    # dangerous reading. They are told where to get the figures.
    #
    # When is_renal is set, the full band prints: that is the patient the
    # numbers were computed for.
    _lim = d.get("renal_limit")
    if not is_renal:
        if isinstance(_lim, (int, float)) and _lim:
            if _EN:
                return (f"Renally adjusted below CrCl {int(_lim)}. Specific "
                        f"doses are not printed for a patient not flagged "
                        f"as renally impaired — recheck if renal function "
                        f"changes and consult BNF 2025.")
            return (f"يحتاج تعديل الجرعة تحت CrCl {int(_lim)}. الجرعات "
                    f"التفصيلية لا تُطبع لمريض غير مُسجَّل بقصور كلوي — "
                    f"أعِد التقييم إذا تغيّرت الوظيفة الكلوية، وراجع BNF 2025.")
        return d.get("renal_note_en" if _EN else "renal_note", "") or ""

    if not _EN:
        return d.get("renal_note", "") or ""
    en = (d.get("renal_note_en") or "").strip()
    if en:
        return en
    if "renal_note_en" in d:
        return ("Renal dosing withheld -- entry flagged for clinical "
                "verification. Consult BNF 2025.")
    return d.get("renal_note", "") or ""

def join_more(items, n):
    """Join first n items, then say how many were withheld."""
    items = [str(i) for i in (items or [])]
    head = ", ".join(items[:n])
    rest = len(items) - n
    return head + (f"  (+{rest} more)" if rest > 0 else "")

def clip(text, limit):
    """Word-boundary-safe truncation with a visible ellipsis.

    The previous code sliced clinical strings at a raw character index,
    which cut dose bands mid-number ('CrCl 40-6') and gave the reader no
    signal that anything had been dropped. This never splits a token and
    always marks the cut.
    """
    s = str(text or '')
    if len(s) <= limit:
        return s
    cut = s[:limit]
    sp = cut.rfind(' ')
    if sp > limit * 0.55:
        cut = cut[:sp]
    return cut.rstrip(' ,;.-') + '\u2026'

# ── Compact CSS ──────────────────────────────────────────────────────
PDF_CSS = """
@page {
    size: A4;
    margin: 6mm 10mm 8mm 10mm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages) " | Microbiology CDSS | @@LABFOOT@@";
        font-size: 7.5pt; color: #7b8794;
        font-family: 'Noto Sans','Liberation Sans','DejaVu Sans', sans-serif;
    }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
/* ══ TYPE SYSTEM ═══════════════════════════════════════════════════════
   Serif sets prose, headings and the masthead (clinical/journal register).
   Sans sets numeric and tabular data (digit clarity in dense dose strings).
   Amiri is listed last in every stack and every Latin family ahead of it has
   zero Arabic coverage, so Arabic resolves to Amiri and nothing else does.
   Geometric symbols (✓ ✗ ⊘ ◆ ● ▣ ▲ ↻ ⊕) fall through to DejaVu Sans.        */
body { font-family: 'Noto Serif','Liberation Serif','Amiri','DejaVu Sans',serif;
       font-size: 9.3pt; line-height: 1.42; color: #1a1a2e; direction: ltr;
       background: #fff; -weasy-hyphens: none; }

/* Data faces — tabular figures so dose columns align and digits stay distinct */
.ast, .compact-tbl, .info4, .dose-grid, .ranked-row, .tier-sep,
.hdr-right, .hdr-lbl, .score-lbl {
    font-family: 'Noto Sans','Liberation Sans','Amiri','DejaVu Sans',sans-serif;
    font-variant-numeric: tabular-nums;
    -weasy-font-variant-numeric: tabular-nums;
}
/* Binomial names stay serif italic — scientific convention */
.hdr-org, i.sci { font-family:'Noto Serif','Liberation Serif',serif; font-style:italic; }
/* Arabic runs */
.rtl, .ar, .hdr-pt { font-family:'Amiri','Noto Naskh Arabic',serif; }
.ltr { direction: ltr; unicode-bidi: embed; display: inline; }
.rtl { direction: rtl; unicode-bidi: embed; }
/* Header — compact */
.hdr { background:#0d3b66; color:#fff; padding:2mm 8mm 1.5mm; display:flex;
       justify-content:space-between; align-items:center; }
.hdr-lab  { font-size:15.5pt; font-weight:bold; letter-spacing:0.35pt; }
.hdr-pt   { font-size:9pt; }
.hdr-org  { font-size:9.2pt; }
.hdr-sub  { font-size:8.6pt; color:#c3d3e4; margin-top:0.4mm; }
.hdr-pills { margin-top:0.7mm; }
.hdr-right { font-size:8.6pt; color:#edf3f9; text-align:right; direction:ltr; }
.hdr-lbl  { font-size:8pt; color:#9fb8d2; letter-spacing:0.5pt; }
.accent   { height:1mm; background:#ff8c00; }
.content  { padding: 0.5mm 0; }
/* Micro info grid */
.info4 { display: table; width: 100%; border-collapse: collapse; font-size:9pt; margin:1mm 0; }
.info4 tr td { padding: 1mm 2.5mm; border: 0.3pt solid #d5d8dc; }
.lbl4 { background:#f4f6f8; font-weight:bold; color:#0d3b66; width:14%; }
.val4 { width:22%; }
/* Section titles — tighter */
.sec-ttl { font-size:9.2pt; font-weight:bold; color:#0d3b66; text-transform:uppercase;
            letter-spacing:0.9pt; border-bottom:0.7pt solid #0d3b66;
            padding-bottom:0.4mm; margin:1.6mm 0 0.8mm;
            direction:ltr; text-align:left; }
/* AST table */
.ast { width:100%; border-collapse:collapse; font-size:8.8pt; direction:ltr; }
.ast th { background:#0d3b66; color:#fff; padding:1mm 2.5mm; text-align:left; font-size:8pt; }
.ast td { padding:1mm 2.5mm; border:0.3pt solid #d5d8dc; text-align:left; }
.ast tr:nth-child(even) td { background:#f8f9fa; }
.sir-s { color:#1e8449; font-weight:bold; }
.sir-i { color:#b7770d; font-weight:bold; }
.sir-r { color:#922b21; font-weight:bold; }
/* Two-column grid */
.pb { page-break-after: always; }
.grid2 { display:table; width:100%; border-spacing:1mm; border-collapse:separate; direction:ltr; }
.g2l { display:table-cell; width:49%; vertical-align:top; direction:ltr; text-align:left; }
.g2r { display:table-cell; width:49%; vertical-align:top; direction:ltr; text-align:left; }
/* Ranked rows — tighter */
.ranked-row { padding:1mm 2.5mm; margin:0.4mm 0; border-radius:1.5mm; direction:ltr; text-align:left;
              display:flex; justify-content:space-between; align-items:center; page-break-inside:avoid; }
.tier-sep { font-size:8.2pt; font-weight:bold; text-transform:uppercase; letter-spacing:0.3pt;
            direction:ltr; text-align:left;
            padding:0.2mm 0; margin-top:0.8mm; border-top:0.8pt solid; }
/* Alerts — tighter */
.alert { padding:1.1mm 2.8mm; border-radius:1.5mm; margin:0.5mm 0; font-size:9.2pt; direction:ltr; text-align:left; }
.al-warn   { background:#fef9e7; border:0.4pt solid #b7770d; color:#7d6608; }
.al-danger { background:#fdedec; border:0.4pt solid #922b21; color:#78281f; }
.al-info   { background:#eaf4fb; border:0.4pt solid #2980b9; color:#1a5276; }
.score-bar { background:#e5e7eb; border-radius:1.5mm; height:3mm; width:100%; }
.score-fill{ height:3mm; border-radius:1.5mm; }
.compact-tbl { width:100%; border-collapse:collapse; font-size:9.2pt; direction:ltr; }
.compact-tbl td { padding:0.8mm 2.5mm; border:0.3pt solid #d5d8dc; text-align:left; }
.compact-tbl .lbl { background:#f4f6f8; font-weight:bold; color:#0d3b66; width:40%; }
.warn-val  { color:#b7770d; font-weight:bold; }
.danger-val{ color:#922b21; font-weight:bold; }
.no-break  { page-break-inside: avoid; }
hr.dv { border:none; border-top:0.4pt solid #d5d8dc; margin:0.6mm 0; }
/* Safety net: long, unbreakable drug names must never overflow the A4 margin */
.content, .alert, .g2l, .g2r, .ranked-row > div { overflow-wrap:anywhere; }
.ranked-row > div { min-width:0; }
"""

# ── Specimen short label for header (lab-report convention) ───────────
SPECIMEN_SHORT = {
    "Urine":       "Urine C/S",
    "Blood":       "Blood C/S",
    "Sputum":      "Sputum C/S",
    "Wound Swab":  "Wound C/S",
    "Pus":         "Pus C/S",
    "Stool":       "Stool C/S",
    "CSF":         "CSF C/S",
}

def header_html(page_lbl: str, *, mdr_class, mdr_result, _hdr_ph_labels, esbl_conf, esbl_prob,
                esbl_result, lab_name, lab_city, specimen_short, date_in, now_str,
                organism) -> str:
    """The navy masthead: lab, specimen, date, patient, organism and the MDR / mechanism pills."""
    mdr_pills = ""
    # MDR/XDR/PDR — deterministic category count (Magiorakos 2012), always shown
    if mdr_class:
        # v7.0: the physician report prints MDR for a provisional XDR/PDR
        # ("possible XDR" stays on the screen and in the internal QA report).
        from cdss.resistance.mdr import physician_mdr_level
        _mdr_pill = physician_mdr_level(mdr_result) or mdr_class
        mdr_pills += pill(_mdr_pill, "background:#922b21;color:#fff" if _mdr_pill in ("XDR", "PDR")
                          else "background:#b7770d;color:#fff")+" "
    # Resistance phenotypes (MRSA/VRE/CRE/CRAB/CRPA) — confirmed via direct AST
    # markers, always shown. Weak/fallback inferences already excluded upstream.
    for ph in _hdr_ph_labels[:3]: mdr_pills += pill(ph, "background:#6e2fa0;color:#fff")+" "
    # ESBL/AmpC/Carbapenemase — genuinely PREDICTED mechanisms (predict_esbl()).
    # Only surface in header when confidence is high; lower-confidence calls
    # remain available in the body detail, not as a prominent badge.
    if esbl_conf >= 70:
        if esbl_prob == "crpa":
            mdr_pills += pill("DTR-P.aeruginosa" if (esbl_result or {}).get("dtr") else "CR-P.aeruginosa",
                              "background:#922b21;color:#fff" if (esbl_result or {}).get("dtr")
                              else "background:#b7770d;color:#fff")
        elif esbl_prob in ("carbapenemase", "possible_carbapenemase"): mdr_pills += pill("CARBAPENEMASE","background:#922b21;color:#fff")
        elif esbl_prob in ("ampc", "ampc_plasmid"):        mdr_pills += pill("AmpC","background:#b7770d;color:#fff")
        elif esbl_prob in ("high","moderate"): mdr_pills += pill("ESBL+","background:#b7770d;color:#fff")
    _pills_html = ("<div class='hdr-pills'>" + mdr_pills + "</div>") if mdr_pills else ""
    return f"""<div class="hdr">
  <div>
    <div class="hdr-lab">{_esc(lab_name)}</div>
    <div class="hdr-sub">{_esc(lab_city)} &nbsp;|&nbsp; Microbiology CDSS</div>
    {_pills_html}
  </div>
  <div class="hdr-right">
    <b style="font-size:11pt">{_esc(specimen_short)}</b><br>
    <span class="hdr-lbl">{page_lbl}</span><br>
    {_esc(date_in or now_str[:10])}<br>
    <b class="hdr-pt">&#x2067;@@PTNAME@@&#x2069;</b><br>
    <span class="hdr-org">&#x2066;{_esc(organism)}&#x2069;</span>
  </div>
</div><div class="accent"></div><div class="content">"""


def avoid_reason_tag(bd, sir_map, *, is_mrsa=False, is_carbapenemase=False, is_esbl_like=False):
    """(tag, colour) for one banned agent in the physician PDF's AVOID strip."""
    cat = bd.get("category", "")
    nm  = bd.get("name", "")
    _sir = sir_map.get(nm, "")
    _info_lookup = ABX_GUIDELINES.get(nm, {})
    _cls = (_info_lookup.get("class", "") or "").lower()
    # 0. v7.0: no breakpoint for this pair -- the result (even an R) says nothing
    if cat == "no_breakpoint":
        return ('⊘ No breakpoint', '#7f8c8d')
    # 1. Resistant in culture (explicit R)
    if cat == "resistant" or _sir == "R":
        return ('✗ (R)', '#922b21')
    # 2. Pregnancy contraindication
    if cat == "pregnancy":
        return ('⊘ Pregnancy', '#7d3c98')
    # 3. Pediatric / child
    if cat in ("child", "pediatric"):
        return ('⊘ Pediatric', '#7d3c98')
    # 4. Renal
    if cat == "renal":
        return ('⚠ Renal', '#b7770d')
    # 5. Organism-based (MRSA / ESBL / AmpC / Carbapenemase / intrinsic)
    if cat == "organism":
        _is_betalactam = any(k in _cls for k in
                             ("penicillin", "cephalosporin", "carbapenem", "monobactam"))
        # MRSA: detected + beta-lactam
        if is_mrsa and _is_betalactam:
            return ('⚠ MRSA -- β-lactam', '#922b21')
        # Carbapenemase
        if is_carbapenemase and _is_betalactam:
            return ('⚠ Carbapenemase', '#922b21')
        # ESBL/AmpC suppression of penicillins+cephalosporins
        if is_esbl_like and _is_betalactam:
            return ('⚠ ESBL Concern', '#b7770d')
        # Otherwise intrinsic resistance
        return ('⚠ Intrinsic R', '#922b21')
    # v7.0: name the reason instead of a bare "Avoid"
    return {"uti_upper": ('⊘ Cystitis only', '#b7770d'), "specimen": ('⊘ Site', '#b7770d'),
            "safety_gate": ('⊘ Site / host', '#b7770d'), "hepatic": ('⚠ Hepatic', '#b7770d'),
            "allergy": ('⊘ Allergy', '#922b21'), "neonate": ('⊘ Neonate', '#7d3c98'),
            "cross_resistance": ('✗ Cross-R', '#922b21'),
            "interaction": ('⚠ Interaction', '#b7770d')}.get(cat, ('✗ Avoid', '#922b21'))


def section_treatment_gate(*, H, _EN, gate) -> None:
    """v7.2: the pathogenicity "do not treat" verdict, or the physician's override of it."""
    if not gate:
        return
    _v = _esc(gate.get("verdict", ""))
    if gate.get("override"):
        H.append('<div class="alert al-warn" style="font-size:9pt;line-height:1.5">'
                 '<b>⚠ Options shown at the physician\'s request</b> although the pathogenicity '
                 f'assessment says: {_v}. {_esc(gate.get("reason_en", ""))}'
                 + ('' if _EN else f'<div dir="rtl" style="text-align:right">{_esc(gate.get("reason_ar", ""))}</div>')
                 + '</div>')
        return
    H.append('<div class="sec-ttl">NO ANTIBIOTIC TREATMENT INDICATED</div>')
    H.append('<div class="alert al-danger" style="font-size:9.5pt;line-height:1.55">'
             f'<b>{_v}</b><br>{_esc(gate.get("reason_en", ""))}'
             + ('' if _EN else f'<div dir="rtl" style="text-align:right">{_esc(gate.get("reason_ar", ""))}</div>')
             + '<br><span style="font-size:8.4pt">Treatment options were withheld; the '
               'susceptibility result is for information. Re-assess if symptoms or signs '
               'of infection develop.</span></div>')
