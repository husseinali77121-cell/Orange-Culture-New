# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""run_analysis(): the whole clinical pipeline as one pure function."""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from cdss.common.aux_tests import is_aux_key
from cdss.common.case_context import (
    LOW_MUSCLE_CRCL_NOTE_AR,
    LOW_MUSCLE_CRCL_NOTE_EN,
    TDM_AGENTS,
    build_case_context,
)
from cdss.therapy.clsi_categories import canonical_panel
from cdss.organisms.pathogenicity import gate_suppresses, treatment_gate
from cdss.common.specimen import (
    classify_specimen,
)
from cdss.health import (
    INTRINSIC_TABLE_OK,
    SAFETY_GATE_AVAILABLE,
    apply_safety_gate,
)
from cdss.resistance.mdr import (
    classify_mdr,
)
from cdss.resistance.mechanism import (
    predict_esbl,
)
from cdss.resistance.phenotypes import (
    detect_resistance_phenotypes,
)
from cdss.stewardship.combination import (
    get_combination_therapy,
)
from cdss.stewardship.duration import (
    get_treatment_duration,
)
from cdss.stewardship.ranking import (
    rank_sensitive_antibiotics,
)
from cdss.stewardship.severity import (
    suggest_severity,
)
from cdss.stewardship.syndrome import (
    get_infection_syndrome,
)
from cdss.therapy.engine import (
    analyze_antibiotics,
)


# ═══════════════════════════════════════════════════════════════════════════
#  run_analysis() — THE PIPELINE AS ONE CALLABLE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════
#  WHY THIS EXISTS
#  Until 2026-08-03 the whole decision pipeline lived INSIDE the Streamlit UI
#  block, and that block sits behind an OCR file upload. Line-tracing a full UI
#  run reached 12.8% of this file and touched NONE of analyze_antibiotics,
#  apply_safety_gate, detect_resistance_phenotypes or generate_report: without a
#  file there is no drug list, so the analysis never starts.
#
#  The consequence was not theoretical. A text replacement added `age_months=`
#  to two get_combination_therapy() calls that take no such parameter — a
#  TypeError on the combination panel and on PDF export — and all ten suites
#  stayed green, because every suite calls these functions DIRECTLY with correct
#  arguments and none of them walks the path the user walks.
#
#  This function is that path, minus Streamlit. It takes a Patient, an organism,
#  a specimen and an S/I/R map, and returns everything the UI renders. The UI
#  now calls it instead of inlining it, so a test can walk the same code the
#  clinician does — which is the only way the class of bug above gets caught.
#
#  It is deliberately PURE: no session_state, no widgets, no I/O. Everything it
#  needs arrives as arguments and everything it produces is returned.
# ═══════════════════════════════════════════════════════════════════════════
def run_analysis(
    patient: "Patient",
    organism: str,
    specimen: str,
    sir_map: Dict[str, str],
    drugs: Optional[List[str]] = None,
    *,
    apply_gate: bool = True,
    carbapenemase_type: Optional[str] = None,
    uti_syndrome: Optional[str] = None,
    pathogenicity: Optional[Dict[str, Any]] = None,
    treat_override: bool = False,
) -> Dict[str, Any]:
    """Run the full clinical pipeline and return every panel the UI shows.

    Returns a dict with: allowed / warned / banned / preg_warn / interactions,
    gate_report, phenotypes, mdr, mechanism, ranked, combinations, syndrome,
    duration, severity, patient_warnings.

    `carbapenemase_type` (KPC / OXA-48 / MBL, from NG-Test CARBA-5, Xpert or
    PCR) and `uti_syndrome` (cystitis / upper / None) were added 2026-11-10:
    without the first the engine cannot choose between the novel agents, and
    without the second it cannot tell a cystitis from a pyelonephritis.

    `pathogenicity` (v7.2) is the CURRENT assess_pathogenicity() result, if one
    was calculated. A "do not treat" verdict (asymptomatic bacteriuria,
    contaminant, colonisation, rejected sputum) sets `treatment_gate` and empties
    `ranked` and `duration` -- the drug-safety buckets are still returned, so a
    physician who overrides (`treat_override=True`, recorded in the gate) sees
    the same lists.
    """
    # D-test / penicillinase travel in the panel as Positive / Negative. The
    # therapy engine reads them from the panel as entered; every other step
    # (gate, MDR, mechanism, phenotypes, ranking) gets the S/I/R rows only.
    raw_panel = dict(sir_map or {})
    # CLSI SDD (v6.9, decision D4): the therapy engine reads it from the raw
    # panel (it names the SDD regimen); every other step sees it as the I it is
    # interpreted as -- none of them knows the word.
    sir_map = canonical_panel({d: v for d, v in raw_panel.items() if not is_aux_key(d)})
    drugs = list(drugs if drugs is not None else sir_map.keys())
    k = patient.as_kwargs()
    # v7.0: ONE record of the case facts (collection method, host factors).
    case = build_case_context(specimen, list(getattr(patient, "host_factors", None) or []),
                              getattr(patient, "collection_method", ""))
    # v7.1 (IDSA cUTI 2025): a urinary catheter / nephrostomy makes the UTI
    # complicated. With no explicit choice the engine now treats it as one --
    # the same rule the UI applies (therapy_rules.resolve_uti_syndrome).
    # v7.2 (second external review): complicated, not pyelonephritis -- "cuti".
    # v7.3 (third review): a device keeps an explicit "lower" complicated too.
    if uti_syndrome in (None, "lower") and case.cuti_device:
        uti_syndrome = "cuti"

    allowed, warned, banned, preg_warn, interactions = analyze_antibiotics(
        drugs, organism, specimen, k["age"], k["sex"], k["is_renal"],
        k["cl_cr"], k["is_preg"], k["is_hepatic"], k["current_meds"], raw_panel,
        k["child_pugh"], k["age_months"],
        carbapenemase_type=carbapenemase_type, uti_syndrome=uti_syndrome,
        allergies=list(getattr(patient, "allergies", None) or []),
        weight_kg=getattr(patient, "weight_kg", None),
    )

    gate_report: Dict[str, Any] = {}
    if apply_gate and SAFETY_GATE_AVAILABLE:
        allowed, warned, banned, gate_report = apply_safety_gate(
            allowed, warned, banned,
            organism=organism, specimen=specimen, sir_map=sir_map,
            age_years=k["age"], age_months=k["age_months"],
            is_pregnant=k["is_preg"], cl_cr=k["cl_cr"], is_renal=k["is_renal"],
            is_hepatic=k["is_hepatic"], child_pugh=k["child_pugh"],
        )
        # 2026-11-11 (round 4): the pregnancy-caution bucket passes the same
        # terminal check -- it used to be the one list the gate never saw.
        if preg_warn:
            from cdss.therapy.safety_gate import gate_pregnancy_bucket
            preg_warn, banned, _pmoves = gate_pregnancy_bucket(
                preg_warn, banned,
                organism=organism, specimen=specimen,
                age_years=k["age"], age_months=k["age_months"],
                is_pregnant=k["is_preg"], cl_cr=k["cl_cr"], is_renal=k["is_renal"],
                is_hepatic=k["is_hepatic"], child_pugh=k["child_pugh"],
            )
            if _pmoves:
                gate_report.setdefault("moves", []).extend(_pmoves)
                _c = gate_report.setdefault("counts", {})
                _c["banned"] = len(banned)
                _c["preg_warn"] = len(preg_warn)
                _c["moved"] = len(gate_report["moves"])

    if case.low_muscle_mass and not k["is_renal"]:
        _add_tdm_notes(allowed + warned)

    phenotypes = detect_resistance_phenotypes(organism, sir_map)
    mechanism = predict_esbl(organism, sir_map)
    mdr = classify_mdr(organism, sir_map)
    ranked = rank_sensitive_antibiotics(allowed, specimen, organism, sir_map, phenotypes,
                                        carbapenemase_type=carbapenemase_type,
                                        uti_syndrome=uti_syndrome)
    # v7.2: a "do not treat" pathogenicity verdict reaches the advice.
    treat_gate = treatment_gate(pathogenicity, override=treat_override)
    if gate_suppresses(treat_gate):
        ranked = []
    combinations = get_combination_therapy(
        phenotypes,
        is_pregnant=k["is_preg"], age_years=k["age"], age_months=k["age_months"],
        is_renal=k["is_renal"], cl_cr=k["cl_cr"], is_hepatic=k["is_hepatic"],
        organism=organism, carbapenemase_type=carbapenemase_type,
    )

    # FIX 2026-11-11 (round 4): this passed `cl_cr or 95`, so an UNKNOWN
    # clearance on a patient flagged renal -- and a measured clearance of 0 --
    # was read as a normal 95 ml/min and never made a UTI "complicated".
    # suggest_severity() resolves None itself (resolve_crcl), like every other
    # layer.
    severity = suggest_severity(specimen, k["age"], k["sex"], k["is_preg"],
                                k["is_renal"], k["cl_cr"])
    _uti_cath = case.is_cath and case.is_urine
    # v7.1: the device that names the syndrome for THIS specimen (urinary
    # catheter / ventilator / central line) -- HAP/VAP and CRBSI were unreachable.
    syndrome = get_infection_syndrome(specimen, organism, k["age"], k["is_preg"],
                                      is_cath=case.syndrome_device(), sex=k["sex"],
                                      uti_upper=str(uti_syndrome or "").lower() == "upper",
                                      complicated=str(uti_syndrome or "").lower() == "cuti")
    _syn_key = duration_syndrome_key(syndrome, uti_syndrome, specimen)
    duration = get_treatment_duration(
        specimen, organism, _syn_key, k["age"], k["sex"], k["is_renal"],
        phenotypes, severity.get("suggested", "moderate"),
        is_cath=_uti_cath, primary=(ranked[0] if ranked else None),
        is_preg=bool(k["is_preg"]),
    ) if not gate_suppresses(treat_gate) else None

    # ── Which safety layers actually ran ────────────────────────────────────
    # ADDED 2026-08-05 after an import-failure injection: with safety_gate or
    # clinical_matrix unimportable, this function returned a full, confident
    # result set with gate_report={} and said nothing. The UI does raise a
    # "DEGRADED CLINICAL MODE" banner, but run_analysis() is the PUBLIC entry
    # point now — anything calling it programmatically, this project's own test
    # suites included, received un-gated recommendations that were
    # indistinguishable from gated ones.
    #
    # A result that skipped the terminal safety check must SAY SO in the result,
    # not only on a page the caller may never render. Callers can then refuse to
    # report, and a test can assert the gate ran.
    degraded = []
    if not SAFETY_GATE_AVAILABLE:
        degraded.append("safety_gate + clinical_matrix — no site-penetration "
                        "check and no host-state demotion were applied")
    elif apply_gate and not gate_report:
        degraded.append("safety_gate returned no report — the terminal check "
                        "may not have run")
    if not INTRINSIC_TABLE_OK:
        degraded.append("clinical_data — intrinsically inactive agents were NOT "
                        "filtered out and are NOT excluded from MDR counting")

    return {
        "allowed": allowed, "warned": warned, "banned": banned,
        "preg_warn": preg_warn, "interactions": interactions,
        "gate_report": gate_report, "phenotypes": phenotypes,
        "mechanism": mechanism, "mdr": mdr, "ranked": ranked,
        "combinations": combinations, "severity": severity,
        "syndrome": syndrome, "duration": duration, "case": case,
        "patient_warnings": patient.validate(),
        # Empty on a healthy run. Non-empty means a safety layer did not run and
        # the result must not be reported as if it had.
        "degraded": degraded,
        "gate_applied": bool(apply_gate and SAFETY_GATE_AVAILABLE),
        # v7.2: None, or the no-treatment gate (see treatment_gate()).
        "treatment_gate": treat_gate,
    }

def _add_tdm_notes(items: List[Dict[str, Any]]) -> None:
    """Low muscle mass: creatinine overestimates GFR -> levels, not CrCl (v7.0)."""
    for it in items:
        if not isinstance(it, dict) or it.get("name") not in TDM_AGENTS:
            continue
        for key, txt in (("clinical_note", LOW_MUSCLE_CRCL_NOTE_AR),
                         ("clinical_note_en", LOW_MUSCLE_CRCL_NOTE_EN)):
            old = str(it.get(key) or "").strip()
            if txt not in old:
                it[key] = f"{old}  \n{txt}" if old else txt
        it["tdm_note"] = LOW_MUSCLE_CRCL_NOTE_AR
        it["tdm_note_en"] = LOW_MUSCLE_CRCL_NOTE_EN


def duration_syndrome_key(syndrome: Any, uti_syndrome: Optional[str], specimen: str) -> str:
    """The syndrome string the duration engine dispatches on.

    ONE place for it (2026-11-11, round 4). run_analysis() turned an "upper"
    UTI into "pyelonephritis" before asking for a duration, but the on-screen
    Treatment Duration panel and the PDF each asked again with the bare
    syndrome label ("Urinary Tract Infection (UTI)"). A clinician who picked
    "pyelonephritis / cUTI" in the sidebar therefore saw nitrofurantoin and
    fosfomycin removed by the engine and, in the panel below, the 5-day
    uncomplicated-cystitis course (nitrofurantoin 5 d | fosfomycin single dose).
    """
    if isinstance(syndrome, dict):
        # v7.1: the sub-type too -- "HAP/VAP" is a sub-type of "Respiratory Tract
        # Infection", and the duration engine never saw it.
        key = " | ".join(x for x in (str(syndrome.get("syndrome") or ""),
                                     str(syndrome.get("sub_type") or "")) if x)
    else:
        key = str(syndrome or "")
    if (str(uti_syndrome or "").lower() in ("upper", "pyelonephritis", "urosepsis")
            and classify_specimen(specimen) == "urine"):
        return "pyelonephritis"
    # v7.2: complicated without upper-tract signs -- the cUTI course, not pyelonephritis.
    if str(uti_syndrome or "").lower() == "cuti" and classify_specimen(specimen) == "urine":
        return "complicated UTI"
    return key
