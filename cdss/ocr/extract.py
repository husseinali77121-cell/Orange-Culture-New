# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""OCR image -> structured culture report."""
from typing import Any
from typing import Dict

from cdss.ocr.ocr_parsing import age_reading_is_ambiguous
from cdss.ocr.ocr_parsing import detect_age_months
from cdss.ocr.ocr_parsing import extract_detected_drugs
from cdss.ocr.ocr_parsing import parse_result_line
from cdss.ocr.detect import (
    classify_sir_from_line,
    detect_age,
    detect_culture_condition,
    detect_organism,
    detect_pus_cells,
    detect_rbcs,
    detect_sex,
    detect_specimen,
)
from cdss.ocr.image import (
    preprocess_image,
    run_ocr,
)


def extract_all_data_cached(file_bytes: bytes) -> Dict[str, Any]:
    _, thresh  = preprocess_image(file_bytes)
    full_text  = run_ocr(thresh)
    text_lower = full_text.lower()
    sir_map: Dict[str, str] = {}
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
            # readable: keep the more resistant reading, never the S.
            _old = sir_map.get(matched_abx)
            if _old and _old != result:
                result = max(_old, result, key="SIR".index)
            sir_map[matched_abx] = result
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
            "Organism": detect_organism(text_lower),
        },
        "drugs":     extract_detected_drugs(full_text),
        "sir_map":   sir_map,
        "raw_text":  full_text,
        # ── New: Microscopy + Condition ──────────────────────────────────
        "pus_cells": detect_pus_cells(full_text),
        "rbcs":      detect_rbcs(full_text),
        "condition": detect_culture_condition(full_text),
    }
