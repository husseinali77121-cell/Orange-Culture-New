# -*- coding: utf-8 -*-
# © Dr. Hussein Ali — Orange Lab, 6 October City, Egypt
# Microbiology CDSS — All Rights Reserved
"""Drawing helpers of the decision-tree image: palette, fonts, boxes, wrapped text.

Split out of report_service.generate_decision_tree_image() (v6.7, 2026-11-14),
where they were closures over the function's scale factor `S`. The image is
drawn at S = 2 and that is the only scale it is drawn at, so S is a module
constant here; the bodies are otherwise unchanged and the image bytes are held
to the pre-split output by tests/test_report_split.py.
"""
import functools

from cdss.common.optional_deps import ARABIC_SUPPORT
from cdss.common.optional_deps import ImageFont
from cdss.common.optional_deps import _arabic_reshaper_mod

S = 2      # the image's scale factor -- generate_decision_tree_image() asserts it matches

# ── Color Palette (identical to reference) ────────────────────────────────
BG         = (248, 250, 252)
WHITE      = (255, 255, 255)
DARK       = (28,  32,  40)
GRAY       = (95, 100, 112)
LIGHT_GRAY = (190, 195, 205)

NAVY       = (4,   26,  63)
PURPLE_BD  = (120, 75, 178);  PURPLE_BG  = (247, 243, 254)
GREEN_BD   = (45, 138,  68);  GREEN_BG   = (236, 252, 240);  GREEN_TXT  = (20,  95,  40)
AMBER_BD   = (195,140,  30);  AMBER_BG   = (255, 250, 228);  AMBER_TXT  = (120,  80,   0)
RED_BD     = (183, 52,  52);  RED_BG     = (255, 237, 234);  RED_TXT    = (148,  30,  30)
BLUE_BD    = (35,  90, 172);  BLUE_BG    = (234, 244, 255);  BLUE_TXT   = (15,   55, 145)
ALERT_BD   = (205,115,  50);  ALERT_BG   = (255, 248, 232);  ALERT_TXT  = (130,  60,   5)
SPEC_BD    = (35,  90, 172);  SPEC_BG    = (234, 244, 255)
MICRO_BD   = (30, 130,  65);  MICRO_BG   = (234, 252, 238)
FL_BD      = (190,138,  28);  FL_BG      = (255, 250, 225)
FOOT_BD    = (185,192,200);   FOOT_BG    = (247, 249, 251)

# ── Fonts (all scaled) ────────────────────────────────────────────────────
@functools.lru_cache(maxsize=None)   # v6.7: text_wrap() re-loaded the font file on every shrink step
def gf(size: int, bold: bool = False):
    """
    Robust font loader with comprehensive fallbacks.
    Priority: Liberation Sans -> DejaVu -> NotoSans -> Amiri -> auto-discover
    Liberation/DejaVu give the clean sans-serif look of the old images.
    NotoSans/Amiri are fallbacks for Streamlit Cloud if Liberation not found.
    """
    import os as _os
    _b = "Bold" if bold else "Regular"
    paths = [
        # ── DejaVu Sans FIRST -- supports Arabic Unicode (fonts-dejavu-core) ─
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/dejavu-sans/DejaVuSans{'-Bold' if bold else ''}.ttf",
        # ── Liberation Sans (fonts-liberation in packages.txt) ──────────────
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{_b}.ttf",
        f"/usr/share/fonts/truetype/liberation2/LiberationSans-{_b}.ttf",
        f"/usr/share/fonts/liberation/LiberationSans-{_b}.ttf",
        # ── Noto Sans (fonts-noto-core in packages.txt) -- clean sans-serif ──
        f"/usr/share/fonts/truetype/noto/NotoSans-{_b}.ttf",
        f"/usr/share/fonts/truetype/noto/NotoSans{'Bold' if bold else 'Regular'}.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        # ── Amiri (fonts-hosny-amiri in packages.txt) -- Arabic+Latin ────────
        f"/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-{_b}.ttf",
        f"/usr/share/fonts/opentype/fonts-hosny-amiri/amiri-{'bold' if bold else 'regular'}.ttf",
        f"/usr/share/fonts/truetype/amiri/Amiri-{_b}.ttf",
        # ── Other common fonts ───────────────────────────────────────────────
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/ubuntu/Ubuntu-{'B' if bold else 'R'}.ttf",
    ]
    for p in paths:
        if _os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size * S)
            except Exception:
                continue
    # Auto-discover: search for ANY usable sans-serif font
    for _fdir in ["/usr/share/fonts/truetype", "/usr/share/fonts/opentype",
                  "/usr/share/fonts"]:
        if not _os.path.isdir(_fdir):
            continue
        try:
            for _root, _, _files in _os.walk(_fdir):
                for _f in sorted(_files):   # sorted = deterministic order
                    if not _f.lower().endswith((".ttf", ".otf")):
                        continue
                    _fl = _f.lower()
                    if any(k in _fl for k in
                           ("liberation", "dejavu", "notosans", "noto-sans",
                            "ubuntu", "freesans", "amiri", "arial", "sans")):
                        try:
                            return ImageFont.truetype(
                                _os.path.join(_root, _f), size * S)
                        except Exception:
                            continue
        except Exception:
            continue
    return ImageFont.load_default()



def fh(f) -> int:
    return f.size if hasattr(f, "size") else 14 * S

def tw(draw, text, font) -> float:
    try:
        return draw.textlength(text, font=font)
    except Exception:
        return len(text) * fh(font) * 0.6

# ── Arabic text helper ────────────────────────────────────────────────────
def _fix_arabic(text: str) -> str:
    """
    Reshape Arabic text for Pillow.
    reshape() connects letters correctly.
    get_display() reverses word order -- NOT used here to avoid reversal.
    """
    if not text:
        return ""
    if not ARABIC_SUPPORT:
        return str(text)
    try:
        return _arabic_reshaper_mod.reshape(str(text))
    except Exception:
        return str(text)

def rbox(draw, box, bg, bd, radius=14, width=3):
    draw.rounded_rectangle(
        [box[0], box[1], box[2], box[3]],
        radius=radius * S, fill=bg, outline=bd, width=width * S
    )

def text_wrap(draw, x, y, text, font, fill, max_w, gap=4, max_y=None, min_size=7):
    """
    Word-wraps text within max_w. If max_y is given and the wrapped
    text would cross that boundary at the current font size, the font
    is progressively shrunk (down to min_size) so the text always
    stays inside its box; if it still doesn't fit at min_size, the
    last visible line is truncated with "…" instead of overflowing
    past the border.
    """
    text = _fix_arabic(text)   # reshape Arabic before wrapping

    def _wrap(f):
        words = text.split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if tw(draw, trial, f) <= max_w:
                cur = trial
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines

    f = font
    lines = _wrap(f)
    lh = fh(f) + gap * S

    if max_y is not None and (y + lh * len(lines)) > max_y:
        nominal = max(min_size, int(fh(font) / S) - 1)
        for step in range(nominal, min_size - 1, -1):
            f2 = gf(step)
            lines2 = _wrap(f2)
            lh2 = fh(f2) + gap * S
            if (y + lh2 * len(lines2)) <= max_y:
                f, lines, lh = f2, lines2, lh2
                break
        else:
            f = gf(min_size)
            lines = _wrap(f)
            lh = fh(f) + gap * S
            max_lines = max(1, int((max_y - y) // lh))
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines[-1] = lines[-1].rstrip() + "…"

    for line in lines:
        draw.text((x, y), line, fill=fill, font=f)
        y += lh
    return y

# AWaRe colors -- Access أخضر، Watch برتقالي
AWARE_NAME_COLORS = {
    "[A]": (20, 138, 68),    # أخضر -- Access
    "[W]": (180, 100,  0),   # برتقالي -- Watch
    "[NR]": (90, 90, 90),    # رمادي -- WHO "Not Recommended"
}

def section_box(draw, box, title, title_color, subtitle, items, bg, bd,
                ft, fs, fi):
    x1, y1, x2, y2 = box
    rbox(draw, box, bg, bd, radius=16, width=3)
    draw.text((x1 + 14*S, y1 + 12*S), _fix_arabic(title), fill=title_color, font=ft)
    cy = y1 + 12*S + fh(ft) + 6*S
    if subtitle:
        draw.text((x1 + 14*S, cy), _fix_arabic(subtitle), fill=(110,115,125), font=fs)
        cy += fh(fs) + 4*S
    draw.line([(x1 + 10*S, cy), (x2 - 10*S, cy)], fill=bd, width=1*S)
    cy += 8*S
    for item in items:
        if cy + fh(fi) + 7*S > y2 - 8*S:
            draw.text((x1 + 14*S, cy), "…", fill=LIGHT_GRAY, font=fi)
            break
        # استخراج badge [A] أو [W]
        badge = ""
        display_name = item
        for b in ["[A]", "[W]", "[NR]"]:
            if item.endswith(b):
                badge = b
                display_name = item[:-len(b)].rstrip() + (" (WHO: not recommended)" if b == "[NR]" else "")
                break
        # لون الاسم حسب AWaRe
        name_color = AWARE_NAME_COLORS.get(badge, DARK)
        cy = text_wrap(draw, x1 + 14*S, cy, f"• {display_name}",
                       fi, name_color, x2 - x1 - 26*S, gap=5, max_y=y2-8*S)
