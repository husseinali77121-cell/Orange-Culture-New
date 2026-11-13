# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Hepatic dosing annotations for the allowed list."""
from typing import Dict
from typing import List

from cdss.therapy.tables import (
    HEPATIC_DOSING,
)


def get_hepatic_recommendations(allowed_drugs: List[Dict], child_pugh: str) -> List[Dict[str, str]]:
    """Hepatic dosing recommendations -- BNF 2025 | Lexicomp 2025"""
    results = []
    for drug in allowed_drugs:
        name = drug.get("name", "")
        if name in HEPATIC_DOSING:
            level, rec = HEPATIC_DOSING[name].get(child_pugh, ("Normal", "No adjustment"))
            note = HEPATIC_DOSING[name].get("note", "")
            results.append({
                "name": name, "level": level,
                "recommendation": rec, "note": note,
                "requires_action": level not in ("Normal", "Renal-based", "AUC/MIC monitoring"),
            })
    results.sort(key=lambda x: (0 if x["requires_action"] else 1, x["name"]))
    return results
