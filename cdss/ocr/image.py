# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Image pre-processing and Tesseract OCR."""
from typing import Any
from typing import Tuple
import re

from cdss.ocr.ocr_parsing import normalize_ocr_text
from cdss.common.optional_deps import (
    OCR_AVAILABLE,
    OCR_IMPORT_ERROR,
    cv2,
    np,
    pytesseract,
)


class OCRUnavailableError(RuntimeError):
    """The OCR libraries (opencv / numpy / pytesseract) could not be imported."""


def ensure_ocr_dependencies() -> None:
    if OCR_AVAILABLE:
        return
    raise OCRUnavailableError(
        "تعذر تحميل مكتبات OCR المطلوبة لتشغيل قراءة الصور.\n\n"
        f"Runtime import error: {OCR_IMPORT_ERROR}"
    )


# =========================================================
# OCR
# =========================================================
def preprocess_image(file_bytes: bytes) -> Tuple[Any, Any]:
    ensure_ocr_dependencies()
    arr  = np.frombuffer(file_bytes, np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("تعذر قراءة الصورة. تأكد أن الملف صورة سليمة.")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.7, fy=1.7, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11,
    )
    kernel = np.ones((1, 1), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    return img, thresh

def run_ocr(thresh: Any) -> str:
    ensure_ocr_dependencies()
    configs = ["--psm 6", "--psm 11", "--psm 4"]
    outputs = []
    for cfg in configs:
        for lang in ["ara+eng", "eng"]:
            try:
                txt = pytesseract.image_to_string(thresh, lang=lang, config=cfg)
                txt = normalize_ocr_text(txt)
                if txt:
                    outputs.append(txt)
            except Exception:
                continue
    if not outputs:
        raise RuntimeError("OCR failed: no text extracted")
    return max(outputs, key=lambda x: len(re.sub(r"\s+", "", x)))


# =========================================================
# Word positions (v7.8, external review of v7.7)
# =========================================================
# `image_to_string` throws the layout away: a report printing results in
# Sensitive / Intermediate / Resistant COLUMNS, or "Sensitive to: / Resistant
# to:" lists side by side, came out with an empty panel (measured on rendered
# reports: 0 of 7 results), and a lone "S" was read as the digit "5" -- the
# parser rightly refuses "5", so even a one-result-per-line report gave 2 of 7.
# These two functions give the layout reader in cdss.ocr.extract what it needs:
# every word with its box and confidence, and a re-read of ONE result cell with
# the alphabet limited to S / I / R.
def run_ocr_words(thresh: Any, psm: str = "11") -> list:
    """Every word Tesseract finds, with its box and confidence (English)."""
    ensure_ocr_dependencies()
    try:
        d = pytesseract.image_to_data(thresh, lang="eng", config=f"--psm {psm}",
                                      output_type=pytesseract.Output.DICT)
    except Exception:
        return []
    out = []
    for i, text in enumerate(d.get("text") or []):
        t = str(text or "").strip()
        if not t:
            continue
        try:
            conf = float(d["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        out.append({"text": t, "conf": conf, "x": int(d["left"][i]), "y": int(d["top"][i]),
                    "w": int(d["width"][i]), "h": int(d["height"][i])})
    return out


def read_result_cell(cell: Any, row_h: float) -> Tuple[Any, str]:
    """(verdict or None, how it was read) for the ink right of one drug.

    `cell` is the row band (the drug's text height plus a margin), cut from the
    drug's right edge. Words ("Sensitive", "R (>=16)") are read as written; a
    cell holding ONE glyph is enlarged and read as a single character, because
    Tesseract reads a lone small "S" as the digit 5 (which the parser rightly
    refuses). The glyph must look like a capital letter -- one blob, letter
    height, inside the band -- and a lone vertical stroke is an I only if it
    does not run the band's full height (a table rule does). "5" is never S.
    """
    from cdss.ocr.ocr_parsing import normalize_sir_value
    ensure_ocr_dependencies()
    if cell is None or getattr(cell, "size", 0) == 0:
        return None, "empty"
    cell = _drop_rules(_drop_specks(cell, row_h))
    ys, xs = (cell < 128).nonzero()
    if len(xs) == 0:
        return None, "empty"
    band_h = cell.shape[0]
    tight = cell[max(0, ys.min() - 3):ys.max() + 4, max(0, xs.min() - 3):xs.max() + 4]
    padded = cv2.copyMakeBorder(tight, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
    try:
        plain = normalize_ocr_text(pytesseract.image_to_string(padded, lang="eng",
                                                               config="--psm 7")).strip()
    except Exception:
        plain = ""
    words = [normalize_sir_value(t) for t in re.split(r"[\s()\[\]]+", plain) if t]
    words = [v for v in words if v]
    if len(set(words)) == 1 and re.search(r"[A-Za-z]{2,}|\b[SIR]\b", plain):
        return words[0], f"read '{plain}'"
    if len(set(words)) > 1:
        return None, f"two verdicts ('{plain}')"
    # The interpretation is the RIGHTMOST item of a cell ("<=2  S", "8  I"):
    # glyphs are grouped into words by the gaps between them and the last word
    # is re-read alone -- only when it is one letter-sized glyph inside the band.
    blobs = sorted(_glyph_boxes(cell), key=lambda b: b[0])
    if not blobs:
        return None, f"no character found ('{plain or 'blank'}')"
    groups = [[blobs[0]]]
    for b in blobs[1:]:
        px, _py, pw, _ph = groups[-1][-1]
        if b[0] - (px + pw) > 0.35 * row_h:
            groups.append([b])
        else:
            groups[-1].append(b)
    last = groups[-1]
    if len(last) != 1:
        return None, f"no single result character ('{plain or 'blank'}')"
    bx, by, bw, bh = last[0]
    if by <= 0 or by + bh >= band_h - 1:
        return None, "the result character touches the row edge"
    if not (0.45 * row_h <= bh <= 1.25 * row_h):
        return None, "glyph is not letter-sized"
    tight = cell[max(0, by - 3):by + bh + 4, max(0, bx - 3):bx + bw + 4]
    # A plain I is a solid vertical bar; a 1 has a flag (and often a base), so
    # it is wider and far less filled. Shape decides here, not Tesseract,
    # which reads the same bar as I, | or 1 depending on the size.
    glyph = cell[by:by + bh, bx:bx + bw]
    fill = float((glyph < 128).sum()) / max(1, bw * bh)
    if bw <= 0.22 * bh and fill >= 0.7:
        return "I", "a single vertical bar (I)"
    # Read at three sizes: one small glyph is unstable in Tesseract, so the
    # reading counts only when every size that reads a letter agrees.
    reads = [_read_one_glyph(tight, height) for height in (56, 72, 96)]
    letters = []
    for ch, conf in reads:
        if ch.upper() in ("S", "R") and len(ch) == 1 and conf >= 40 and 0.3 * bh <= bw <= 1.1 * bh:
            letters.append((ch.upper(), conf))
        elif ch in ("I", "|", "l") and bw <= 0.35 * bh:      # never "1": an MIC
            letters.append(("I", conf))
        elif ch:
            letters.append(("?" + ch, conf))
    kinds = {k for k, _c in letters}
    if len(kinds) == 1 and not next(iter(kinds)).startswith("?"):
        k = next(iter(kinds))
        return k, f"single character read {k} at {len(letters)} sizes"
    if not letters:
        return None, "single character not read"
    return None, "single character unclear (" + ", ".join(sorted(k.lstrip("?") for k in kinds)) + ")"


def _read_one_glyph(tight: Any, height: int) -> Tuple[str, float]:
    f = float(height) / max(1, tight.shape[0])
    big = cv2.resize(tight, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    big = cv2.threshold(big, 128, 255, cv2.THRESH_BINARY)[1]
    big = cv2.copyMakeBorder(big, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    try:
        d = pytesseract.image_to_data(big, lang="eng", config="--psm 10",
                                      output_type=pytesseract.Output.DICT)
    except Exception:
        return "", -1.0
    best = ("", -1.0)
    for i, t in enumerate(d.get("text") or []):
        t = str(t or "").strip()
        try:
            c = float(d["conf"][i])
        except (TypeError, ValueError):
            c = -1.0
        if t and c > best[1]:
            best = (t, c)
    return best


def _drop_rules(cell: Any) -> Any:
    """The cell without rule remnants: a stroke spanning the band's height, or
    a long thin horizontal fragment at its top or bottom edge."""
    inv = (cell < 128).astype("uint8")
    n, lab, stats, _c = cv2.connectedComponentsWithStats(inv, connectivity=8)
    bh = cell.shape[0]
    keep = np.ones(n, dtype=bool)
    keep[0] = False
    for i in range(1, n):
        x, y, w, h = (int(v) for v in stats[i, :4])
        vertical_rule = h >= 0.85 * bh and w <= 0.15 * bh
        edge_fragment = (y <= 1 or y + h >= bh - 1) and h <= 0.2 * bh and w >= 0.6 * bh
        if vertical_rule or edge_fragment:
            keep[i] = False
    out = np.full_like(cell, 255)
    out[keep[lab]] = 0
    return out


def _drop_specks(cell: Any, row_h: float) -> Any:
    """The cell without ink blobs too small to be part of a character (scan noise)."""
    inv = (cell < 128).astype("uint8")
    n, lab, stats, _c = cv2.connectedComponentsWithStats(inv, connectivity=8)
    keep = np.zeros(n, dtype=bool)
    for i in range(1, n):
        # a letter broken by binarisation leaves fragments of a few % of h^2;
        # scan specks are a handful of pixels
        keep[i] = (stats[i, cv2.CC_STAT_AREA] >= max(12, 0.006 * row_h * row_h)
                   or stats[i, cv2.CC_STAT_HEIGHT] >= 0.2 * row_h)
    out = np.full_like(cell, 255)
    out[keep[lab]] = 0
    return out


def _glyph_boxes(cell: Any) -> list:
    """(x, y, w, h) of every ink blob big enough to be a character."""
    inv = (cell < 128).astype("uint8")
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(inv, connectivity=8)
    h = cell.shape[0]
    return [tuple(int(v) for v in stats[i, :4]) for i in range(1, n)
            if stats[i, cv2.CC_STAT_HEIGHT] >= 0.25 * h and stats[i, cv2.CC_STAT_AREA] >= 0.01 * h * h]


def remove_table_lines(thresh: Any) -> Any:
    """The binarised page without long horizontal / vertical rules (grid lines
    would otherwise count as a mark in every column)."""
    ensure_ocr_dependencies()
    inv = 255 - thresh
    h, w = thresh.shape[:2]
    lines = 0 * inv
    for k in ((max(40, w // 30), 1), (1, max(40, h // 30))):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, k)
        lines = cv2.bitwise_or(lines, cv2.morphologyEx(inv, cv2.MORPH_OPEN, kernel))
    return 255 - cv2.subtract(inv, lines)
