# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Treatment-duration database and lookup."""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
import re

from cdss.common.specimen import (
    classify_specimen,
)


# ═══════════════════════════════════════════════════════════════════════
# CLINICAL DECISION ENGINES -- v4.0
# ① Treatment Duration  ② IV->PO Switch  ③ Hepatic Dosing (Child-Pugh)
# ④ Combination Therapy  ⑤ De-escalation Advisor
# References: IDSA AMR Guidance 2026 | Sanford 2025 | WHO AWaRe 2025
#             MERINO 2018 | NINJA 2020 | ATTACK 2023 | STOP-IT 2015
# ═══════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════
# ENGINE 1 -- Treatment Duration Engine
# IDSA AMR Guidance 2026 | Sanford Guide 2025 | ATS/IDSA CAP 2019
# IDSA cUTI 2025 | IDSA SSTI 2014 | STOP-IT trial 2015
# ═══════════════════════════════════════════════════════════════════════
# Durations re-read 2026-11-10 against IDSA cUTI 2025, BALANCE (NEJM 2025),
# ATS/IDSA HAP/VAP 2016 and IDSA bacterial meningitis. Defects fixed: cUTI and
# pyelonephritis were 10-14 days (14 for men), GNB bacteraemia was a flat 14
# days IV with no oral step-down, HAP/VAP sent non-fermenters to 14 days, and
# every CSF isolate that was not a pneumococcus got the 21-day GNB course --
# including N. meningitidis and H. influenzae (7 days). "IDSA UTI 2022" was
# not a real citation.
TREATMENT_DURATION_DB: Dict[str, Any] = {
    "UTI_uncomplicated_female": {
        "label": "Uncomplicated cystitis (Female)",
        "days": (1, 7), "standard": 5, "iv_days": 0, "po_days": 5,
        "notes": "Agent-dependent: Nitrofurantoin 5d | TMP-SMX 3d | Fosfomycin 3 g single dose | "
                 "beta-lactam 3-7d.",
        "follow_up_culture": False, "ref": "IDSA/ESCMID uncomplicated cystitis 2011",
    },
    "UTI_complicated": {
        "label": "Complicated UTI (incl. men, catheter-associated)",
        "days": (5, 14), "standard": 7, "iv_days": 0, "po_days": 7,
        "notes": "7d if prompt response (FQ 5-7d) -- men included. 10-14d only for delayed "
                 "response or an unresolved urological source. Oral step-down once improving.",
        "follow_up_culture": False, "ref": "IDSA cUTI Guideline 2025",
    },
    "Pyelonephritis_outpatient": {
        "label": "Pyelonephritis (Outpatient)",
        "days": (5, 7), "standard": 7, "iv_days": 0, "po_days": 7,
        "notes": "FQ 5-7d | TMP-SMX or beta-lactam 7d. Verify sensitivities.",
        "follow_up_culture": False, "ref": "IDSA cUTI Guideline 2025",
    },
    # v7.0 (review 2026-11-19): a febrile catheter-associated UTI had no row
    # and fell to "Pyelonephritis (Outpatient)", IV 0 d.
    "UTI_catheter": {
        "label": "Catheter-associated UTI (CA-UTI)",
        "days": (7, 14), "standard": 7, "iv_days": 2, "po_days": 5,
        "notes": ("7 d if prompt response, 10-14 d if delayed (IDSA CA-UTI). Replace the catheter "
                  "if in place >= 2 weeks and culture from the new one; remove it if no longer "
                  "needed. Oral step-down only to an agent the isolate is S to."),
        "follow_up_culture": False, "ref": "IDSA CA-UTI Guideline · IDSA cUTI Guideline 2025",
    },
    "Pyelonephritis_inpatient": {
        "label": "Pyelonephritis / cUTI (Inpatient)",
        "days": (7, 14), "standard": 7, "iv_days": 2, "po_days": 5,
        "notes": "7d total if prompt response (incl. urinary-source bacteraemia); IV until "
                 "afebrile 24-48h -> high-bioavailability oral step-down.",
        "follow_up_culture": False, "ref": "IDSA cUTI Guideline 2025",
    },
    "CAP_mild": {
        "label": "CAP -- Mild (Outpatient)",
        "days": (5, 7), "standard": 5, "iv_days": 0, "po_days": 5,
        "notes": "5 days adequate for mild CAP. No CURB-65 risk factors.",
        "follow_up_culture": False, "ref": "IDSA/ATS CAP Guidelines 2019",
    },
    "CAP_moderate": {
        "label": "CAP -- Moderate (Inpatient)",
        # FIX 2026-11-10 (round 2): was 7-10 d. ATS/IDSA 2019: treat until
        # clinically stable and for no less than 5 days; ATS 2025 suggests even
        # shorter courses for stable non-severe CAP.
        "days": (5, 7), "standard": 5, "iv_days": 2, "po_days": 3,
        "notes": "5d minimum and until clinically stable (afebrile 48-72h, <=1 instability "
                 "sign); ATS 2025: 3-5d is enough for non-severe CAP that stabilises early. "
                 "IV -> oral step-down at stability. 7d for MRSA / P. aeruginosa.",
        "follow_up_culture": False, "ref": "ATS/IDSA CAP 2019 | ATS CAP 2025",
    },
    "CAP_severe": {
        "label": "CAP -- Severe (ICU)",
        # FIX 2026-11-10 (round 2): was 10-14 d. Severity alone does not
        # lengthen CAP therapy; complications and specific pathogens do.
        "days": (5, 10), "standard": 7, "iv_days": 4, "po_days": 3,
        "notes": ">=5d and until clinically stable; 7d for MRSA / P. aeruginosa (ATS/IDSA 2019). "
                 "Longer only for empyema, abscess, S. aureus bacteraemia, Legionella with slow "
                 "response. PCT can support stopping.",
        "follow_up_culture": True, "ref": "ATS/IDSA CAP 2019 | ATS CAP 2025",
    },
    "HAP_VAP": {
        "label": "HAP / VAP",
        "days": (7, 14), "standard": 7, "iv_days": 7, "po_days": 0,
        "notes": "7d for HAP and VAP, non-fermenters included (ATS/IDSA 2016). Longer only for "
                 "slow response, abscess, empyema or immunosuppression.",
        "follow_up_culture": False, "ref": "ATS/IDSA HAP/VAP 2016",
    },
    "Bacteremia_GNB": {
        "label": "GNB Bacteremia",
        "days": (7, 14), "standard": 7, "iv_days": 3, "po_days": 4,
        "notes": "7d if the source is controlled and the patient is improving (BALANCE, NEJM 2025); "
                 "14d for uncontrolled source, severe immunosuppression or slow response. Oral "
                 "step-down (FQ / TMP-SMX / high-bioavailability beta-lactam) once stable.",
        "follow_up_culture": False, "ref": "BALANCE 2025 | IDSA cUTI 2025",
    },
    "Bacteremia_Enterococcus": {
        "label": "Enterococcal Bacteremia",
        "days": (7, 14), "standard": 7, "iv_days": 7, "po_days": 0,
        "notes": "7-14d if uncomplicated and the source is removed. E. faecalis: assess for "
                 "endocarditis (DENOVA score / echo) -- endocarditis needs 4-6 weeks.",
        "follow_up_culture": True, "ref": "Expert consensus | ESC Endocarditis 2023",
    },
    "Bacteremia_Strep": {
        "label": "Streptococcal Bacteremia",
        "days": (10, 14), "standard": 10, "iv_days": 5, "po_days": 5,
        "notes": "10-14d (oral step-down possible once stable). Exclude endocarditis if persistent "
                 "or viridans group.",
        "follow_up_culture": False, "ref": "Expert consensus",
    },
    "Bacteremia_CoNS": {
        "label": "Coagulase-negative Staphylococcal Bacteremia",
        "days": (5, 14), "standard": 7, "iv_days": 7, "po_days": 0,
        "notes": "Treat only if TRUE infection (>=2 sets / device). 5-7d after catheter removal; "
                 "10-14d with catheter retention + lock therapy. Single positive bottle = "
                 "contaminant until proven otherwise.",
        "follow_up_culture": True, "ref": "IDSA CRBSI 2009",
    },
    "Bacteremia_MSSA": {
        "label": "MSSA Bacteremia",
        "days": (14, 42), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "Min 14d from first negative culture (uncomplicated) | 28-42d (complicated/"
                 "endovascular). Echo + repeat blood cultures mandatory. ID consult.",
        "follow_up_culture": True, "ref": "IDSA MRSA 2011 (SAB principles) | expert consensus",
    },
    "Bacteremia_MRSA": {
        "label": "MRSA Bacteremia",
        "days": (14, 42), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "Vancomycin AUC/MIC target 400-600. Min 14d (uncomplicated) | 42d (endocarditis).",
        "follow_up_culture": True, "ref": "IDSA MRSA Guidelines 2011 | ASHP/IDSA/PIDS/SIDP vancomycin consensus 2020",
    },
    "Meningitis_pneumococcal": {
        "label": "Pneumococcal Meningitis",
        "days": (10, 14), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "Dexamethasone 0.15 mg/kg q6h x 2-4d, started before or with the first "
                 "antibiotic dose. IV throughout.",
        "follow_up_culture": True, "ref": "IDSA Bacterial Meningitis 2004",
    },
    "Meningitis_meningococcal": {
        "label": "Meningococcal Meningitis",
        "days": (7, 7), "standard": 7, "iv_days": 7, "po_days": 0,
        "notes": "7d IV. Chemoprophylaxis for close contacts.",
        "follow_up_culture": False, "ref": "IDSA Bacterial Meningitis 2004",
    },
    "Meningitis_haemophilus": {
        "label": "H. influenzae Meningitis",
        "days": (7, 7), "standard": 7, "iv_days": 7, "po_days": 0,
        "notes": "7d IV. Dexamethasone in children (before/with first dose).",
        "follow_up_culture": False, "ref": "IDSA Bacterial Meningitis 2004",
    },
    "Meningitis_listeria": {
        "label": "Listeria Meningitis",
        "days": (21, 42), "standard": 21, "iv_days": 21, "po_days": 0,
        "notes": ">=21d IV (longer for rhombencephalitis/abscess). Ampicillin +/- gentamicin.",
        "follow_up_culture": True, "ref": "IDSA Bacterial Meningitis 2004",
    },
    "Meningitis_GBS": {
        "label": "Group B Streptococcal Meningitis",
        "days": (14, 21), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "14-21d IV.", "follow_up_culture": True, "ref": "IDSA Bacterial Meningitis 2004",
    },
    "Meningitis_GNB": {
        "label": "Gram-Negative Meningitis",
        "days": (21, 21), "standard": 21, "iv_days": 21, "po_days": 0,
        "notes": "21d IV for aerobic Gram-negative bacillary meningitis. Verify CSF sterilization.",
        "follow_up_culture": True, "ref": "IDSA Bacterial Meningitis 2004",
    },
    # ── Added 2026-11-11 (round 4) ─────────────────────────────────────────
    # Every CSF isolate that was not pneumococcus / meningococcus /
    # H. influenzae / Listeria / GBS fell to "Gram-Negative Meningitis, 21 d" --
    # S. aureus, MRSA, CoNS, enterococci and unidentified Gram-positive cocci
    # included.
    "Meningitis_staph": {
        "label": "Staphylococcal Meningitis / Ventriculitis",
        "days": (10, 14), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "Usually shunt / EVD / post-neurosurgical: remove or externalise the device. "
                 "S. aureus 10-14d; CoNS 10d with minimal CSF abnormality, 10-14d with "
                 "pleocytosis / low glucose -- counted from the first sterile CSF culture. "
                 "Repeat CSF cultures until sterile.",
        "follow_up_culture": True,
        "ref": "IDSA Healthcare-Associated Ventriculitis and Meningitis 2017",
    },
    "Meningitis_other": {
        "label": "Bacterial Meningitis (other / not fully identified)",
        "days": (10, 21), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "No organism-specific duration: set it on the FINAL identification and the CSF "
                 "response (pneumococcus 10-14d, GBS 14-21d, staphylococci 10-14d, enterococci / "
                 "viridans streptococci >=14d). Identify the organism; ID consultation.",
        "follow_up_culture": True,
        "ref": "IDSA Bacterial Meningitis 2004 | IDSA 2017",
    },
    "Bacteremia_GPC_unidentified": {
        "label": "Gram-positive cocci bacteremia (not yet identified)",
        "days": (5, 14), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "Treat as S. aureus until identified (clusters on Gram stain): repeat blood "
                 "cultures, no oral step-down, echo if S. aureus. Re-set the duration on the "
                 "identification -- CoNS 5-7d after line removal, streptococci 10-14d, "
                 "enterococci 7-14d.",
        "follow_up_culture": True, "ref": "IDSA MRSA 2011 (SAB principles) | IDSA CRBSI 2009",
    },
    "Bacteremia_Listeria": {
        "label": "Listeria Bacteremia",
        "days": (14, 21), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "Ampicillin +/- gentamicin, 2 weeks IV for bacteraemia without CNS involvement; "
                 "LP / brain imaging if any neurological sign (>=21d for CNS infection). "
                 "Cephalosporins are inactive.",
        "follow_up_culture": True, "ref": "Expert consensus | IDSA Bacterial Meningitis 2004",
    },
    "Bacteremia_anaerobe": {
        "label": "Anaerobic Bacteremia",
        "days": (7, 14), "standard": 10, "iv_days": 3, "po_days": 7,
        "notes": "Duration follows the source (intra-abdominal, pelvic, abscess) and its control; "
                 "drain collections. Metronidazole is ~100% bioavailable -- oral step-down once "
                 "stable.",
        "follow_up_culture": False, "ref": "Expert consensus | IDSA IAI 2010",
    },
    "SSTI_mild": {
        "label": "SSTI -- Mild (Cellulitis)",
        "days": (5, 7), "standard": 5, "iv_days": 0, "po_days": 5,
        "notes": "5d oral adequate for uncomplicated cellulitis without systemic signs.",
        "follow_up_culture": False, "ref": "IDSA SSTI Guidelines 2014",
    },
    "SSTI_moderate": {
        "label": "SSTI -- Moderate",
        "days": (7, 14), "standard": 7, "iv_days": 2, "po_days": 5,
        "notes": "IV until afebrile + local improvement -> step-down oral.",
        "follow_up_culture": False, "ref": "IDSA SSTI 2014",
    },
    "SSTI_severe": {
        "label": "SSTI -- Severe / Necrotizing",
        "days": (10, 21), "standard": 14, "iv_days": 14, "po_days": 0,
        "notes": "IV + surgical source control. ID consult mandatory.",
        "follow_up_culture": True, "ref": "IDSA SSTI 2014",
    },
    "Osteomyelitis": {
        "label": "Osteomyelitis",
        "days": (42, 84), "standard": 42, "iv_days": 14, "po_days": 28,
        "notes": "IV 2 weeks -> high-bioavailability oral 4+ weeks. Total ≥6 weeks.",
        "follow_up_culture": True, "ref": "IDSA Vertebral Osteomyelitis 2015 | OVIVA (NEJM 2019)",
    },
    "Intraabdominal_mild": {
        "label": "Intraabdominal Infection (Source Controlled)",
        "days": (4, 7), "standard": 4, "iv_days": 2, "po_days": 2,
        "notes": "4d if source controlled (STOP-IT trial 2015). Extend only for ongoing sepsis.",
        "follow_up_culture": False, "ref": "IDSA IAI 2010 | STOP-IT 2015",
    },
    "Intraabdominal_severe": {
        "label": "Intraabdominal Infection (Severe)",
        # FIX 2026-11-10 (round 2): was 7-14 d. With adequate source control
        # ~4 days is as good as longer (STOP-IT, NEJM 2015; SIS 2017).
        "days": (4, 7), "standard": 5, "iv_days": 4, "po_days": 1,
        "notes": "4-7d AFTER adequate source control (STOP-IT). Persisting signs beyond day 7 "
                 "mean failed source control -> re-image, do not just extend antibiotics.",
        "follow_up_culture": True, "ref": "STOP-IT (NEJM 2015) | SIS 2017 | IDSA IAI 2010",
    },
    "GI_mild": {
        "label": "GI Infection -- Mild/Moderate (Supportive Care)",
        "days": (0, 5), "standard": 0, "iv_days": 0, "po_days": 0,
        "notes": "Most GI infections: supportive care (fluids, electrolytes). "
                 "Antibiotics ONLY for: bloody diarrhea, immunocompromised, "
                 "severe dehydration, Salmonella typhi, Shigella, C. diff.",
        "follow_up_culture": False, "ref": "IDSA Foodborne GI 2017 | WHO 2025",
    },
    "GI_severe": {
        "label": "Severe GI Infection / Immunocompromised",
        "days": (3, 7), "standard": 5, "iv_days": 2, "po_days": 3,
        "notes": "Azithromycin or Ciprofloxacin 3-5d. C. diff -> Fidaxomicin or Vancomycin 10d (IDSA/SHEA 2021). "
                 "Salmonella typhi -> 7-14d. Reassess daily.",
        "follow_up_culture": True, "ref": "IDSA 2017 | Sanford 2025",
    },
}

def _sir_lookup(drug: str, sir_map: Dict[str, str]) -> Optional[str]:
    """Return S/I/R for `drug` from sir_map, matching keys tolerantly."""
    if not sir_map:
        return None
    # "SDD" must not be read by its first letter as S (CLSI SDD is read as I).
    from cdss.therapy.clsi_categories import canonical_panel
    sir_map = canonical_panel(sir_map)
    try:
        from cdss.formulary.abx_guidelines import normalize_abx_key
        target = normalize_abx_key(drug)
        for k, v in sir_map.items():
            if normalize_abx_key(k) == target:
                return ((v or "").strip().upper()[:1]) or None
    except Exception:
        low = {k.lower(): v for k, v in sir_map.items()}
        val = low.get(drug.lower())
        return ((val or "").strip().upper()[:1]) or None
    return None

_REGIMEN_TOKENS = [
    ("TMP-SMX",        ["Trimethoprim/Sulfamethoxazole"]),
    ("Nitrofurantoin", ["Nitrofurantoin"]),
    ("Fosfomycin",     ["Fosfomycin"]),
    ("FQ",             ["Ciprofloxacin", "Ofloxacin", "Norfloxacin",
                        "Levofloxacin", "Gatifloxacin", "Moxifloxacin"]),
]

def _regimen_token_status(drug_names, sir_map) -> str:
    seen = [s for s in (_sir_lookup(d, sir_map) for d in drug_names) if s]
    if not seen:
        return "NT"
    if "S" in seen:
        return "S"
    if "I" in seen:
        return "I"
    return "R"

def annotate_regimen_note(note: str, sir_map: Dict[str, str], lang: str = "ar") -> str:
    """Flag each guideline agent quoted in a duration note with its real AST
    status, so the note can never contradict the antibiogram. Sensitive agents
    stay unflagged; R / I / not-tested agents are marked."""
    if not note or not sir_map:
        return note
    flags = {
        "R":  " ⚠️[R -- مقاوم في هذه المزرعة]" if lang == "ar" else " ⚠️[R -- resistant here]",
        "I":  " [I]",
        "NT": " [غير مُختبر]" if lang == "ar" else " [not tested]",
    }
    out = note
    for token, drugs in _REGIMEN_TOKENS:
        if token not in out:
            continue
        flag = flags.get(_regimen_token_status(drugs, sir_map), "")
        if not flag:
            continue
        out = re.sub(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])",
                     lambda m: m.group(0) + flag, out, count=1)
    return out

def get_treatment_duration(
    specimen: str, organism: str, syndrome: str,
    age: int, sex: str, is_renal: bool,
    phenotypes: List[Dict], severity: str = "moderate",
    *,
    is_cath: bool = False,
    primary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Treatment Duration Engine -- IDSA AMR Guidance 2026 | Sanford Guide 2025

    v7.0 (review 2026-11-19):
      is_cath  a urinary catheter is in place (case record) -> CA-UTI row.
      primary  the top-ranked agent; its ROUTE sets the IV / PO split. The
               panel printed "IV: 0 d · PO: 7 d" under gentamicin IV/IM as the
               only active agent.
    """
    org  = organism.lower()
    synd = (syndrome or "").lower()
    _cat = classify_specimen(specimen)
    ph   = [p.get("phenotype", "") for p in phenotypes]
    has_mrsa = "MRSA" in ph
    has_mdr  = any(x in ph for x in ["MDR", "XDR", "PDR", "CRE", "CRPA", "CRAB"])

    key = None
    if _cat == "urine":
        if is_cath and (severity != "mild" or any(k in synd for k in ["pyelonephritis", "upper",
                                                                     "kidney", "pyelo"])):
            key = "Pyelonephritis_inpatient" if severity == "severe" else "UTI_catheter"
        elif any(k in synd for k in ["pyelonephritis", "upper", "kidney", "pyelo"]):
            # Syndrome explicitly says pyelonephritis
            key = "Pyelonephritis_inpatient" if severity == "severe" else "Pyelonephritis_outpatient"
        elif severity == "severe":
            # Severe UTI without explicit syndrome -> treat as pyelonephritis/inpatient
            key = "Pyelonephritis_inpatient"
        elif severity == "moderate" or sex == "Male" or age >= 65 or is_renal or has_mdr:
            # Complicated: male, elderly, renal impaired, MDR, or moderate severity
            key = "UTI_complicated"
        else:
            # Mild + female + young + no complicating factors -> uncomplicated
            key = "UTI_uncomplicated_female"
    elif _cat == "sputum":
        if any(k in synd for k in ["hap", "vap", "hospital", "ventil"]):
            key = "HAP_VAP"
        elif severity == "mild":   key = "CAP_mild"
        elif severity == "severe": key = "CAP_severe"
        else:                      key = "CAP_moderate"
    elif _cat == "blood":
        # 2026-11-10: every non-S. aureus isolate used to get the GNB course
        # (CoNS, enterococci and streptococci included).
        # 2026-11-11 (round 4): "Staphylococcus spp." inherits S. aureus
        # everywhere else in the engine, but here it fell to the CoNS course
        # ("single bottle = contaminant"); unidentified Gram-positive cocci,
        # Listeria and anaerobes fell to "GNB Bacteremia".
        if has_mrsa or "mrsa" in org:           key = "Bacteremia_MRSA"
        elif ("staphylococcus aureus" in org or "lugdunensis" in org
              or org.strip().startswith("staphylococcus spp")):
            key = "Bacteremia_MSSA"            # S. lugdunensis behaves like S. aureus
        elif "coagulase" in org or "staphylococc" in org:
            key = "Bacteremia_CoNS"
        elif "enterococc" in org or org.strip() == "vre":
            key = "Bacteremia_Enterococcus"
        elif "streptococc" in org:               key = "Bacteremia_Strep"
        elif "gram-positive" in org or "gram positive" in org:
            key = "Bacteremia_GPC_unidentified"
        elif "listeria" in org:                  key = "Bacteremia_Listeria"
        elif "anaerob" in org or "لاهوائ" in org or "bacteroides" in org:
            key = "Bacteremia_anaerobe"
        else:                                    key = "Bacteremia_GNB"
    elif _cat == "csf":
        # Match pneumococcus explicitly so Klebsiella *pneumoniae* (a GNB) is not
        # mis-routed to the pneumococcal-meningitis protocol.
        _is_pneumococcus = ("streptococcus pneumoniae" in org
                            or "s. pneumoniae" in org or "pneumococc" in org)
        if _is_pneumococcus:                     key = "Meningitis_pneumococcal"
        elif "meningitidis" in org or "meningococc" in org:
            key = "Meningitis_meningococcal"
        elif "influenzae" in org or "haemophilus" in org:
            key = "Meningitis_haemophilus"
        elif "listeria" in org:                  key = "Meningitis_listeria"
        elif "agalactiae" in org or "group b" in org:
            key = "Meningitis_GBS"
        elif has_mrsa or any(k in org for k in ("staphylococc", "mrsa", "mssa", "coagulase")):
            key = "Meningitis_staph"
        elif any(k in org for k in ("enterococc", "streptococc", "gram-positive",
                                    "gram positive")) or org.strip() == "vre":
            key = "Meningitis_other"
        else:                                    key = "Meningitis_GNB"
    elif _cat in ("wound", "pus"):
        if any(k in synd for k in ["necrotiz", "fasciitis", "gangrene"]): key = "SSTI_severe"
        elif "osteomyelitis" in synd or "bone" in synd:                    key = "Osteomyelitis"
        elif severity == "mild":   key = "SSTI_mild"
        elif severity == "severe": key = "SSTI_severe"
        else:                      key = "SSTI_moderate"
    elif _cat == "stool":
        # GI infections: most need NO antibiotic; treat only severe/immunocompromised
        key = "GI_severe" if severity == "severe" else "GI_mild"
    elif _cat == "abdomen":
        key = "Intraabdominal_severe" if severity == "severe" else "Intraabdominal_mild"

    if not key:
        return {"label": "Not matched", "min_days": 7, "max_days": 14, "standard_days": 10,
                "iv_days": 3, "po_days": 7, "notes": "Individualize based on clinical response.",
                "follow_up_culture": True, "ref": "Clinical judgment"}

    d = TREATMENT_DURATION_DB[key].copy()
    mn, mx = d["days"]
    notes_extra = []
    if has_mdr:
        # 2026-11-10: was `mx = max(mx, 14)`. Once an ACTIVE agent is given,
        # duration does not differ for resistant organisms (IDSA AMR 2026).
        notes_extra.append("MDR organism: same duration as for a susceptible isolate once on an "
                           "active agent (IDSA AMR 2026); the clock starts at active therapy.")
    if is_renal: notes_extra.append("Renal impairment: monitor drug levels closely.")
    if age > 65:  notes_extra.append("Elderly: monitor for toxicity; shorter courses if responding.")
    if notes_extra:
        _base = d.get("notes") or ""
        d["notes"] = (_base + " | " if _base else "") + " | ".join(notes_extra)
    d.update({"min_days": mn, "max_days": mx, "standard_days": d["standard"]})
    _route_split(d, primary)
    return d


def _route_split(d: Dict[str, Any], primary: Optional[Dict[str, Any]]) -> None:
    """Make the IV / PO split agree with the route of the agent actually chosen."""
    if not primary:
        return
    name = str(primary.get("name", ""))
    total = int(d.get("standard_days") or d.get("standard") or 0)
    if not name or total <= 0:
        return
    # `high_po` is the formulary's oral-route flag (the same one the screen's
    # "Route" line and the ranking read: cdss.common.util.get_route_label).
    oral = primary.get("high_po")
    if oral is None:
        from cdss.formulary.abx_guidelines import ABX_GUIDELINES
        oral = (ABX_GUIDELINES.get(name) or {}).get("high_po", False)
    if not oral:
        if int(d.get("po_days") or 0) > 0:
            d["iv_days"], d["po_days"] = total, 0
            d["route_note"] = (f"{name} is parenteral only (IV/IM): the whole course is parenteral "
                               "unless an oral agent tests S for a step-down.")
            d["notes"] = (d.get("notes") or "") + " | " + d["route_note"]
    elif int(d.get("iv_days") or 0) == 0 and int(d.get("po_days") or 0) == 0:
        d["po_days"] = total
