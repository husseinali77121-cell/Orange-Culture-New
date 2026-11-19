"""v6.8 (2026-11-14): the reports are drawn with the shipped fonts, on every machine.

Reported from the Windows EXE: the decision-tree image's text was unreadably
small, and the PDF's font did not match the online app. Cause: every font path
in the code was a Linux path. On Windows the image fell back to Pillow's fixed
10-pixel default (on a canvas drawn at twice size), and the PDF to whatever
Windows had. The repository now ships the files (fonts/), and these tests hold
that the image and the PDF use them -- including on a machine with no system
fonts at all (simulated here by hiding /usr/share/fonts).
"""
import os
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def no_system_fonts(monkeypatch):
    """A machine like the Windows EXE's: none of the Linux font paths exist."""
    real_isfile, real_isdir = os.path.isfile, os.path.isdir

    def hidden(p):
        return str(p).replace("\\", "/").startswith("/usr/share/fonts")
    monkeypatch.setattr(os.path, "isfile", lambda p: False if hidden(p) else real_isfile(p))
    monkeypatch.setattr(os.path, "isdir", lambda p: False if hidden(p) else real_isdir(p))
    from cdss.reports import image_parts
    image_parts.gf.cache_clear()
    yield
    image_parts.gf.cache_clear()


def test_the_shipped_fonts_are_all_there_and_are_real_font_files():
    from cdss.reports.fonts import REQUIRED_FILES, fonts_dir
    d = fonts_dir()
    assert d == ROOT / "fonts"
    for name in REQUIRED_FILES:
        head = (d / name).read_bytes()[:4]
        assert head in (b"\x00\x01\x00\x00", b"true", b"OTTO"), f"{name} is not a TrueType/OpenType file"
    for lic in ("OFL-Noto.txt", "OFL-Amiri.txt", "LICENSE-DejaVu.txt"):
        assert (d / lic).is_file(), f"fonts/{lic} (licence) is missing"


def test_every_shipped_family_is_one_the_report_css_asks_for():
    from cdss.reports.fonts import FONT_FACES
    from cdss.reports.pdf_parts import PDF_CSS
    css = PDF_CSS + (ROOT / "cdss/reports/patho_pdf.py").read_text(encoding="utf-8") \
        + (ROOT / "cdss/reports/qa_pdf.py").read_text(encoding="utf-8")
    for family, *_ in FONT_FACES:
        assert f"'{family}'" in css, f"{family} is shipped but no report CSS names it"


def test_font_faces_are_registered_ahead_of_the_report_css():
    from cdss.reports.fonts import FONT_FACES, font_face_css, with_bundled_fonts
    css = font_face_css()
    assert css.count("@font-face") == len(FONT_FACES)
    assert "url('file:" in css and "format('truetype')" in css
    html = "<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{}</style></head><body>x</body></html>"
    out = with_bundled_fonts(html)
    assert out.index("@font-face") < out.index("body{}")
    assert out.replace("<style>\n" + css + "\n</style>", "") == html


def test_no_fonts_folder_leaves_the_html_untouched(monkeypatch):
    from cdss.reports import fonts
    monkeypatch.setattr(fonts, "fonts_dir", lambda: None)
    fonts.font_face_css.cache_clear()
    try:
        assert fonts.with_bundled_fonts("<html><head></head></html>") == "<html><head></head></html>"
    finally:
        fonts.font_face_css.cache_clear()


def test_every_pdf_writer_registers_the_shipped_fonts():
    # v7.0: the two one-page sheets write through fit_page.render_one_page,
    # which is the one place that registers the fonts for them.
    for f in ("report_service.py", "fit_page.py"):
        src = (ROOT / "cdss" / "reports" / f).read_text(encoding="utf-8")
        assert "_wp.HTML(string=with_bundled_fonts(" in src, f"{f} writes a PDF without the shipped fonts"
    for f in ("patho_pdf.py", "qa_pdf.py"):
        src = (ROOT / "cdss" / "reports" / f).read_text(encoding="utf-8")
        assert "render_one_page(build)" in src and "_wp.HTML(" not in src, \
            f"{f} must write through fit_page.render_one_page"


def test_image_font_is_the_shipped_file_even_with_no_system_fonts(no_system_fonts):
    pytest.importorskip("PIL")
    from cdss.reports.fonts import fonts_dir
    from cdss.reports.image_parts import S, gf
    for bold in (False, True):
        f = gf(14, bold)
        assert Path(f.path).parent == fonts_dir()
        assert f.size == 14 * S          # the bug: 10 pixels, whatever size was asked


def test_last_resort_font_is_still_full_size(monkeypatch, no_system_fonts):
    pytest.importorskip("PIL")
    from cdss.reports import image_parts
    monkeypatch.setattr(image_parts, "font_file", lambda name: None)
    real_isfile, real_isdir = os.path.isfile, os.path.isdir
    monkeypatch.setattr(os.path, "isfile", lambda p: False if str(p).endswith((".ttf", ".otf")) else real_isfile(p))
    monkeypatch.setattr(os.path, "isdir", lambda p: False)
    image_parts.gf.cache_clear()
    f = image_parts.gf(14)
    if not hasattr(f, "size"):
        pytest.skip("Pillow < 10.1 has no scalable default font")
    assert f.size == 14 * image_parts.S


def test_decision_tree_image_is_identical_with_and_without_system_fonts(monkeypatch):
    pytest.importorskip("PIL")
    from cdss.common.clinical_utils import Patient
    from cdss.pipeline import run_analysis
    import cdss.reports.report_service as RS
    from cdss.reports import image_parts
    sir = {"Ampicillin": "R", "Ceftriaxone": "R", "Meropenem": "S", "Nitrofurantoin": "S",
           "Trimethoprim/Sulfamethoxazole": "S", "Gentamicin": "S"}
    r = run_analysis(Patient(age_years=62, sex="Female"), "Escherichia coli", "Urine", sir)

    def draw():
        image_parts.gf.cache_clear()
        names = [d["name"] for d in r["ranked"]]
        return RS.generate_decision_tree_image(
            patient_name="محمد أحمد", age=62, sex="Female", weight=70, cl_cr=80, is_renal=False, is_preg=False,
            organism="Escherichia coli", specimen="Urine", first_line=names[:2], preferred=names[2:6],
            use_caution=[d["name"] for d in r["warned"]], contraindicated=[d["name"] for d in r["banned"]],
            reserve=[], notes=[], colony_count=">10^5", date_in="2026-11-14", pus_cells="20-25", rbcs="3-5",
            lab_name="Orange Lab", lab_city="6 October", mdr_result=r["mdr"], esbl_result=r["mechanism"],
            phenotypes=r["phenotypes"], age_months=None)
    here = draw()
    real_isfile, real_isdir = os.path.isfile, os.path.isdir
    hide = lambda p: str(p).replace("\\", "/").startswith("/usr/share/fonts")   # noqa: E731
    monkeypatch.setattr(os.path, "isfile", lambda p: False if hide(p) else real_isfile(p))
    monkeypatch.setattr(os.path, "isdir", lambda p: False if hide(p) else real_isdir(p))
    try:
        windows_like = draw()
    finally:
        image_parts.gf.cache_clear()
    assert here and here == windows_like


def test_image_titles_lose_their_unprintable_emoji():
    from cdss.reports.image_parts import image_glyph_guard
    assert image_glyph_guard("🔬  ORANGE LAB") == "◆  ORANGE LAB"
    assert image_glyph_guard("🛡  RESERVE (WHO)") == "RESERVE (WHO)"
    assert image_glyph_guard("⚠  ESBL ALERT") == "⚠  ESBL ALERT"
    assert image_glyph_guard("محمد") == "محمد"


def test_embedded_font_names_reads_plain_and_compressed_pdfs():
    from cdss.reports.fonts import embedded_font_names, missing_families
    plain = b"%PDF-1.7\n1 0 obj << /Type /Font /BaseFont /ABCDEF+NotoSerif-Regular >> endobj\n"
    packed = zlib.compress(b"<< /Type /Font /BaseFont /QWERTY+Amiri-Bold >> "
                           b"<< /BaseFont /DejaVuSans >> << /BaseFont /XYZABC+NotoSans-Bold >>")
    pdf = plain + b"2 0 obj << /Type /ObjStm /Filter /FlateDecode >>\nstream\n" + packed + b"\nendstream\nendobj\n"
    assert embedded_font_names(pdf) == {"NotoSerif-Regular", "Amiri-Bold", "DejaVuSans", "NotoSans-Bold"}
    assert missing_families(pdf) == []
    assert missing_families(plain) == ["Noto Sans", "Amiri", "DejaVu Sans"]


def test_the_exe_proves_its_fonts_and_the_build_no_longer_downloads_them():
    launcher = (ROOT / "launcher.py").read_text(encoding="utf-8")
    for step in ("shipped report fonts (fonts/)", "decision-tree image draws with the shipped font",
                 "PDF embeds Noto Serif / Noto Sans / Amiri / DejaVu Sans"):
        assert step in launcher
    assert "ORANGE_CDSS_FONTS_DIR" in launcher
    wf = (ROOT / ".github" / "workflows" / "build-exe.yml").read_text(encoding="utf-8")
    assert "python tools/check_report_fonts.py" in wf
    assert "NotoNaskhArabic-Regular.ttf\" = \"https" not in wf      # the old download-and-warn step
    assert '"fonts/**"' in wf
