# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""HTML escaping and PDF glyph safety for the report writers."""



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
