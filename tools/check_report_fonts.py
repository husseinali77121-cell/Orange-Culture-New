"""Prove which font files draw the reports (v6.8).

    python tools/check_report_fonts.py

Exit 0 only if:
  * the shipped fonts folder (fonts/) is found and complete;
  * the decision-tree image loads the shipped DejaVu Sans at full size
    (the Windows EXE used to fall back to Pillow's 10-pixel default);
  * a PDF in the clinical report's CSS embeds Noto Serif, Noto Sans, Amiri and
    DejaVu Sans -- read back from the PDF itself, not assumed from the CSS.

The Windows build runs this before PyInstaller (build-exe.yml), and the EXE
runs the same checks on itself in --selftest.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from cdss.reports.fonts import (REQUIRED_FILES, font_probe_pdf, fonts_dir,
                                    embedded_font_names, missing_families)
    from cdss.reports.image_parts import S, gf

    d = fonts_dir()
    if d is None:
        print("FAIL: no fonts/ folder with NotoSerif-Regular.ttf was found")
        return 1
    absent = [f for f in REQUIRED_FILES if not (d / f).is_file()]
    if absent:
        print(f"FAIL: fonts/ is missing {absent}")
        return 1
    print(f"OK   fonts folder: {d} ({len(REQUIRED_FILES)} files)")

    f = gf(14)
    path = getattr(f, "path", "")
    if not (isinstance(path, str) and os.path.dirname(os.path.abspath(path)) == str(d)
            and getattr(f, "size", 0) == 14 * S):
        print(f"FAIL: decision-tree image font is {path or 'the built-in default'} "
              f"at size {getattr(f, 'size', '?')} (expected {d}/DejaVuSans.ttf at {14 * S})")
        return 1
    print(f"OK   decision-tree image font: {path} at {f.size}px")

    try:
        pdf = font_probe_pdf()
    except ImportError:
        print("SKIP PDF check: WeasyPrint is not installed here")
        return 0
    missing = missing_families(pdf)
    names = sorted(embedded_font_names(pdf))
    if missing:
        print(f"FAIL: the PDF does not embed {missing}; it embeds {names}")
        return 1
    print(f"OK   PDF embeds: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
