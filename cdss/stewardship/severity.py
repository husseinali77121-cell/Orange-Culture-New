# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Severity suggestion from specimen and host factors."""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from cdss.common.specimen import (
    classify_specimen,
)


def suggest_severity(
    specimen: str, age: int, sex: str,
    is_preg: bool, is_renal: bool, cl_cr: float,
    host_factors: Optional[List] = None,
    symptoms: Optional[List] = None,
) -> Dict[str, Any]:
    """
    Auto-suggest infection severity based on patient risk factors.
    Clinical basis: IDSA cUTI 2025 | IDSA CAP 2019 | Sanford 2025 |
                    AHA Infective Endocarditis 2015 | SCCM Sepsis-3 2016.

    Returns:
        suggested: "mild" | "moderate" | "severe"
        reasons:   list of clinical reasons
        override:  True (user can still change it)
    """
    _cat   = classify_specimen(specimen)
    hf     = [h.lower() for h in (host_factors or [])]
    syms   = [s.lower() for s in (symptoms or [])]
    # FIX v6.7: the host factors come from the pathogenicity panel's lists
    # ("Immunosuppressants / Steroids", "Neutropenia", "Renal transplant"), and
    # none of them contains the word "immunocompromised" this function looked
    # for -- an immunosuppressed host never raised the suggested severity.
    _immuno = any(k in " ".join(hf) for k in ("immunocomp", "immunosupp", "steroid",
                                              "neutropen", "transplant"))
    # Neutropenia is the emergency (febrile neutropenia); other immunosuppression
    # makes the infection complicated, not automatically severe.
    _neutropenic = "neutropen" in " ".join(hf)

    reasons_severe   = []
    reasons_moderate = []
    reasons_mild     = []

    # ── Universal red flags -> SEVERE ─────────────────────────────────────
    if any(k in " ".join(syms) for k in
           ["septic shock", "hypotension", "icu", "bacteremia",
            "altered consciousness", "confusion", "rigors"]):
        reasons_severe.append("Systemic sepsis signs / shock")

    if "central line" in " ".join(hf) or _neutropenic:
        reasons_severe.append("Immunocompromised / central line")
    elif _immuno:
        reasons_moderate.append("Immunosuppressed host (steroids / transplant) -> complicated")

    # ── Specimen-specific logic ────────────────────────────────────────────
    if _cat == "urine":
        # v7.1 (review 2026-11-19): IDSA cUTI 2025 defines a complicated UTI by
        # infection beyond the bladder (fever, systemic signs, bacteraemia, flank
        # pain) or a urinary catheter, intermittent catheterisation, stent or
        # nephrostomy -- and says diabetes, immunocompromise, male sex and
        # urologic abnormalities "no longer automatically make a UTI
        # complicated". This block called male, age >= 65, renal impairment,
        # diabetes and reflux "complicated (IDSA cUTI 2025)". They still shape
        # the choice of agent (renal dosing, prostate penetration) and the
        # duration (men: 7 days) -- elsewhere, not as "complicated".
        if is_preg:
            reasons_moderate.append("Pregnancy -> managed as its own category (IDSA ASB 2019 / ACOG)")
        if any(k in " ".join(hf) for k in ["catheter", "stent", "stone", "nephrostomy",
                                           "conduit"]):
            reasons_moderate.append("Urinary catheter / stent / stone -> complicated UTI "
                                    "(IDSA cUTI 2025)")
        if any(k in " ".join(syms) for k in ["fever", "flank", "loin", "costovertebral"]):
            reasons_moderate.append("Upper UTI / systemic signs -> complicated UTI (IDSA cUTI 2025)")
        if not reasons_moderate and not reasons_severe:
            reasons_mild.append("No sign beyond the bladder and no catheter -> cystitis "
                                "(IDSA cUTI 2025: male sex, age, diabetes and renal impairment "
                                "do not by themselves make a UTI complicated)")

    elif _cat == "sputum":
        # CURB-65 proxy: Age ≥65, renal, altered mentation
        curb = 0
        if age >= 65:         curb += 1; reasons_moderate.append("Age ≥ 65 (CURB-65)")
        if is_renal:          curb += 1; reasons_moderate.append("Renal impairment (CURB-65)")
        if any(k in " ".join(syms) for k in ["confusion", "altered"]):
            curb += 1; reasons_severe.append("Altered mentation (CURB-65 ≥3)")
        if curb == 0:
            reasons_mild.append("No CURB-65 risk factors -> mild CAP")

    elif _cat == "blood":
        # Bacteremia is always at least moderate
        reasons_moderate.append("Bloodstream infection -> minimum moderate")
        if age >= 65 or is_renal:
            reasons_severe.append("Bacteremia + age ≥65 / renal impairment -> severe")

    elif _cat == "csf":
        # CNS = always severe
        reasons_severe.append("CNS infection -> always severe")

    elif _cat in ("wound", "pus"):
        if "diabetes" in " ".join(hf) or _immuno:
            reasons_moderate.append("Wound infection + DM/immunocompromised")
        elif not reasons_moderate and not reasons_severe:
            reasons_mild.append("Simple SSTI without systemic features")

    elif _cat in ("stool", "abdomen"):
        if age >= 65 or is_renal or is_preg:
            reasons_moderate.append("GI infection + high-risk host")
        if any(k in " ".join(syms) for k in ["bloody", "fever", "dehydration"]):
            reasons_moderate.append("Febrile / bloody diarrhea -> moderate+")
        else:
            reasons_mild.append("GI infection without systemic features -> supportive")

    # ── Final decision ────────────────────────────────────────────────────
    if reasons_severe:
        return {"suggested": "severe",   "reasons": reasons_severe,   "override": True}
    elif reasons_moderate:
        return {"suggested": "moderate", "reasons": reasons_moderate, "override": True}
    else:
        return {"suggested": "mild",     "reasons": reasons_mild or ["No risk factors identified"],
                "override": True}
