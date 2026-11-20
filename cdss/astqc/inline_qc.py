# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Inline AST QC rules and the composed run_ast_qc()."""
from typing import Any
from typing import Dict
from typing import List

from cdss.common.log import logger
from cdss.ocr.ocr_parsing import normalize_sir_map
from cdss.common.specimen import (
    classify_specimen,
)
from cdss.health import (
    AST_RULES_MODULES_AVAILABLE,
    _check_consistency_ext,
    _check_reportability_ext,
    _fmt_consistency,
    _fmt_reportability,
)


# =========================================================
# MODULE 2 -- AST Internal Consistency & Reportability Checker
# INTERNAL QC ONLY. Feeds the AST-QA report and the QC expander. It NEVER
# changes the antibiotic recommendations (allowed / warned / banned): it only
# flags results that should be reviewed before sign-out, so no treatment
# decision is ever derived from it.
#
# Four passes, run in order (see run_ast_qc):
#   1) reportability  -- "should this agent be on this organism's panel?"
#                        (intrinsic resistance / no breakpoints / in-vivo failure)
#   2) consistency    -- "do these results contradict each other?"
#                        (equivalence + hierarchy, with CTX-M / OXA-48 guards)
#   3) specimen fit   -- urinary-only agents reported for a non-urine isolate
#   4) phenotype      -- ESBL / carbapenemase pattern notes
#
# Passes 1-2 are provided by the shared ast_reportability / ast_consistency
# modules (single source of truth with the Orange Lab build). Passes 3-4 are
# inline. Output is English (complete sentences) on purpose: the internal PDF
# renders right-to-left Arabic incorrectly.
#
# References: EUCAST Intrinsic Resistance v3.3 | EUCAST Breakpoint Tables v16.1 |
#             CLSI M100 Ed36 | EUCAST Expert Rules.
# =========================================================

def _sir_val(sir_map: Dict[str, str], drug: str) -> str:
    return (sir_map.get(drug) or "").strip().upper()

def _org_any(org_lower: str, names) -> bool:
    return any(n in org_lower for n in names)

# Urinary-only agents: therapeutic levels are reached in urine only, so a result
# for a non-urine (systemic) isolate is not clinically actionable.
_URINARY_ONLY = {
    "Nitrofurantoin": "Nitrofurantoin reaches therapeutic concentrations only in urine.",
    "Fosfomycin":     "Oral fosfomycin is a urinary agent (IV fosfomycin is the systemic exception).",
    "Norfloxacin":    "Norfloxacin reaches adequate concentrations only in the urinary and GI tracts.",
    # v6.9 (decision D5): licensed and studied for uncomplicated cystitis only.
    "Pivmecillinam":  "Pivmecillinam (tested as mecillinam) is licensed for uncomplicated cystitis only.",
    "Gepotidacin":    "Gepotidacin is licensed for uncomplicated cystitis (and urogenital gonorrhoea) only.",
    "Sulopenem":      "Oral sulopenem is licensed for uncomplicated cystitis only.",
}

# Non-Enterobacterales Gram-negatives NOT covered by the intrinsic-Enterobacterales
# reportability rule -- add a Gram-positive-only-agent guard for them here.
_NON_ENTERO_GN = ["pseudomonas", "acinetobacter", "stenotrophomonas",
                  "burkholderia", "moraxella"]

_GRAM_POS_ONLY = ["Vancomycin", "Teicoplanin", "Linezolid", "Daptomycin"]

def _pass_specimen_fit(specimen: str, sir_map: Dict[str, str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if classify_specimen(specimen) in ("urine", ""):   # urinary agents belong in urine
        return out
    for drug, why in _URINARY_ONLY.items():
        if _sir_val(sir_map, drug) in ("S", "I", "R"):
            out.append({
                "id": f"SPEC-URN:{drug}",
                "severity": "warning",
                "message": (f"⚠️ **Specimen appropriateness** — **{drug} [{_sir_val(sir_map, drug)}]** — "
                            f"tested on a {specimen} isolate. {why} It is not clinically actionable "
                            f"for a non-urinary (systemic) infection."),
                "fix": (f"Suppress {drug} from the {specimen} report; it is a urinary-tract agent only.  \n"
                        f"📖 CLSI M100 Ed36 / product labels — site of infection"),
            })
    return out

def _pass_non_entero_gram_pos(org_lower: str, sir_map: Dict[str, str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not _org_any(org_lower, _NON_ENTERO_GN):
        return out
    for drug in _GRAM_POS_ONLY:
        v = _sir_val(sir_map, drug)
        if v in ("S", "I", "R"):
            out.append({
                "id": f"REP-GPO-GN:{drug}",
                "severity": "error",
                "message": (f"🚫 **Intrinsic resistance** — **{drug} [{v}]** — reported for a "
                            f"Gram-negative organism, but {drug} has no activity and no breakpoint "
                            f"against Gram-negative bacteria."),
                "fix": (f"Remove {drug}; it must never be tested or reported for a Gram-negative isolate.  \n"
                        f"📖 CLSI M100 Ed36 Appendix B · EUCAST Intrinsic Resistance v3.3"),
            })
    return out

# ── Phenotype-level rules (ESBL / carbapenemase). Intrinsic-resistance and
#    equivalence checks that used to live here are now handled by the
#    reportability / consistency modules, so only the phenotype notes remain.
#    QC006 is corrected to the EUCAST v16.1 "report as tested" stance. ──
AST_QC_RULES = [
    {
        "id": "QC003",
        # Excluded: the Morganellaceae (Proteus / Providencia / Morganella) and
        # Serratia are INTRINSICALLY colistin-resistant, so "Colistin R" is the
        # expected result for them and flagging it as atypical sent the lab
        # chasing a correct identification. EUCAST v3.3 Table 1.
        "organisms": [],
        "not_organisms": ["proteus", "providencia", "morganella", "serratia",
                          "hafnia", "edwardsiella", "burkholderia"],
        "condition": lambda s: (
            any(s.get(d) == "S" for d in ["Imipenem/Cilastatin", "Meropenem"]) and
            s.get("Colistin") == "R" and
            sum(1 for v in s.values() if v == "R") >= 6
        ),
        "severity": "warning",
        "message": "⚠️ A carbapenem is Susceptible while Colistin is Resistant amid broad resistance. "
                   "This unusual pattern warrants confirmation of the organism identification.",
        "fix": "Verify the isolate identification; this susceptibility pattern is atypical.  \n"
               "📖 EUCAST Expert Rules (unusual phenotype — no CLSI counterpart)",
    },
    {
        "id": "QC004",
        "organisms": ["E. coli", "Escherichia", "Klebsiella", "Proteus", "Enterobacter",
                      "Citrobacter", "Serratia", "Enterobacterales"],
        # FIX 2026-11-10: split by marker. Imipenem R is EXPECTED in Proteeae
        # (intrinsically elevated MICs), so it cannot trigger the carbapenemase
        # prompt for Proteus / Morganella / Providencia. Meropenem/Ertapenem R
        # still does (QC004 below); imipenem R does for the rest (QC004b).
        "condition": lambda s: (
            any(s.get(d) == "S" for d in ["Ceftriaxone", "Cefotaxime", "Cefepime"]) and
            any(s.get(d) == "R" for d in ["Meropenem", "Ertapenem"])
        ),
        "severity": "warning",
        "message": "⚠️ A carbapenem is Resistant while a cephalosporin is Susceptible. This pattern is "
                   "uncommon (it may reflect an OXA-48-like carbapenemase or porin loss) and should be confirmed.",
        "fix": "Confirm with a carbapenemase assay (e.g., mCIM / PCR) before reporting.  \n"
               "📖 CLSI M100 Ed36 Tables 3B / 3C (mCIM / eCIM) · EUCAST detection guidance",
    },
    {
        "id": "QC004b",
        "organisms": ["E. coli", "Escherichia", "Klebsiella", "Enterobacter",
                      "Citrobacter", "Serratia", "Enterobacterales"],
        "not_organisms": ["proteus", "morganella", "providencia"],
        "condition": lambda s: (
            any(s.get(d) == "S" for d in ["Ceftriaxone", "Cefotaxime", "Cefepime"]) and
            s.get("Imipenem/Cilastatin") == "R"
            and s.get("Meropenem") != "R" and s.get("Ertapenem") != "R"
        ),
        "severity": "warning",
        "message": "⚠️ Imipenem is Resistant while a cephalosporin is Susceptible. This pattern is "
                   "uncommon (it may reflect a carbapenemase or porin loss) and should be confirmed.",
        "fix": "Confirm with a carbapenemase assay (e.g., mCIM / PCR) before reporting.  \n"
               "📖 CLSI M100 Ed36 Tables 3B / 3C (mCIM / eCIM) · EUCAST detection guidance",
    },
    {
        "id": "QC005",
        "organisms": ["Staphylococcus aureus", "MRSA"],
        "condition": lambda s: s.get("Linezolid") == "R",
        "severity": "warning",
        "message": "⚠️ Linezolid Resistance in Staphylococcus aureus is very rare and should be confirmed.",
        "fix": "Repeat by a reference method (Etest or broth microdilution) before reporting.  \n"
               "📖 CLSI M100 Ed36",
    },
    {
        "id": "QC006",
        "organisms": ["E. coli", "Escherichia", "Klebsiella", "Proteus"],
        "condition": lambda s: (
            any(s.get(d) == "R" for d in ["Ceftriaxone", "Cefotaxime"]) and
            any(s.get(d) == "S" for d in [
                "Cefuroxime", "Cephalexin", "Cefaclor", "Cefixime",
                "Cefoperazone", "Cefoperazone + Sulbactam"])
        ),
        "trigger_fn": lambda s: [
            d for d in ["Cefuroxime", "Cephalexin", "Cefaclor", "Cefixime",
                        "Cefoperazone", "Cefoperazone + Sulbactam"] if s.get(d) == "S"],
        "trigger_r_fn": lambda s: [d for d in ["Ceftriaxone", "Cefotaxime"] if s.get(d) == "R"],
        "severity": "warning",
        "message": "⚠️ **Pattern worth noting** — {r_drug} = R with a lower-generation cephalosporin "
                   "({drugs}) = S, a pattern often seen with ESBL production. First check for a "
                   "third-generation cephalosporin discrepancy (see any panel-discrepancy alerts above).",
        "fix": "LABORATORY REPORTING: report susceptibilities exactly as tested. Per CLSI M100 Ed36 Table 3A (and EUCAST Breakpoint "
               "Tables v16.1), the current cephalosporin breakpoints already detect the clinically "
               "important mechanisms, and the presence or absence of an ESBL does not by itself change "
               "the category -- do NOT edit a Susceptible cephalosporin to Resistant (that pre-2017 "
               "practice was withdrawn). ESBL detection is for infection control and surveillance only.  \n"
               "TREATMENT (separate, physician-level decision): a carbapenem is preferred over "
               "cephalosporins / piperacillin-tazobactam for ESBL bacteraemia even when they test "
               "Susceptible (IDSA AMR guidance; MERINO trial, JAMA 2018).  \n"
               "📖 CLSI M100 Ed36 Table 3A · EUCAST Breakpoint Tables v16.1 -- Enterobacterales cephalosporin note",
    },
]

def run_ast_qc(organism: str, sir_map: Dict[str, str], specimen: str = "",
               sdd=None) -> List[Dict[str, Any]]:
    """Internal AST consistency / reportability audit (English, informational only).

    INFORMATIONAL ONLY -- never consulted when building the antibiotic
    recommendations, so it can flag freely without affecting any decision.
    Returns a de-duplicated list of {id, severity, message, fix}.
    """
    _raw_panel = dict(sir_map or {})
    sir_map = normalize_sir_map(sir_map)
    if not sir_map:
        return []
    org_lower = (organism or "").lower()
    issues: List[Dict[str, Any]] = []

    # ── Pass 0 (v7.4): the panel is counted and named consistently ───────────
    # External case review 2026-11-20: "Errors: 0" beside counts that did not
    # reconcile and one agent listed as both tested and missing.
    try:
        from cdss.astqc.reconciliation import mandatory_checks
        from cdss.astqc.ast_panel_completeness import check_panel_completeness
        issues.extend(mandatory_checks(organism, specimen, _raw_panel,
                                       check_panel_completeness(organism, specimen, sir_map)))
    except Exception as _e:
        logger.warning("reconciliation pass failed: %s", _e, exc_info=True)

    # ── Pass 1: reportability (shared module) ────────────────────────────────
    if AST_RULES_MODULES_AVAILABLE and _check_reportability_ext:
        try:
            for _iss in _check_reportability_ext(organism, sir_map):
                _r = _fmt_reportability(_iss, lang="en")
                issues.append({
                    "id": _iss.get("id", "REP"),
                    "severity": _iss.get("severity", "warning"),
                    "message": _r["message"],
                    "fix": _r["fix"],
                })
        except Exception as _e:
            logger.warning("reportability pass failed: %s", _e, exc_info=True)

    # ── Pass 2: internal consistency (shared module) ─────────────────────────
    if AST_RULES_MODULES_AVAILABLE and _check_consistency_ext:
        try:
            for _iss in _check_consistency_ext(organism, sir_map):
                _r = _fmt_consistency(_iss, lang="en")
                issues.append({
                    "id": _iss.get("id", "CON"),
                    "severity": _iss.get("severity", "error"),
                    "message": _r["message"],
                    "fix": _r["fix"],
                })
        except Exception as _e:
            logger.warning("consistency pass failed: %s", _e, exc_info=True)

    # ── Pass 2b: phenotype plausibility (v7.0) ───────────────────────────────
    try:
        from cdss.astqc.phenotype_plausibility import check_plausibility, format_finding
        for _f in check_plausibility(organism, sir_map, sdd):
            _r = format_finding(_f, lang="en")
            issues.append({"id": _f["id"], "severity": _f["severity"],
                           "message": _r["message"],
                           "fix": _r["fix"].replace("✏️ ", "", 1) + "\n" + _r["reference"]})
    except Exception as _e:
        logger.warning("plausibility pass failed: %s", _e, exc_info=True)

    # ── Pass 3: specimen appropriateness + non-Enterobacterales GN guard ─────
    issues.extend(_pass_specimen_fit(specimen, sir_map))
    # The shared ast_reportability module now flags wrong-spectrum agents for ALL
    # Gram-negatives (a superset of this inline guard). Run the inline guard ONLY
    # as a fallback when that module is absent, so the two never double-report.
    if not AST_RULES_MODULES_AVAILABLE:
        issues.extend(_pass_non_entero_gram_pos(org_lower, sir_map))

    # ── Pass 4: phenotype rules ──────────────────────────────────────────────
    for rule in AST_QC_RULES:
        if rule["organisms"]:
            if not any(o.lower() in org_lower or org_lower in o.lower()
                       for o in rule["organisms"]):
                continue
        # Negative gating. Without this the "not_organisms" key on a rule would be
        # silently inert -- the rule would still fire on the very species it names
        # as exclusions. ast_reportability already supports this; AST_QC_RULES did
        # not, so the two rule engines disagreed on how a rule is scoped.
        if rule.get("not_organisms"):
            if any(o.lower() in org_lower for o in rule["not_organisms"]):
                continue
        try:
            if rule["condition"](sir_map):
                _msg = rule["message"]
                if "trigger_r_fn" in rule and "{r_drug}" in _msg:
                    _rt = rule["trigger_r_fn"](sir_map)
                    _msg = _msg.replace("{r_drug}", " / ".join(_rt) if _rt else "Cephalosporin")
                if "trigger_fn" in rule and "{drugs}" in _msg:
                    _tt = rule["trigger_fn"](sir_map)
                    _msg = _msg.replace("{drugs}", " / ".join(_tt) if _tt else "Cephalosporin")
                issues.append({
                    "id": rule["id"], "severity": rule["severity"],
                    "message": _msg, "fix": rule["fix"],
                })
        except Exception as _exc:
            logger.warning("AST QC rule %s failed and was skipped: %s",
                           rule.get("id", "?"), _exc, exc_info=True)
            continue

    # De-duplicate identical findings
    _seen = set()
    _uniq: List[Dict[str, Any]] = []
    for it in issues:
        _k = (it["id"], it["message"])
        if _k not in _seen:
            _seen.add(_k)
            _uniq.append(it)
    return _uniq
