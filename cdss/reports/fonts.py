# -*- coding: utf-8 -*-
# © Dr. Hussein Ali — Orange Lab, 6 October City, Egypt
# Microbiology CDSS — All Rights Reserved
"""The fonts the reports are drawn with, shipped with the program.

Added v6.8 (2026-11-14). Online, Streamlit Cloud installs Noto, Amiri and
DejaVu from packages.txt, and the PDF CSS and the decision-tree image found
them under /usr/share/fonts. The Windows EXE has none of them:

  * the PDF fell back to whatever Windows had (Times New Roman, Segoe UI), so
    the offline report did not look like the online one;
  * the decision-tree image found no font file at all and fell back to
    Pillow's built-in default -- a fixed 10-pixel face on a canvas drawn at
    twice size, so every word was unreadably small.

The repository now carries the exact files (fonts/, see fonts/README.md).
This module finds that folder -- beside the code, or inside the EXE -- and

  * font_face_css() / with_bundled_fonts(): registers the files with
    WeasyPrint through @font-face, under the SAME family names the CSS already
    asks for ('Noto Serif', 'Noto Sans', 'Amiri', 'Noto Naskh Arabic',
    'DejaVu Sans'), so every stack resolves to the shipped file on every
    machine;
  * font_file(): gives the image renderer a path to load.

Nothing here changes what a report says -- only which font file draws it.
"""
import functools
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# (CSS family, weight, style, file) -- the family names are the ones the
# report CSS uses; do not rename them without changing the CSS.
FONT_FACES: Tuple[Tuple[str, int, str, str], ...] = (
    ("Noto Serif", 400, "normal", "NotoSerif-Regular.ttf"),
    ("Noto Serif", 700, "normal", "NotoSerif-Bold.ttf"),
    ("Noto Serif", 400, "italic", "NotoSerif-Italic.ttf"),
    ("Noto Serif", 700, "italic", "NotoSerif-BoldItalic.ttf"),
    ("Noto Sans", 400, "normal", "NotoSans-Regular.ttf"),
    ("Noto Sans", 700, "normal", "NotoSans-Bold.ttf"),
    ("Amiri", 400, "normal", "Amiri-Regular.ttf"),
    ("Amiri", 700, "normal", "Amiri-Bold.ttf"),
    ("Noto Naskh Arabic", 400, "normal", "NotoNaskhArabic-Regular.ttf"),
    ("Noto Naskh Arabic", 700, "normal", "NotoNaskhArabic-Bold.ttf"),
    ("DejaVu Sans", 400, "normal", "DejaVuSans.ttf"),
    ("DejaVu Sans", 700, "normal", "DejaVuSans-Bold.ttf"),
)
REQUIRED_FILES: Tuple[str, ...] = tuple(f for *_, f in FONT_FACES)

# A folder counts only if it has the file every report needs first.
_MARKER = "NotoSerif-Regular.ttf"


def _candidate_dirs() -> List[Path]:
    out: List[Path] = []
    env = os.environ.get("ORANGE_CDSS_FONTS_DIR")          # set by launcher.py in the EXE
    if env:
        out.append(Path(env))
    meipass = getattr(sys, "_MEIPASS", None)                # PyInstaller's unpack folder
    if meipass:
        out.append(Path(meipass) / "fonts")
    out.append(Path(__file__).resolve().parents[2] / "fonts")   # <repo>/fonts
    return out


@functools.lru_cache(maxsize=None)
def fonts_dir() -> Optional[Path]:
    """The shipped fonts folder, or None if this copy of the program has none."""
    for d in _candidate_dirs():
        try:
            if (d / _MARKER).is_file():
                return d
        except OSError:
            continue
    return None


def font_file(name: str) -> Optional[str]:
    """Absolute path of a shipped font file, or None."""
    d = fonts_dir()
    if d is None:
        return None
    p = d / name
    return str(p) if p.is_file() else None


@functools.lru_cache(maxsize=None)
def font_face_css() -> str:
    """@font-face rules for every shipped file that is present ("" if none)."""
    d = fonts_dir()
    if d is None:
        return ""
    rules = []
    for family, weight, style, fname in FONT_FACES:
        p = d / fname
        if not p.is_file():
            continue
        rules.append(
            "@font-face { font-family: '%s'; font-weight: %d; font-style: %s; "
            "src: url('%s') format('truetype'); }" % (family, weight, style, p.resolve().as_uri()))
    return "\n".join(rules)


def with_bundled_fonts(html: str) -> str:
    """`html` with the shipped fonts registered ahead of the report's own CSS.

    Used on the way into WeasyPrint only (the HTML a test or the preview sees
    is unchanged). With no fonts folder the HTML is returned as it is, and the
    CSS stacks fall back to installed fonts exactly as before.
    """
    css = font_face_css()
    if not css:
        return html
    block = "<style>\n" + css + "\n</style>"
    low = html[:4000].lower()
    i = low.find("<head")
    if i != -1:
        j = html.find(">", i)
        if j != -1:
            return html[:j + 1] + block + html[j + 1:]
    return block + html


def embedded_font_names(pdf: bytes) -> set:
    """Base names of the fonts a PDF embeds ("NotoSerif-Regular", "Amiri-Bold", ...).

    Used by the EXE self-test and by tools/check_report_fonts.py to PROVE which
    files drew a report, rather than trusting the CSS. Reads the /BaseFont
    entries both in the plain file and inside compressed (Flate) streams,
    because WeasyPrint may pack its font dictionaries into object streams.
    """
    import re
    import zlib
    pat = re.compile(rb"/BaseFont\s*/([A-Za-z0-9+_.\-]+)")
    chunks = [pdf]
    for m in re.finditer(rb"stream\r?\n", pdf):
        start = m.end()
        end = pdf.find(b"endstream", start)
        if end == -1:
            continue
        try:
            chunks.append(zlib.decompress(pdf[start:end]))
        except zlib.error:
            try:
                chunks.append(zlib.decompressobj().decompress(pdf[start:end]))
            except zlib.error:
                continue
    names = set()
    for c in chunks:
        for raw in pat.findall(c):
            name = raw.decode("latin-1")
            names.add(name.split("+", 1)[1] if "+" in name else name)   # drop the subset tag
    return names


# Family -> the substring its embedded name carries (case- and hyphen-blind).
EXPECTED_IN_PDF = {"Noto Serif": "notoserif", "Noto Sans": "notosans",
                   "Amiri": "amiri", "DejaVu Sans": "dejavusans"}


def missing_families(pdf: bytes) -> list:
    """Shipped families that a report PDF should embed but does not."""
    names = {n.lower().replace("-", "").replace("_", "") for n in embedded_font_names(pdf)}
    return [fam for fam, key in EXPECTED_IN_PDF.items() if not any(key in n for n in names)]


def font_probe_pdf() -> bytes:
    """A one-page PDF in the clinical report's own CSS, touching every shipped family:
    serif prose (Noto Serif), a data cell (Noto Sans), an Arabic run (Amiri) and the
    report's symbols (DejaVu Sans). Needs WeasyPrint."""
    import weasyprint
    from cdss.reports.html_utils import pdf_glyph_guard
    from cdss.reports.pdf_parts import PDF_CSS
    html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            + PDF_CSS.replace("@@LABFOOT@@", "Orange Lab") + "</style></head><body>"
            "<div class='hdr'><div class='hdr-lab'>ORANGE LAB</div>"
            "<div class='hdr-pt'>محمد أحمد</div></div>"
            "<p>Recommended therapy <b>first line</b> <i class='sci'>Escherichia coli</i></p>"
            "<table class='ast'><tr><td>Ceftriaxone 1 g IV q24h</td><td>12.5</td></tr></table>"
            "<p class='ar rtl'>يُعطى بعد الأكل مرتين يومياً</p>"
            "<p>✓ ✗ ⊘ ◆ ● ▣ ▲ ⚠ ≥ ≤ →</p></body></html>")
    return weasyprint.HTML(string=with_bundled_fonts(pdf_glyph_guard(html))).write_pdf()
