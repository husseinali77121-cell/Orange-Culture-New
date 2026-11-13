# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Field detectors over OCR text: age, sex, specimen, organism, S/I/R, microscopy."""
from typing import Dict
from typing import Optional
import re

from cdss.ocr.ocr_parsing import ORGANISM_OCR_ALIASES
from cdss.ocr.ocr_parsing import normalize_sir_value
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.common.catalog import (
    BACTERIA_TYPES,
    SPECIMEN_TYPES,
)
from cdss.common.specimen import (
    _SPEC_CAT_TO_TYPE,
    classify_specimen,
)


def detect_age(text: str) -> Optional[int]:
    r"""Age in YEARS from a report header. Returns 0 for anyone under one year.

    The previous version matched `Age[:\s]+(\d+)` before considering the unit,
    so every sub-year notation in common use was read as a number of YEARS:

        "Age: 6/12"        -> 6      (means 6 MONTHS in Egyptian, Indian and
                                      UK paediatric notation)
        "Age: 3 months"    -> None
        "Age: 20 days"     -> None

    Reading a six-month-old as a six-year-old bypasses every infant and neonatal
    gate in the engine at once -- ceftriaxone, TMP-SMX and nitrofurantoin all
    become ALLOWED for a patient with hard contraindications to all three. Units
    are therefore matched BEFORE the bare number, and `detect_age_months`
    supplies the precision the neonatal table needs.
    """
    # FIX 2026-11-11 (round 4): the unit patterns ran over the WHOLE report
    # first, so "growth after 2 days incubation" made a 45-year-old age 0. The
    # age is now read from the age field itself -- see
    # ocr_parsing.parse_patient_age for the rules and the history.
    from cdss.ocr.ocr_parsing import parse_patient_age
    return parse_patient_age(text)[0]

def detect_sex(text_lower: str) -> Optional[str]:
    """Robust sex detection — regex with word boundaries, Female checked first.
    Handles: 'sex: male/female', 'sex: m/f', 'sex=male', 'gender: ...', Arabic."""
    # Female first (avoids 'male' substring inside 'female')
    if (re.search(r'(?:sex|gender)\s*[:=]?\s*(?:female|f\b)', text_lower)
            or re.search(r'\bfemale\b', text_lower)
            or "أنثى" in text_lower or "انثى" in text_lower):
        return "Female"
    # Male: word boundary on 'male' so it won't fire on 'female'
    if (re.search(r'(?:sex|gender)\s*[:=]?\s*(?:male|m\b)', text_lower)
            or re.search(r'\bmale\b', text_lower)
            or "ذكر" in text_lower):
        return "Male"
    return None

def detect_specimen(text_lower: str) -> Optional[str]:
    """Specimen type from the OCR text.

    FIX 2026-11-11 (round 4): this returned the FIRST specimen name found
    anywhere in the text, in list order (Urine, Blood, Sputum, ...). Analyte
    lines name other specimens: a CSF report prints "RBCs (red blood cells)"
    and a stool report "occult blood", so both came back as BLOOD -- which
    then filtered the organism list and pre-selected a bloodstream workflow.
    Now: the labelled specimen field first, then "<x> culture", then the most
    specific words, with the analyte words ("blood", "pus") last.
    """
    t = str(text_lower or "").lower()

    def _typ(cat: str) -> Optional[str]:
        name = _SPEC_CAT_TO_TYPE.get(cat)
        return name if name in SPECIMEN_TYPES else None

    for m in re.finditer(r"(?:specimen|sample|type of specimen|نوع العينة|العينة)"
                         r"\s*(?:type)?\s*[:\-]\s*([^\n|]{2,40})", t):
        cat = classify_specimen(m.group(1))
        if cat and _typ(cat):
            return _typ(cat)
    m = re.search(r"(?<![a-z])(urine|blood|sputum|stool|csf|wound|pus|throat|tracheal|bal)"
                  r"\s*(?:culture|c\s*/\s*s|c\s*&\s*s)", t)
    if m:
        cat = classify_specimen(m.group(1))
        if cat and _typ(cat):
            return _typ(cat)
    for name, keys in (("CSF", ("csf", "cerebrospinal", "نخاعي")),
                       ("Stool", ("stool", "faec", "fecal", "براز")),
                       ("Sputum", ("sputum", "bronch", "tracheal", "بلغم")),
                       ("Urine", ("urine", "بول")),
                       ("Wound Swab", ("wound", "swab", "جرح", "مسحة")),
                       ("Blood", ("blood culture", "bacteraem", "bacterem", "bottle")),
                       ("Pus", ("abscess", "pus ", "صديد", "خراج")),
                       ("Blood", ("blood",))):
        if name in SPECIMEN_TYPES and any(k in t for k in keys):
            return name
    return None

# Spellings a laboratory actually prints, mapped to the profile key. Detection
# was plain containment of the PROFILE NAME, so a report saying "Escherichia
# coli" -- the full binomial, which is what most laboratories write -- matched
# nothing and the organism field came back empty. Since almost every downstream
# decision keys on the organism, an empty field silently disables intrinsic
# resistance, mechanism inference and MDR classification all at once.


def detect_organism(text_lower: str) -> Optional[str]:
    """Best-matching organism from OCR text, profile names AND lab spellings.

    Longest alias wins, so "escherichia coli" is not decided by the shorter
    "e. coli" fragment and "enterococcus faecium" is not swallowed by
    "enterococcus".
    """
    t = str(text_lower or "").lower()

    # FIX 2026-11-10: plain substring matching read "gas" inside "gastric" /
    # "gastroenteritis" as Group A Streptococcus and "cons" inside
    # "consistent" / "consultant" as CoNS. Every alias is now matched on
    # letter boundaries (digits and punctuation still count as a boundary).
    def _hits(needle: str) -> int:
        n = needle.lower()
        if not n:
            return 0
        return len(re.findall(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", t))

    counts: Dict[str, int] = {}
    for organism in BACTERIA_TYPES:
        c = _hits(organism)
        if c > 0:
            counts[organism] = counts.get(organism, 0) + c
    if not counts:
        for alias in sorted(ORGANISM_OCR_ALIASES, key=len, reverse=True):
            if _hits(alias):
                mapped = ORGANISM_OCR_ALIASES[alias]
                if mapped in ORGANISM_PROFILE:
                    return mapped
        return None
    return max(counts, key=counts.get)

def classify_sir_from_line(line: str) -> Optional[str]:
    """S/I/R from one printed AST line.

    Routed through normalize_sir_value() so the OCR reader and the engine cannot
    disagree about what a result means. Before this, the engine accepted SDD and
    NS while the OCR classifier returned None for both, and neither side
    understood the Arabic حساس / مقاوم / متوسط that bilingual reports print --
    so a resistant drug read from an Arabic report simply had no result at all.
    """
    ll = str(line or "").lower().strip()
    # Longest-first so "non-susceptible" is not read as "susceptible".
    for pat, token in (
        (r"(?:non[\s\-]?susceptible|not\s+susceptible)", "NS"),
        (r"(?:susceptible[\s\-]*dose[\s\-]*dependent|\bsdd\b)", "SDD"),
        (r"\b(?:sensitive|susceptible|sens)\b", "S"),
        (r"\b(?:resistant|resist)\b", "R"),
        (r"\b(?:intermediate|inter)\b", "I"),
        (r"\bns\b", "NS"),
        (r"(?:حسّاس|حساس)", "S"),
        (r"(?:مقاوم)", "R"),
        (r"(?:متوسط|متوسطة)", "I"),
    ):
        if re.search(pat, ll):
            return normalize_sir_value(token)
    tail = re.search(r"\b([sir])\b\s*$", ll)
    if tail:
        return tail.group(1).upper()
    return None

# ── Drug-name scanning: SPAN-CLAIMING, LONGEST-WINS ──────────────────────────
#  BUG FIXED (Acinetobacter / Sputum report): the old scanner tested plain
#  containment of every drug name in the raw OCR text. Because every combination
#  agent CONTAINS its own partner drug, one printed line manufactured several
#  phantom panel entries that were never tested:
#
#      "Ampicillin/Sulbactam"          -> also produced "Ampicillin"
#      "Amoxicillin + Clavulanic acid" -> also produced "Amoxicillin"
#      "Cefoperazone + Sulbactam"      -> also produced "Cefoperazone"
#      "Cefuroxime sodium"             -> also produced "Cefuroxime"
#      "Levofloxacin"                  -> also produced "Ofloxacin"  (!)
#
#  Those phantoms then hit INTRINSIC_RESISTANCE: for A. baumannii bare
#  Ampicillin / Amoxicillin ARE intrinsically resistant while the tested
#  Ampicillin/Sulbactam is NOT, so the report showed an intrinsic-resistance
#  alert for a drug that was never on the panel.
#
#  The fix scans the NORMALIZED text (same normalisation as the alias index, so
#  "+", "/", spaces and case never matter), longest alias first, and CLAIMS the
#  character span each match occupies. A shorter name that falls entirely inside
#  an already-claimed span is a fragment of the longer name, not a second drug.

# ═══════════════════════════════════════════════════════════════════════════
# CLSI / EUCAST DISK CODES  (added 2026-08-01)
# ---------------------------------------------------------------------------
# DEFECT THIS FIXES
# ABX_ALIAS_INDEX held 176 aliases, rich in Egyptian brand names (Augmentin,
# Curam, Unictam, Sigmaclav, Unasyn, Tazocin) and containing ZERO disk codes.
# VITEK, Phoenix and hand-read disk plates all label by code, so a report
# printed as "AMC  R / CIP  R / SXT  R / MEM  R" produced an EMPTY panel and
# nothing said so. Measured on a Pseudomonas isolate the same AST went from
# MDR (4/5 categories) to level=None -- the MDR alert disappeared entirely
# because half the panel was never parsed.
#
# WHY THIS IS NOT JUST MORE ALIASES
# Several codes are one or two letters: P (benzylpenicillin), E (erythromycin),
# DO (doxycycline), CN (gentamicin), TE (tetracycline), VA (vancomycin), AK
# (amikacin). Dropping those into ABX_ALIAS_INDEX would make them match inside
# ordinary words -- normalize_abx_key strips punctuation, so "Patient" contains
# "p" and "Date" contains "te". Every one of them would fire on the report
# header.
#
# So a code is honoured ONLY when it stands alone as a whole token AND the line
# also carries an S/I/R verdict. That is the shape of a result row and nothing
# else. A code appearing in prose has no verdict beside it and is ignored.
# ═══════════════════════════════════════════════════════════════════════════

# A result row must carry a verdict. Reuse the same vocabulary the value parser
# accepts so the two cannot drift.







def detect_pus_cells(text: str) -> str:
    """
    Extract Pus cells / WBCs from OCR text.
    Handles: 6-8, 10-15, >10, Over 100, >100/HPF, TNTC, كثيرة
    """
    import re
    text_l = text.lower()

    # FIX (#O1): scope the generic qualifiers (>N / over N / TNTC / +++) to the
    # pus/WBC line when one is present, so a '>N' belonging to RBCs or the colony
    # count elsewhere in the report is not misread as the pus-cell value.
    _pus_line = ""
    for _ln in text_l.splitlines():
        # Round 5: "Leukocyte esterase: +++" is a dipstick line, not a cell
        # count -- it used to win over the real "Pus cells: 2-4" line below it
        # and came back as ">100". "Pus: 50-60" (no "cells") is accepted.
        if "esterase" in _ln:
            continue
        if re.search(r"pus\s*cells?|(?<![a-z])pus\s*[:=]|w\.?b\.?c|leu[ck]ocyt|صديد", _ln):
            _pus_line = _ln
            break
    # FIX 2026-11-11 (round 4): this used to fall back to the WHOLE report when
    # no pus/WBC line existed, and the generic qualifiers below then read the
    # culture section as microscopy -- "Colony count: >100,000 CFU/mL" became
    # pus cells ">100" and "Moderate growth of Klebsiella" became "10-20",
    # both fed to the pathogenicity score as pyuria the report never stated.
    # Without a labelled line there is no pus-cell value to qualify; only the
    # bare N/HPF fallback at the end (which has its own guards) may still run.
    if not _pus_line:
        if not re.search(r"r\.?\s*b\.?\s*c|red\s*b|erythro|cast|epithel|crystal|"
                         r"yeast|bacteri|حمراء|بلورات", text_l):
            for pat in (r"(\d+\s*[-–]\s*\d+)\s*/\s*hpf", r"(\d+)\s*/\s*hpf"):
                m = re.search(pat, text_l, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
        return ""
    scope = _pus_line

    # Round 5: a NUMBER printed right after the label is the value. The verbal
    # qualifiers below used to be tried first over the whole line, so
    # "Pus cells 15-20 /HPF, many bacteria" came back as ">30" -- the word
    # belongs to the bacteria.
    _after = re.split(r"pus\s*cells?|(?<![a-z])pus(?=\s*[:=])|w\.?\s*b\.?\s*c\.?s?|"
                      r"leu[ck]ocytes?|صديد", scope, maxsplit=1)[-1]
    _m_num = re.match(r"(?:[\s:=\-–/().]|h\.?p\.?f\.?)*(\d+\s*[-–]\s*\d+|\d+)(?![\d,.]*\d)",
                      _after)
    if _m_num:
        return _m_num.group(1).strip()

    # ── Text qualifiers (check first, within scope) ──────────────────────────
    # ADDED 2026-08-03. This extractor and pathogenicity._parse_pus disagreed
    # about the same words: the SCORER resolved "full field", "loaded",
    # "plenty", "many", "occasional" to numbers, and this EXTRACTOR returned ""
    # for all of them — so the verbal readings never reached the scorer that
    # knew what to do with them. A microscopist writing "pus cells: full field",
    # the strongest pyuria on the form, produced no value at all.
    #
    # The vocabularies are now the same one, resolved to the same words, so a
    # change to _PUS_VERBAL cannot silently leave this function behind.
    if re.search(r"tntc|too\s+numerous|innumerable|uncountable"
                 r"|full\s*field|packed|loaded|مليء|حقل\s*كامل", scope):
        return "TNTC"
    if re.search(r"plenty|numerous|كثير", scope):
        return ">50"
    if re.search(r"\bmany\b|عديد", scope):
        return ">30"
    if re.search(r"\bmoderate\b|متوسط", scope):
        return "10-20"
    if re.search(r"occasional|\bfew\b|scanty|قليل", scope):
        return "1-3"
    if re.search(r"\bnil\b|\bnone\b|not\s*seen|absent|لا\s*يوجد", scope):
        return "0"
    m_over = re.search(r"over\s*(\d+)", scope)
    if m_over:
        return f"Over {m_over.group(1)}"
    m_gt = re.search(r">\s*(\d+)", scope)
    if m_gt:
        return f">{m_gt.group(1)}"
    if re.search(r"\+{3,}|كثير", scope):
        return ">100"

    # ── Numeric patterns (anchored to pus/wbc first) ─────────────────────────
    patterns = [
        r"pus(?:\s*cells?)?\s*[:\-]?\s*(\d+\s*[-–]\s*\d+|\d+)",
        r"wbcs?\s*[:\-]?\s*(\d+\s*[-–]\s*\d+|\d+)",
        r"(\d+\s*[-–]\s*\d+)\s*/\s*hpf",
        r"(\d+)\s*/\s*hpf",
    ]
    # Anchored patterns (1-2) may search the whole text: they carry their own
    # "pus cells" / "wbc" label. The bare /HPF patterns (3-4) MUST stay inside the
    # pus line, otherwise they pick up whichever analyte happens to be printed
    # first -- RBCs, casts, epithelial cells.
    for pat in patterns[:2]:
        m = re.search(pat, text_l, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    if _pus_line:
        for pat in patterns[2:]:
            m = re.search(pat, _pus_line, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        # "Pus cells / HPF    2-4" puts the unit before the value, so the
        # number-then-/HPF patterns miss it. Strip the label and the unit off the
        # pus line and take whatever number is left -- still confined to that line.
        _rest = re.sub(r"pus\s*cells?|w\.?\s*b\.?\s*c\.?s?|leu[ck]ocytes?|صديد",
                       " ", _pus_line, flags=re.IGNORECASE)
        _rest = re.sub(r"/?\s*h\.?p\.?f\.?|per\s+field|[:\-–]\s*$", " ", _rest,
                       flags=re.IGNORECASE)
        m = re.search(r"(\d+\s*[-–]\s*\d+|\d+)", _rest)
        if m:
            return m.group(1).strip()
        return ""

    # No pus/WBC label anywhere. Fall back to a bare "N/HPF" ONLY when the report
    # names no competing analyte -- otherwise the first /HPF figure in the report
    # belongs to something else and must not be reported as a pus-cell count.
    if not re.search(r"r\.?\s*b\.?\s*c|red\s*b|erythro|cast|epithel|crystal|"
                     r"yeast|bacteri|حمراء|بلورات", text_l):
        for pat in patterns[2:]:
            m = re.search(pat, text_l, re.IGNORECASE)
            if m:
                return m.group(1).strip()
    return ""

def detect_rbcs(text: str) -> str:
    """استخرج قيمة RBCs من نص OCR."""
    import re
    patterns = [
        r"rbcs?\s*[:\-]?\s*(\d+\s*[-–]\s*\d+|\d+)",
        r"red\s*blood\s*cells?\s*[:\-]?\s*(\d+\s*[-–]\s*\d+|\d+)",
        r"كريات\s*حمراء\s*[:\-]?\s*(\d+\s*[-–]\s*\d+|\d+)",
        r"erythrocytes?\s*[:\-]?\s*(\d+\s*[-–]\s*\d+|\d+)",
    ]
    text_l = text.lower()
    for pat in patterns:
        m = re.search(pat, text_l, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # Handle text qualifiers for RBCs -- ONLY on a line that names red cells.
    # FIX 2026-11-11 (round 4): the old test ("TNTC somewhere, and the word
    # 'pus' not before it") turned "WBC: TNTC" / "Leucocytes: TNTC" into an RBC
    # value, and fired on any TNTC in a report with no pus label at all.
    for _ln in text_l.splitlines():
        if (re.search(r"tntc|too\s+numerous|full\s*field", _ln)
                and re.search(r"r\.?\s*b\.?\s*c|red\s*b|erythro|كريات\s*حمراء", _ln)
                and not re.search(r"pus|w\.?\s*b\.?\s*c|leu[ck]|صديد", _ln)):
            return "TNTC"
    # Fallback: find the /HPF line that actually NAMES red cells. Never guess by
    # position -- the old "second /HPF line" rule returned the pus-cell count as
    # RBCs whenever the RBC label was dotted (R.B.Cs), and fabricated a value from
    # the casts line on reports that had no RBC row at all.
    _RBC_LABEL = re.compile(r"r\.?\s*b\.?\s*c|red\s*b|erythro|كريات\s*حمراء|حمراء")
    _NOT_RBC   = re.compile(r"pus|w\.?\s*b\.?\s*c|leu[ck]|صديد|cast|epithel|crystal|"
                            r"bacteri|yeast|mucus|املاح|بلورات")
    hpf_lines = [l for l in text_l.splitlines() if "hpf" in l]
    _cands = [l for l in hpf_lines if _RBC_LABEL.search(l) and not _NOT_RBC.search(l)]
    if _cands:
        _rbc_l = _cands[0]
        m_ov = re.search(r"over\s*(\d+)|>\s*(\d+)", _rbc_l)
        if m_ov:
            n = m_ov.group(1) or m_ov.group(2)
            return f"Over {n}" if "over" in _rbc_l else f">{n}"
        m2 = re.search(r"(\d+\s*[-–]\s*\d+|\d+)", _rbc_l)
        if m2:
            return m2.group(1).strip()
    return ""

def detect_culture_condition(text: str) -> str:
    """استخرج نوع ظروف المزرعة: Aerobic / Anaerobic / Both."""
    import re
    text_l = text.lower()
    if re.search(r"both|aerobic\s*[&+]\s*anaerobic|anaerobic\s*[&+]\s*aerobic", text_l):
        return "Both (Aerobic + Anaerobic)"
    if re.search(r"anaerob", text_l):
        return "Anaerobic"
    if re.search(r"aerob", text_l):
        return "Aerobic"
    return ""
