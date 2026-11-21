# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""HTML escaping and PDF glyph safety for the report writers; the short
labels the Clinical Tree and the PDF print beside a drug (v7.9)."""
from typing import Any, Dict, Iterable, Mapping, Optional



# =========================================================
# أدوات رسم الصورة
# =========================================================
def _score_color(score: int) -> str:
    if score >= 75: return "#922b21"
    if score >= 50: return "#b7770d"
    if score >= 30: return "#e67e22"
    return "#1e8449"

def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))

def _md_inline(text: str) -> str:
    """Escape HTML, then render the tiny markdown subset the QC messages use:
    **bold** -> <b>, markdown line breaks -> <br>. Used for AST-QA issues whose
    text comes from the reportability / consistency modules."""
    import re as _re
    out = _esc(text)
    out = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = out.replace("  \n", "<br>").replace("\n", "<br>")
    return out

import re as _re_bidi

# A Latin run inside Arabic text: starts with a letter / digit / "(", may carry
# spaces and the punctuation drug names and citations use, ends on a letter,
# digit, ")" "%" or ".".
_LATIN_RUN = _re_bidi.compile(
    r"[A-Za-z0-9(][A-Za-z0-9\-+/.,()%:'≥≤<>=·×µ ]*[A-Za-z0-9).%]|[A-Za-z0-9]")
_ARABIC = _re_bidi.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
LRI, PDI = "\u2066", "\u2069"


def bidi_isolate(text: str) -> str:
    """Wrap every Latin run of an ARABIC sentence in LRI ... PDI (v7.0).

    Review 2026-11-19: in the QA sheet's Organism Summary, sentences such as
    "مقاومة جوهرية: Colistin · Nitrofurantoin (CLSI M100 Appendix B1)" came out
    with the English words and the brackets in the wrong order -- the Unicode
    bidi algorithm treats the punctuation between neutral-direction runs by the
    paragraph direction. An isolate makes each English run one LTR unit.
    Text with no Arabic is returned unchanged. Apply BEFORE escaping.
    """
    if not isinstance(text, str) or not _ARABIC.search(text):
        return text

    def _iso(run: str) -> str:
        # an unmatched bracket stays OUTSIDE the isolate, where the bidi
        # algorithm pairs it with its partner in the Arabic text
        depth, cut = 0, -1
        for i, ch in enumerate(run):
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    cut = i
                    break
                depth -= 1
        if cut < 0 and depth > 0:
            d = 0
            for i in range(len(run) - 1, -1, -1):
                if run[i] == ")":
                    d += 1
                elif run[i] == "(":
                    if d == 0:
                        cut = i
                        break
                    d -= 1
        if cut >= 0:
            return _iso(run[:cut]) + run[cut] + _iso(run[cut + 1:])
        core = run.strip()
        if not core or not any(c.isalnum() for c in core):
            return run
        i = run.find(core)
        return run[:i] + LRI + core + PDI + run[i + len(core):]

    def _wrap(m):
        return _iso(m.group(0))

    return _LATIN_RUN.sub(_wrap, text)


# ══════════════════════════════════════════════════════════════════════════
# PDF GLYPH GUARD
# ══════════════════════════════════════════════════════════════════════════
# The deployment image (see packages.txt) ships Liberation Sans, Amiri and
# DejaVu Sans. None of them carry emoji. Any emoji reaching WeasyPrint is
# therefore drawn as a .notdef tofu box -- which is what produced the
# "[] Orange Lab" / "[] E. coli" / "[] (R)" boxes in the shipped advisory.
#
# Every replacement below was verified present in DejaVu Sans, so it renders
# as real vector outline: crisp at any zoom, unlike a bitmap emoji font.
_PDF_GLYPH_MAP = {
    # --- status / verdict ------------------------------------------------
    "\u2705":     "\u2713",   # white heavy check   -> check mark
    "\u274C":     "\u2717",   # cross mark          -> ballot X
    "\u2795":     "+",        # heavy plus          -> plus
    "\u2796":     "\u2212",   # heavy minus         -> minus sign
    "\u2757":     "\u26A0",   # exclamation         -> warning sign
    "\u2696":     "\u25C6",   # balance scale       -> black diamond
    "\u2753":     "?",        # question            -> question mark
    # --- prohibition ----------------------------------------------------
    "\U0001F6AB": "\u2298",   # no entry sign       -> circled slash
    "\u26D4":     "\u2298",   # no entry            -> circled slash
    "\U0001F6D1": "\u2298",   # stop sign           -> circled slash
    # --- lab / clinical -------------------------------------------------
    "\U0001F52C": "\u25C6",   # microscope          -> black diamond
    "\U0001F9A0": "\u25CF",   # microbe             -> black circle
    "\U0001F9EB": "\u25C6",   # petri dish          -> black diamond
    "\U0001F48A": "\u2295",   # pill                -> circled plus
    "\U0001F930": "\u26A0",   # pregnant woman      -> warning sign
    "\U0001F489": "",         # syringe             -> drop (decorative)
    "\U0001F3E5": "",         # hospital            -> drop
    "\U0001F3AF": "",         # dart                -> drop
    # --- documents ------------------------------------------------------
    "\U0001F4CB": "\u25A3",   # clipboard           -> framed square
    "\U0001F4DA": "\u00A7",   # books               -> section sign
    "\U0001F4D6": "\u00A7",   # open book           -> section sign
    "\U0001F4C4": "\u25A3",   # page                -> framed square
    # --- alerts ---------------------------------------------------------
    "\U0001F6A8": "\u25B2",   # siren               -> black up triangle
    "\U0001F504": "\u21BB",   # cycle arrows        -> clockwise arrow
    # --- colour-coded status dots ---------------------------------------
    # NOTE: colour is LOST here. These should be CSS-coloured spans at
    # source, not emoji -- see PDF_RENDER_AUDIT.md, finding F9.
    "\U0001F534": "\u25CF",   # red circle
    "\U0001F7E2": "\u25CF",   # green circle
    "\U0001F7E1": "\u25CF",   # yellow circle
    "\U0001F7E0": "\u25CF",   # orange circle
    "\U0001F535": "\u25CF",   # blue circle
    "\U0001F536": "\u25C6",   # large orange diamond
    "\U0001F539": "\u25C6",   # small blue diamond
    "\U0001F7E3": "\u25CF",   # purple circle
}

# Symbols confirmed present in DejaVu Sans -- must survive the sweep below.
_PDF_SAFE_SYMBOLS = frozenset(
    "\u2713\u2717\u2298\u25C6\u25CF\u25CB\u25A3\u25AA\u25B2\u21BB"
    "\u26A0\u2295\u00A7\u2022\u2192\u2264\u2265\u2261\u00B7\u2014\u2013"
)

def pdf_glyph_guard(html: str) -> str:
    """Make `html` renderable by the fonts actually installed.

    1. Maps known emoji to DejaVu-backed vector equivalents.
    2. Drops anything still in an emoji range -- no installed font can draw
       it, so leaving it in guarantees a tofu box. Dropping is strictly
       better than shipping a box into a clinical document.
    3. Strips VS-15/VS-16 selectors, which tofu on their own.
    """
    out = []
    for ch in html:
        if ch in _PDF_SAFE_SYMBOLS:
            out.append(ch)
            continue
        mapped = _PDF_GLYPH_MAP.get(ch)
        if mapped is not None:
            out.append(mapped)
            continue
        o = ord(ch)
        if (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF
                or 0x2B00 <= o <= 0x2BFF or o in (0xFE0E, 0xFE0F)
                or 0x1F1E6 <= o <= 0x1F1FF):
            continue
        out.append(ch)
    return "".join(out)


# ═══════════ Clinical Tree / PDF labels (v7.9) ═══════════
# Short labels the Clinical Tree image prints beside a drug (v7.9).
#
# Moved out of cdss_ui/report_panels.py so they can be tested without Streamlit.
# Kept in this module (not a new file) so cdss/ stays within GitHub's
# 100-files-per-browser-upload limit (NEW_REPO_SETUP.md).
# External case review 2026-11-21 (Klebsiella spp., suprapubic catheter):
#
#   * "Ofloxacin (FQ low-level R)" -- an S result printed with an R and a
#     mechanism that two disk results cannot prove. The tag now keeps the S and
#     says what settles it: "(S · confirm by CIP/LEV)".
#   * "Ertapenem (I)" -- carbapenem non-susceptibility looked like any other I.
#     It now says the work-up is pending, without calling the isolate a
#     carbapenemase producer: "(I · carbapenemase test)".
#   * "Cefepime (I)" -- CLSI M100 Ed36 has no I for this pair; the printed I is
#     SDD or R by MIC and cannot be used as it stands: "(I unverified · MIC)".
#   * "Best available: Gentamicin" -- the only S agent is a candidate, not a
#     verdict; the strategy line says what it still depends on.
CAUTION_TAG: Dict[str, str] = {
    "fq_low_level": "(S · confirm by CIP/LEV)", "esbl_bli_uti_only": "(ESBL: alternative)",
    "intermediate_culture": "(I)", "renal_adjustment": "(Renal dose)",
    "hepatic_adjustment": "(Hepatic dose)", "no_breakpoint": "(No breakpoint)",
    "legacy_breakpoint": "(Old criterion)", "organism_caution": "(Organism)",
    "possible_carbapenemase": "(Carbapenemase test)", "safety_gate": "(Site / host)",
    "allergy": "(Allergy)", "interaction": "(Interaction)", "pregnancy": "(Pregnancy)",
    "ampc_sdd": "(SDD dose)", "ampc_cefepime": "(AmpC)", "child_fq": "(Pediatric)",
    "uti_upper": "(Cystitis only)", "novel_agent": "(Novel agent)",
    "idsa_new_agent": "(IDSA 2026 note)", "esbl_not_excluded": "(ESBL not excluded)",
}

_CARBAPENEMS = ("Ertapenem", "Meropenem", "Imipenem/Cilastatin")

# The physician PDF tier for the first ranked agent when no guideline list is
# behind the rank (it used to say "PRIMARY").
POTENTIAL_PREFERRED = "POTENTIAL PREFERRED OPTION — subject to renal check, severity, specialist review"


def caution_label(item: Mapping[str, Any], organism: str = "",
                  sir_map: Optional[Mapping[str, Any]] = None,
                  sdd_drugs: Iterable[str] = ()) -> str:
    """'Name (why)' for the USE WITH CAUTION column."""
    name = str(item.get("name") or "")
    reason = item.get("warning_reason") or item.get("category") or ""
    tag = CAUTION_TAG.get(reason, "")
    res = str((sir_map or {}).get(name, "") or "").strip().upper()
    if reason == "intermediate_culture" and name in set(sdd_drugs or ()):
        tag = "(SDD)"
    elif res == "I" and name not in set(sdd_drugs or ()):
        from cdss.astqc.phenotype_plausibility import _is_entero, no_i_pair
        if no_i_pair(name, organism):
            tag = "(I unverified · MIC)"
        elif name in _CARBAPENEMS and _is_entero((organism or "").lower()):
            tag = "(I · carbapenemase test)"
    return f"{name} {tag}".strip()


def top_option_line(name: str, route: str, *, guideline_alternative: bool = False) -> str:
    """The CLINICAL STRATEGY line for the first ranked agent.

    "Best available" read as a verdict. An S result makes an agent a candidate;
    infection severity, renal function, the pending mechanism work-up and the
    treating physician / ID review decide.
    """
    if guideline_alternative:
        return f"IDSA alternative: {name} [{route}]"
    return f"Potential option: {name} [{route}] - renal fn, severity, ID review"
