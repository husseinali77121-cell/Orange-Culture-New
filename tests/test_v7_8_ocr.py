"""v7.8: reading AST tables from report images by POSITION (external review of v7.7).

Measured before the change on rendered reports: one result per line 2 of 7,
Sensitive / Resistant columns 0 of 7, side-by-side lists 0 of 7 -- because
image_to_string throws positions away and Tesseract reads a lone "S" as "5".

The standard (the review's): no wrong S from the OCR, and nothing dropped
without being shown to the operator. Every layout below is rendered as a real
image and read by the real OCR; the tests that need Tesseract skip without it.
"""
from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.ocr.detect import detect_no_growth  # noqa: E402
from cdss.ocr.extract import merge_readings  # noqa: E402

TRUTH = {"Amikacin": "S", "Ciprofloxacin": "R", "Cefepime": "S", "Ceftriaxone": "R",
         "Nitrofurantoin": "S", "Imipenem/Cilastatin": "S", "Gentamicin": "I"}
SHOWN = {k: k.split("/")[0] for k in TRUTH}            # "Imipenem" printed
HEAD = ["Patient: Test Case        Age: 45 Y        Sex: Female",
        "Specimen: Urine (Mid stream)", "Organism: Escherichia coli",
        "Colony count: >100,000 CFU/ml", ""]


def _ocr_ready():
    try:
        import cv2  # noqa: F401
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:
        return False
    return shutil.which("tesseract") is not None and (ROOT / "fonts" / "DejaVuSans.ttf").exists()


needs_ocr = pytest.mark.skipif(not _ocr_ready(), reason="Tesseract / OpenCV / Pillow not installed")


def _render(items, grid=None, noisy=False):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    f = ImageFont.truetype(str(ROOT / "fonts" / "DejaVuSans.ttf"), 30)
    fb = ImageFont.truetype(str(ROOT / "fonts" / "DejaVuSans-Bold.ttf"), 32)
    w, h = 1700, 1500
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    y = 40
    for t in HEAD:
        d.text((60, y), t, font=f, fill=0)
        y += 48
    for x, yy, t, bold in items:
        d.text((x, y + yy), t, font=fb if bold else f, fill=0)
    if grid:
        xs, rows = grid
        for x in xs:
            d.line([(x, y - 10), (x, y + 60 + 7 * 50)], fill=0, width=3)
        for yy in rows:
            d.line([(40, y + yy), (1650, y + yy)], fill=0, width=3)
    if noisy:
        import random
        im = im.resize((w // 2, h // 2)).filter(ImageFilter.GaussianBlur(0.8)).resize((w, h))
        rng, px = random.Random(1), im.load()
        for _ in range(25000):
            px[rng.randrange(w), rng.randrange(h)] = rng.choice((0, 255))
    b = io.BytesIO()
    im.convert("RGB").save(b, "PNG")
    return b.getvalue()


def _rows_letters(truth, x_result=700):
    out = [(60, 0, "Antibiotic Sensitivity:", True)]
    for i, (k, v) in enumerate(truth.items()):
        out += [(60, 60 + i * 50, SHOWN.get(k, k), False), (x_result, 60 + i * 50, v, False)]
    return out


def _columns_marks():
    out = [(60, 0, "Antibiotic", True), (620, 0, "Sensitive", True),
           (900, 0, "Intermediate", True), (1250, 0, "Resistant", True)]
    col = {"S": 680, "I": 990, "R": 1310}
    for i, (k, v) in enumerate(TRUTH.items()):
        out += [(60, 60 + i * 50, SHOWN[k], False), (col[v], 60 + i * 50, "X", False)]
    return out


def _side_by_side():
    out = [(60, 0, "Sensitive to:", True), (620, 0, "Intermediate:", True),
           (1150, 0, "Resistant to:", True)]
    for x, cat in ((60, "S"), (620, "I"), (1150, "R")):
        for i, k in enumerate([k for k, v in TRUTH.items() if v == cat]):
            out.append((x, 60 + i * 50, SHOWN[k], False))
    return out


def _two_per_row():
    items, out = list(TRUTH.items()), [(60, 0, "Antibiotic Sensitivity:", True)]
    for i in range(0, len(items), 2):
        r = i // 2
        out += [(60, 60 + r * 50, SHOWN[items[i][0]], False), (520, 60 + r * 50, items[i][1], False)]
        if i + 1 < len(items):
            out += [(900, 60 + r * 50, SHOWN[items[i + 1][0]], False),
                    (1400, 60 + r * 50, items[i + 1][1], False)]
    return out


MIC = {"Amikacin": "<=2", "Ciprofloxacin": ">=4", "Cefepime": "<=1", "Ceftriaxone": ">=64",
       "Nitrofurantoin": "<=16", "Imipenem/Cilastatin": "<=0.25", "Gentamicin": "8"}


def _mic_and_interpretation():
    out = [(60, 0, "Antibiotic", True), (700, 0, "MIC", True), (1100, 0, "Interpretation", True)]
    for i, (k, v) in enumerate(TRUTH.items()):
        out += [(60, 60 + i * 50, SHOWN[k], False), (700, 60 + i * 50, MIC[k], False),
                (1150, 60 + i * 50, v, False)]
    return out


GRID_ROWS = [45 + i * 50 for i in range(8)]
LAYOUTS = {
    # name: (image, truth the read must not contradict, minimum results read)
    "one result per line": (lambda: _render(_rows_letters(TRUTH)), TRUTH, 6),
    "tick-mark columns": (lambda: _render(_columns_marks()), TRUTH, 6),
    "tick-mark columns, ruled": (lambda: _render(_columns_marks(),
                                                 grid=([40, 600, 880, 1230, 1650], GRID_ROWS)),
                                 TRUTH, 6),
    "side-by-side lists": (lambda: _render(_side_by_side()), TRUTH, 6),
    "two pairs per row": (lambda: _render(_two_per_row()), TRUTH, 6),
    "MIC + interpretation, ruled": (lambda: _render(_mic_and_interpretation(),
                                                    grid=([40, 640, 1060, 1650], GRID_ROWS)),
                                    TRUTH, 5),
    "results as words": (lambda: _render(_rows_letters(
        {k: {"S": "Sensitive", "I": "Intermediate", "R": "Resistant"}[v] for k, v in TRUTH.items()})),
        TRUTH, 6),
}


def _read(img):
    from cdss.ocr.extract import extract_all_data_cached
    return extract_all_data_cached(img)


@needs_ocr
@pytest.mark.parametrize("name", list(LAYOUTS))
def test_each_layout_is_read_without_a_wrong_result(name):
    make, truth, minimum = LAYOUTS[name]
    d = _read(make())
    sir = d["sir_map"]
    wrong = {k: (v, truth.get(k)) for k, v in sir.items() if k in truth and v != truth[k]}
    assert not wrong, wrong
    assert not [k for k, v in sir.items() if v == "S" and truth.get(k, "S") != "S"], "a false S"
    assert len([k for k in sir if k in truth]) >= minimum, (len(sir), d["ocr_review"])
    # nothing dropped silently: every drug is read, in conflict, or listed as unclear
    rev = d["ocr_review"]
    for k in truth:
        if k in d["drugs"]:
            assert k in sir or k in rev["conflicts"] or k in rev["unresolved"], k


@needs_ocr
@pytest.mark.parametrize("values", [
    {"Amikacin": "18", "Ciprofloxacin": "21", "Cefepime": "25"},          # zones only
    {"Amikacin": "<=1", "Ciprofloxacin": "1", "Cefepime": "5"},           # MICs only, "1" and "5"
])
def test_numbers_without_an_interpretation_are_never_read_as_results(values):
    items = [(60, 0, "Antibiotic", True), (700, 0, "Result", True)]
    for i, (k, v) in enumerate(values.items()):
        items += [(60, 60 + i * 50, k, False), (720, 60 + i * 50, v, False)]
    assert _read(_render(items))["sir_map"] == {}


@needs_ocr
def test_a_drug_printed_twice_with_two_results_is_a_conflict_not_a_choice():
    rows = _rows_letters(TRUTH) + [(60, 60 + 7 * 50, "Ciprofloxacin", False),
                                   (700, 60 + 7 * 50, "S", False)]
    d = _read(_render(rows))
    assert "Ciprofloxacin" not in d["sir_map"]
    assert "Ciprofloxacin" in d["ocr_review"]["conflicts"]


@needs_ocr
def test_a_poor_scan_reads_nothing_wrong_and_shows_what_it_found():
    d = _read(_render(_rows_letters(TRUTH), noisy=True))
    assert not {k: v for k, v in d["sir_map"].items() if TRUTH.get(k) not in (None, v)}
    found = set(d["drugs"])
    assert found, "the drugs it could find are listed for the operator"
    rev = d["ocr_review"]
    assert all(k in d["sir_map"] or k in rev["unresolved"] or k in rev["conflicts"] for k in found)


# ── pure logic, no OCR needed ─────────────────────────────────────────────
def test_the_two_readers_merge_only_when_they_agree():
    m = merge_readings({"Amikacin": "S", "Ciprofloxacin": "R"},
                       {"sir": {"Amikacin": "S", "Ciprofloxacin": "S", "Cefepime": "S"},
                        "unresolved": {"Gentamicin": "result cell not readable"},
                        "conflicts": {"Ceftriaxone": "the table shows it twice: S and R"}}, {})
    assert m["sir"] == {"Amikacin": "S", "Cefepime": "S"}
    assert set(m["conflicts"]) == {"Ciprofloxacin", "Ceftriaxone"}
    assert m["unresolved"] == {"Gentamicin": "result cell not readable"}
    assert m["sources"] == {"Amikacin": "both", "Cefepime": "table layout"}


def test_a_line_reader_conflict_is_never_overwritten_by_the_table():
    m = merge_readings({}, {"sir": {"Amikacin": "S"}, "unresolved": {}, "conflicts": {}},
                       {"Amikacin": "the report prints it twice: S and R"})
    assert "Amikacin" not in m["sir"] and "Amikacin" in m["conflicts"]


@pytest.mark.parametrize("text,expected", [
    ("Culture: No growth after 48 hours", True), ("No bacterial growth", True),
    ("Culture result: negative", True), ("no organisms isolated", True),
    ("لا يوجد نمو بكتيري", True), ("No significant growth", True),
    ("No growth of anaerobes. E. coli isolated", False),
    ("Moderate growth of Klebsiella; no growth of fungi", False),
    ("Growth of E. coli >100,000 CFU/ml", False)])
def test_no_growth_is_recognised_and_not_confused_with_a_positive_report(text, expected):
    assert detect_no_growth(text) is expected
