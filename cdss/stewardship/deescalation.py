# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""De-escalation evaluation."""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional




# ═══════════════════════════════════════════════════════════════════════
# ENGINE 5 -- De-escalation Advisor
# WHO AWaRe 2025 | IDSA Stewardship 2025
# ═══════════════════════════════════════════════════════════════════════
def evaluate_deescalation(
    allowed: List[Dict], phenotypes: List[Dict],
    hours_on_treatment: int, clinical_improving: bool,
    mdr_level: Optional[str] = None,
) -> Dict[str, Any]:
    """De-escalation advisor -- WHO AWaRe 2025 | IDSA Stewardship 2025

    FIX 2026-11-11 (round 4): "MDR" / "XDR" / "PDR" were looked for among the
    PHENOTYPE names, where no detector ever emits them (the level comes from
    classify_mdr), and DTR-P. aeruginosa was missing -- so an XDR or DTR
    isolate got "de-escalation recommended" with no ID caution. The MDR level
    is now passed in.
    """
    ph_names    = [p.get("phenotype", "") for p in phenotypes]
    is_reserve  = (any(p in ph_names for p in ["MDR", "XDR", "PDR", "CRE", "CRPA", "CRAB", "DTR_PA"])
                   or str(mdr_level or "").upper() in ("MDR", "XDR", "PDR"))
    access_drugs = [d for d in allowed if d.get("aware") == "Access"]
    watch_drugs  = [d for d in allowed if d.get("aware") == "Watch"]
    recs, can_de = [], False

    if hours_on_treatment < 48:
        recs.append(f"INFO: Still in early treatment phase ({hours_on_treatment}h). Complete 48-72h before reassessment.")
    elif not clinical_improving:
        recs.extend(["WARNING: No clinical improvement at 48-72h:",
                     "  - Repeat culture to confirm sensitivity",
                     "  - Assess source control (drainage, catheter removal)",
                     "  - Consider TDM (vancomycin AUC, aminoglycosides)",
                     "  - Consult Infectious Disease"])
    else:
        can_de = True
        recs.append("RECOMMENDED: Clinical improvement documented -- consider spectrum narrowing:")
        if access_drugs:
            names = [d["name"] for d in access_drugs[:4]]
            recs.append(f"  Access-group options: {' | '.join(names)}")
        elif watch_drugs:
            names = [d["name"] for d in watch_drugs[:3]]
            recs.append(f"  Watch-group options: {' | '.join(names)}")
        if is_reserve:
            recs.append("  CAUTION: MDR/XDR organism -- ID consult before de-escalating Reserve agents")
            can_de = False

    recs.append("PRINCIPLE: Narrowest effective spectrum + shortest safe duration (WHO AWaRe 2025)")
    return {
        "can_deescalate": can_de,
        "access_options": [d["name"] for d in access_drugs],
        "watch_options":  [d["name"] for d in watch_drugs],
        "recommendations": recs,
        "is_reserve_organism": is_reserve,
        "ref": "WHO AWaRe 2025 | IDSA Stewardship 2025",
    }
