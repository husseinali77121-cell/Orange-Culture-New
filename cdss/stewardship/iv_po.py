# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""IV-to-oral switch evaluation."""
from typing import Any
from typing import Dict




# ═══════════════════════════════════════════════════════════════════════
# ENGINE 2 -- IV->PO Switch Engine
# IDSA OPAT 2019 | BNF 2025 | BSAC 2023
# ═══════════════════════════════════════════════════════════════════════
HIGH_BIOAVAILABILITY: Dict[str, int] = {
    # Keys match abx_guidelines.py drug names exactly for cross-module consistency
    "Ciprofloxacin": 95, "Levofloxacin": 99, "Moxifloxacin": 90,
    "Ofloxacin": 95, "Norfloxacin": 30,
    "Metronidazole": 99, "Linezolid": 100,
    "Trimethoprim/Sulfamethoxazole": 90, "Doxycycline": 93,
    "Minocycline": 95, "Clindamycin": 87, "Fluconazole": 90,
    "Rifampicin": 95, "Amoxicillin": 90,
    "Amoxicillin + Clavulanic acid": 65,             # fixed: was "Amoxicillin-Clavulanate"
    "Cephalexin": 90, "Cephradine": 90, "Cefuroxime": 52, "Cefixime": 50,
    "Nitrofurantoin": 85, "Fosfomycin": 36, "Azithromycin": 37,
    "Clarithromycin": 52, "Erythromycin": 35, "Trimethoprim": 90,
}

# "bacteremia" removed 2026-11-10: oral step-down is standard for
# uncomplicated Gram-negative and streptococcal bacteraemia once the patient
# is stable (BALANCE 2025; IDSA cUTI 2025). S. aureus bacteraemia and
# endocarditis keep IV-only through their own entries.
ALWAYS_IV_SYNDROMES = frozenset([
    "endocarditis", "meningitis", "septic shock", "staphylococcus aureus bacteremia",
    "necrotizing fasciitis", "osteomyelitis (acute)", "vap",
])

def evaluate_iv_po_switch(
    drug_name: str, syndrome: str,
    clinical_improving: bool, tolerating_oral: bool,
    bacteremia_resolved: bool, days_on_iv: int,
    organism: str = "",
) -> Dict[str, Any]:
    """OPAT IV->PO Evaluation -- IDSA 2019 | BNF 2025

    `organism` added 2026-11-11 (round 4): ALWAYS_IV_SYNDROMES names
    "staphylococcus aureus bacteremia", but the syndrome passed in is the
    specimen-level label ("Bloodstream Infection (BSI) / Bacteremia"), which
    never carries the organism -- so the rule could not fire and S. aureus
    bacteraemia was cleared for oral switch like any Gram-negative one.
    """
    bioavail, matched = 0, ""
    # Exact name first (2026-11-11, round 4): with one substring pass in dict
    # order, "Ofloxacin" matched inside "Ciprofloxacin" and the panel quoted
    # the wrong drug's bioavailability.
    _dl = (drug_name or "").lower()
    for k, v in HIGH_BIOAVAILABILITY.items():
        if k.lower() == _dl:
            bioavail, matched = v, k
            break
    else:
        for k, v in HIGH_BIOAVAILABILITY.items():
            if _dl and _dl in k.lower():
                bioavail, matched = v, k
                break

    blockers, supporters = [], []
    if not clinical_improving: blockers.append("No clinical improvement in 48-72h")
    else:                      supporters.append("Clinical improvement documented")
    if not tolerating_oral:    blockers.append("Not tolerating oral intake")
    else:                      supporters.append("Tolerating oral medications")
    if not bacteremia_resolved: blockers.append("Active bacteremia / endovascular infection")
    else:                       supporters.append("No active bloodstream infection")

    if bioavail >= 80:     supporters.append(f"{matched}: Oral bioavailability {bioavail}% -- excellent for switch")
    elif bioavail >= 50:   blockers.append(f"{matched}: Moderate bioavailability ({bioavail}%) -- consider IV continuation")
    elif bioavail > 0:     blockers.append(f"{matched}: Low bioavailability ({bioavail}%) -- IV preferred")
    else:                  blockers.append(f"{drug_name}: No established oral equivalent")

    synd_lower = (syndrome or "").lower()
    if any(s in synd_lower for s in ALWAYS_IV_SYNDROMES):
        blockers.append(f"{syndrome} -- requires prolonged IV therapy")
    _org_l = (organism or "").lower()
    if (("aureus" in _org_l or "mrsa" in _org_l or "mssa" in _org_l or "lugdunensis" in _org_l)
            and any(k in synd_lower for k in ("bacteremia", "bacteraemia", "bloodstream", "bsi"))
            and "staphylococcus aureus bacteremia" not in synd_lower):
        blockers.append("S. aureus bacteraemia -- IV therapy (>= 14 d from the first negative "
                        "culture); early oral step-down only for low-risk SAB after ID review "
                        "(SABATO, Lancet Infect Dis 2024)")
    if days_on_iv < 2:    blockers.append(f"Less than 48h on IV ({days_on_iv}d) -- complete initial IV course")
    else:                  supporters.append(f"{days_on_iv} days on IV -- appropriate reassessment window")

    can_switch = len(blockers) == 0
    return {
        "can_switch": can_switch, "bioavail": bioavail, "matched_drug": matched,
        "blockers": blockers, "supporters": supporters,
        "verdict": (f"Switch acceptable. Oral bioavailability: {bioavail}%." if can_switch
                    else "IV->PO switch NOT recommended at this time."),
        "ref": "IDSA OPAT 2019 | BNF 2025 | BSAC 2023",
    }
