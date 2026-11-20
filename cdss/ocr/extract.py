# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""OCR image -> structured culture report."""
import re
from typing import Any
from typing import Dict

from cdss.ocr.ocr_parsing import age_reading_is_ambiguous
from cdss.ocr.ocr_parsing import detect_age_months
from cdss.ocr.ocr_parsing import extract_detected_drugs, ocr_name_warnings
from cdss.ocr.ocr_parsing import parse_result_line
from cdss.ocr.detect import (
    classify_sir_from_line,
    detect_age,
    detect_culture_condition,
    detect_no_growth,
    detect_organism,
    detect_pus_cells,
    detect_rbcs,
    detect_sex,
    detect_specimen,
)
from cdss.common.data_consistency import detect_collection_method
from cdss.ocr.image import (
    preprocess_image,
    run_ocr,
)




def extract_all_data_cached(file_bytes: bytes) -> Dict[str, Any]:
    _, thresh  = preprocess_image(file_bytes)
    full_text  = run_ocr(thresh)
    text_lower = full_text.lower()
    line_sir: Dict[str, str] = {}
    line_conflicts: Dict[str, str] = {}
    for line in full_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Round 5 (2026-11-12): a line may carry more than one result (two
        # columns, "Sensitive to: a, b"). One verdict + the longest drug name
        # per line read "Amikacin Sensitive  Ciprofloxacin Resistant" as
        # Ciprofloxacin = S. See ocr_parsing.parse_result_line.
        for matched_abx, result in parse_result_line(line, classify_sir_from_line):
            # The same drug printed twice with different results is not
            # readable. v7.8: it is a CONFLICT shown to the operator (it used
            # to keep the more resistant reading without saying so).
            _old = line_sir.get(matched_abx)
            if _old and _old != result:
                line_conflicts[matched_abx] = f"the report prints it twice: {_old} and {result}"
            line_sir[matched_abx] = result
    for d in line_conflicts:
        line_sir.pop(d, None)
    # v7.8: the AST table read by position, merged with the line reading
    try:
        layout = read_ast_layout(thresh)
    except Exception as exc:                       # the line reading still stands
        layout = {"sir": {}, "unresolved": {}, "layout": f"not read ({type(exc).__name__})"}
    merged = merge_readings(line_sir, layout, line_conflicts)
    sir_map = merged["sir"]
    return {
        "patient": {
            "Name":     None,  # الاسم يُدخل يدوياً فقط
            "Age":      detect_age(full_text),
            # Months are extracted alongside years so an infant report can
            # pre-tick the under-one box instead of relying on the operator to
            # notice. Without it the OCR could read "Age: 6/12" correctly as
            # under one year and the form would still open on the adult branch.
            "AgeMonths": detect_age_months(full_text),
            "AgeAmbiguous": age_reading_is_ambiguous(full_text),
            "Sex":      detect_sex(text_lower),
            "Specimen": detect_specimen(text_lower),
            # v7.4 (external case review): the report's collection method
            # ("Sample: Mid stream urine") -- compared with the method entered in
            # the app (cdss.common.data_consistency). It used to be discarded.
            "CollectionMethod": detect_collection_method(full_text),
            "Organism": detect_organism(text_lower),
            # v7.8: "No growth" against an entered organism + AST is a conflict
            "NoGrowth": detect_no_growth(full_text),
        },
        # v7.8: every drug either reader found -- a drug only the table
        # reader saw (no result read) must still reach the operator's list
        "drugs":     sorted(set(extract_detected_drugs(full_text)) | set(sir_map)
                            | set(merged["conflicts"]) | set(merged["unresolved"])),
        "sir_map":   sir_map,
        # v7.8: what the operator must review before any report
        "ocr_review": {"layout": layout.get("layout"), "sources": merged["sources"],
                       "conflicts": merged["conflicts"], "unresolved": merged["unresolved"]},
        "raw_text":  full_text,
        "name_warnings": ocr_name_warnings(full_text),
        # ── New: Microscopy + Condition ──────────────────────────────────
        "pus_cells": detect_pus_cells(full_text),
        "rbcs":      detect_rbcs(full_text),
        "condition": detect_culture_condition(full_text),
    }


# ═════════════════════════════════════════════════════════════════════════
# v7.8 -- reading the AST table by POSITION (external review of v7.7)
# ═════════════════════════════════════════════════════════════════════════
# Three layouts are read from word positions:
#   * COLUMN MARKS  -- "Antibiotic | Sensitive | Intermediate | Resistant" with an
#     X / tick under one column: the column holding the ink is the result;
#   * COLUMN LISTS  -- "Sensitive to:  Intermediate:  Resistant to:" with the
#     drugs listed under each heading: the heading above the drug is the result;
#   * RESULT CELLS  -- "Amikacin   S" (one or two pairs a row, names or disk
#     codes): the cell right of the drug is re-read alone (S / I / R alphabet
#     when it holds one glyph).
# Anything not clear -- no mark, two marks, an unreadable cell -- is left OUT
# (the drug shows as "detected, no result" for the operator). Nothing becomes S
# by default, and a reading that disagrees with the line reader is a CONFLICT.
_HEAD = (("S", ("sensitive", "susceptible", "sensitive to")),
         ("I", ("intermediate",)),
         ("R", ("resistant", "resistant to")))
_CONNECTORS = {"+", "/", "-", "&", "and", "with"}


def _head_category(word: str) -> Any:
    w = word.lower().strip(":;.,")
    for cat, keys in _HEAD:
        if any(w == k or (k.endswith("e") and w == k[:-1] + "e") for k in keys):
            return cat
    return None


def _rows(words: list) -> list:
    """Words grouped into printed rows (by vertical centre), left to right."""
    rows: list = []
    for w in sorted(words, key=lambda w: w["y"] + w["h"] / 2):
        cy = w["y"] + w["h"] / 2
        for r in rows:
            if abs(r["cy"] - cy) <= 0.55 * max(r["h"], w["h"]):
                r["words"].append(w)
                r["cy"] = (r["cy"] * (len(r["words"]) - 1) + cy) / len(r["words"])
                r["h"] = max(r["h"], w["h"])
                break
        else:
            rows.append({"cy": cy, "h": w["h"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: w["x"])
        # the row's text height: its real words, not the tallest box (a rule
        # fragment or a merged box can be three times the text)
        real = sorted(w["h"] for w in r["words"] if re.search(r"[A-Za-z]{2,}", w["text"]))
        if real:
            r["h"] = real[len(real) // 2]
    return sorted(rows, key=lambda r: r["cy"])


def _drugs_in_row(row: dict) -> list:
    """[(drug, x_left, x_right)] for one printed row, longest name first."""
    from cdss.ocr.ocr_parsing import _scan_line_for_drugs, _scan_line_for_disk_codes
    from cdss.ocr.ocr_parsing import normalize_sir_value
    ws = row["words"]
    out, i = [], 0
    while i < len(ws):
        best = None
        for n in range(min(5, len(ws) - i), 0, -1):
            span = ws[i:i + n]
            if any(normalize_sir_value(w["text"]) is not None or _head_category(w["text"])
                   or not re.search(r"[A-Za-z]", w["text"]) and w["text"] not in _CONNECTORS
                   for w in span):
                continue
            gaps = [b["x"] - (a["x"] + a["w"]) for a, b in zip(span, span[1:])]
            if any(g > 1.6 * row["h"] for g in gaps):
                continue
            hits = _scan_line_for_drugs(" ".join(w["text"] for w in span))
            if len(hits) == 1:
                best = (hits[0], span)
                break
        if best:
            d, span = best
            if out and out[-1][0] == d and span[0]["x"] - out[-1][2] < 2.5 * row["h"]:
                out[-1] = (d, out[-1][1], span[-1]["x"] + span[-1]["w"])   # "Piperacillin + Tazobactam"
            else:
                out.append((d, span[0]["x"], span[-1]["x"] + span[-1]["w"]))
            i += len(span)
        else:
            i += 1
    if not out:                                 # a disk-code row ("AK  S", "CIP R")
        for w in ws:
            codes = _scan_line_for_disk_codes(w["text"], require_verdict=False, check_row=False)
            if len(codes) == 1 and w["text"].isupper() and len(w["text"]) >= 2:
                out.append((codes[0], w["x"], w["x"] + w["w"]))
    return out


def _header(rows: list) -> Any:
    """The row naming >= 2 of Sensitive / Intermediate / Resistant: {cat: x-centre}."""
    for idx, r in enumerate(rows):
        cols = {}
        for w in r["words"]:
            c = _head_category(w["text"])
            if c and c not in cols:
                cols[c] = (w["x"], w["x"] + w["w"])
        if len(cols) >= 2 and "S" in cols and "R" in cols:
            return idx, cols
    return None, None


def _ink(img: Any, x0: float, x1: float, y0: float, y1: float) -> int:
    h, w = img.shape[:2]
    x0, x1 = max(0, int(x0)), min(w, int(x1))
    y0, y1 = max(0, int(y0)), min(h, int(y1))
    if x1 <= x0 or y1 <= y0:
        return 0
    return int((img[y0:y1, x0:x1] < 128).sum())


def read_ast_layout(thresh: Any, words: list = None) -> Dict[str, Any]:
    """{"sir": {drug: S/I/R}, "unresolved": {drug: reason}, "layout": str}."""
    from cdss.ocr.image import read_result_cell, remove_table_lines, run_ocr_words
    from cdss.ocr.ocr_parsing import normalize_sir_value
    # Table rules removed FIRST: with them in, Tesseract read "pAmikacin," at
    # three times the text height plus junk words made of rule fragments, and
    # every cell held rule ink (a ruled table read 0 of 7).
    clean = remove_table_lines(thresh)
    words = words if words is not None else run_ocr_words(clean)
    rows = _rows(words)
    sir: Dict[str, str] = {}
    unresolved: Dict[str, str] = {}
    hidx, cols = _header(rows)
    thresh = clean
    W = thresh.shape[1]

    conflicts: Dict[str, str] = {}

    def _put(d, v, why):
        if d in conflicts:
            return
        if d in sir and sir[d] != v:
            conflicts[d] = f"the table shows it twice: {sir.pop(d)} and {v}"
            return
        sir[d] = v
        del why

    layout = "cells"
    if cols:
        centres = {c: (a + b) / 2 for c, (a, b) in cols.items()}
        order = sorted(centres, key=centres.get)
        gap = min((centres[b] - centres[a] for a, b in zip(order, order[1:])), default=W)
        first_col_left = min(a for a, _b in cols.values())
        for r in rows[hidx + 1:]:
            for d, x0, x1 in _drugs_in_row(r):
                cx = (x0 + x1) / 2
                if x1 > first_col_left - 0.25 * gap:
                    # COLUMN LISTS: the drug itself stands under a heading
                    layout = "column lists"
                    near = min(order, key=lambda c: abs(centres[c] - cx))
                    if abs(centres[near] - cx) <= 0.75 * gap or x0 >= cols[near][0] - 0.25 * gap:
                        _put(d, near, "listed under heading")
                    else:
                        unresolved.setdefault(d, "not under a heading")
                    continue
                # COLUMN MARKS: ink in the drug's row under each heading
                layout = "column marks"
                h = r["h"]
                y0, y1 = r["cy"] - 0.75 * h, r["cy"] + 0.75 * h
                ink = {c: _ink(clean, centres[c] - 0.45 * gap, centres[c] + 0.45 * gap, y0, y1)
                       for c in order}
                thr = 0.12 * h * h
                marked = [c for c in order if ink[c] >= thr]
                weak = [c for c in order if 0 < ink[c] < thr and ink[c] >= thr / 3]
                if len(marked) == 1 and not weak:
                    _put(d, marked[0], "mark under heading")
                else:
                    unresolved.setdefault(d, "no clear mark" if not marked else "marks in two columns")
        return {"sir": sir, "unresolved": unresolved, "conflicts": conflicts, "layout": layout}
    # RESULT CELLS
    for r in rows:
        found = _drugs_in_row(r)
        h = r["h"]
        for k, (d, x0, x1) in enumerate(found):
            # to the next drug on the row, else to the page edge (a fixed width
            # cut a far result column in half: "S" read as a quote mark)
            nxt = found[k + 1][1] if k + 1 < len(found) else W
            # the words between this drug and the next: read them first
            between = [w for w in r["words"] if w["x"] >= x1 - 2 and w["x"] + w["w"] <= nxt + 2]
            verdicts = [normalize_sir_value(w["text"]) for w in between]
            verdicts = [v for v in verdicts if v]
            if len(set(verdicts)) == 1:
                _put(d, verdicts[0], "word next to the drug")
                continue
            if len(set(verdicts)) > 1:
                unresolved.setdefault(d, "two verdicts beside it")
                continue
            # the cell itself: the gap holds no word Tesseract could read
            y0, y1 = int(r["cy"] - 0.9 * h), int(r["cy"] + 0.9 * h)
            cell = thresh[max(0, y0):y1, int(x1 + 0.3 * h):int(nxt - 0.2 * h)]
            if not cell.size or not (cell < 128).any():
                continue                                  # empty: no result printed
            v, how = read_result_cell(cell, h)
            if v:
                _put(d, v, how)
            else:
                unresolved.setdefault(d, f"result cell not readable: {how}")
    return {"sir": sir, "unresolved": unresolved, "conflicts": conflicts, "layout": layout}


def merge_readings(line_sir: Dict[str, str], layout: Dict[str, Any],
                   line_conflicts: Dict[str, str]) -> Dict[str, Any]:
    """One panel from the two readers. Agreement or a single reading is kept;
    a disagreement is a CONFLICT -- left out and shown, never resolved by
    picking one (v7.8)."""
    sir, conflicts = {}, dict(line_conflicts)
    conflicts.update(layout.get("conflicts") or {})
    sources: Dict[str, str] = {}
    lay = layout.get("sir") or {}
    for d in sorted(set(line_sir) | set(lay)):
        a, b = line_sir.get(d), lay.get(d)
        if d in conflicts:
            continue
        if a and b and a != b:
            conflicts[d] = f"text line read {a}, the table layout read {b}"
        elif a or b:
            sir[d] = a or b
            sources[d] = "both" if (a and b) else ("text line" if a else "table layout")
    unresolved = {d: why for d, why in (layout.get("unresolved") or {}).items()
                  if d not in sir and d not in conflicts}
    return {"sir": sir, "conflicts": conflicts, "unresolved": unresolved, "sources": sources}
