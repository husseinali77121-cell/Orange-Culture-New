# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""analyze_antibiotics(): the per-drug therapeutic decision.

    context  = build_context(...)          one frozen record of the case
    for each drug of the panel:
        outcome = Outcome()
        for rule in RULES:                 small functions, fixed order
            rule(context, drug, outcome)
            stop at the first BAN          (a caution does NOT stop the walk)
        bucket the drug                    banned > pregnancy caution > warned > allowed
    whole-panel steps                      upper UTI, notes, I flag, sort, specimen filter

RULES is the single place that fixes the order.  The order decides which reason
is shown first; it can no longer decide whether a later contraindication is
checked, because only a ban ends the walk.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.therapy import postprocess
from cdss.therapy.context import DrugUnderTest, TherapyContext, build_context
from cdss.therapy.notes import warned_note_for
from cdss.therapy.outcome import Outcome, PostNotes
from cdss.therapy.rules import age, allergy, host, mechanism, organism, panel, pregnancy, specific

Rule = Callable[[TherapyContext, DrugUnderTest, Outcome], None]

RULES: Tuple[Rule, ...] = (
    # ── the panel itself ────────────────────────────────────────────────────
    panel.rule_unreadable,
    panel.rule_resistant,
    panel.rule_interaction_alerts,
    # ── the patient's allergies ─────────────────────────────────────────────
    allergy.rule_allergy,
    # ── the organism ────────────────────────────────────────────────────────
    organism.rule_intrinsic,
    organism.rule_mrsa,
    organism.rule_possible_mrsa,
    organism.rule_novel_agents,
    organism.rule_pseudomonas_aminoglycosides,
    organism.rule_surrogate_and_no_breakpoint,
    organism.rule_organism_cautions,
    organism.rule_colistin,
    organism.rule_oral_fosfomycin,
    organism.rule_staph_penicillin_note,
    organism.rule_strep_tmp_smx,
    organism.rule_macrolide_cross_resistance,
    organism.rule_enterococci,
    organism.rule_pneumococcus_csf,
    organism.rule_staph_fluoroquinolone,
    # ── the resistance mechanism ────────────────────────────────────────────
    mechanism.rule_esbl_not_excluded,
    mechanism.rule_ampc_cefepime,
    mechanism.rule_esbl_cefepime,
    mechanism.rule_possible_carbapenemase_betalactam,
    mechanism.rule_esbl_or_carbapenemase_betalactam,
    mechanism.rule_carbapenemase_carbapenem,
    mechanism.rule_possible_carbapenemase_bli,
    mechanism.rule_esbl_or_carbapenemase_bli,
    # ── absolute host contraindications ─────────────────────────────────────
    age.rule_child,
    age.rule_neonate,
    age.rule_preterm_window,
    specific.rule_d_test,
    specific.rule_fusidic_alert,
    specific.rule_staph_penicillinase,
    specific.rule_oxacillin_alert,
    specific.rule_enterococcus_tmp_smx,
    specific.rule_nitrofurantoin_renal,
    pregnancy.rule_pregnancy,
    # ── host cautions: always last (see rules/host.py) ──────────────────────
    host.rule_hepatic,
    host.rule_renal_adjustment,
    host.rule_intermediate,
)

# Which key(s) hold the explanation of a caution, per warning_reason. Facts
# found by LATER rules are appended there, so every renderer prints them.
_NOTE_KEYS = {
    "esbl_bli_uti_only":      ("esbl_note", "esbl_note_en"),
    "possible_carbapenemase": ("esbl_note", "esbl_note_en"),
    "possible_mrsa":          ("possible_mrsa_note",),
    "neonate":                ("reason_detail",),
    "hepatic_adjustment":     ("hepatic_note",),
}


def judge_drug(cx: TherapyContext, dg: DrugUnderTest, post_notes: PostNotes) -> Outcome:
    """Walk one drug through every rule. Only a ban ends the walk."""
    out = Outcome(post_notes)
    for rule in RULES:
        rule(cx, dg, out)
        if out.banned is not None:
            break
    return out


def _secondary_lines(out: Outcome, lang: str) -> List[str]:
    return [t for t in (warned_note_for(it, lang) for it in out.secondary) if t]


def _finish_caution(out: Outcome) -> Dict[str, Any]:
    """The primary caution, with every later fact written into its note."""
    item = out.primary
    keys = _NOTE_KEYS.get(item.get("warning_reason") or "")
    if not keys:
        return item
    for key in ([k for k in keys if str(item.get(k) or "").strip()] or [keys[0]]):
        lang = "en" if key.endswith("_en") else "ar"
        lines = out.extra + _secondary_lines(out, lang)
        if lines:
            item[key] = (str(item.get(key) or "").rstrip() + "\n" + "\n".join(lines)).strip()
    return item


def _finish_pregnancy(out: Outcome) -> Dict[str, Any]:
    """The pregnancy caution, carrying any other caution and host fact with it."""
    item = out.preg_item
    lines: List[str] = list(out.preg_extra)
    if out.primary is not None:
        # The drug has a caution of its own AND a pregnancy caution. It is shown
        # in the pregnancy bucket; the other caution must not disappear.
        first = warned_note_for(out.primary, "ar")
        if first:
            lines.append(first)
        lines += out.extra
        lines += _secondary_lines(out, "ar")
    if lines:
        item["preg_note"] = ((item.get("preg_note") or "").rstrip()
                             + "\n" + "\n".join(lines)).strip()
    return item


def analyze_antibiotics(
    final_drugs: List[str],
    organism_type: str,
    culture_type: str,
    age: int,
    sex: str,
    is_renal: bool,
    cl_cr: Optional[float],
    is_preg: bool,
    is_hepatic: bool,
    current_meds: List[str],
    sir_map: Dict[str, str],
    child_pugh: str = "C",
    age_months: Optional[int] = None,
    *,
    carbapenemase_type: Optional[str] = None,
    uti_syndrome: Optional[str] = None,
    allergies: Optional[List[str]] = None,
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[str]]:
    """Sort the panel into (allowed, warned, banned, pregnancy cautions, alerts)."""
    cx, drugs = build_context(
        final_drugs, organism_type, culture_type, age, sex, is_renal, cl_cr, is_preg,
        is_hepatic, current_meds, sir_map, child_pugh, age_months,
        carbapenemase_type=carbapenemase_type, uti_syndrome=uti_syndrome, allergies=allergies,
    )
    allowed: List[Dict] = []
    warned: List[Dict] = []
    banned: List[Dict] = []
    preg_warn_items: List[Dict] = []
    post_notes: PostNotes = {}

    for drug in drugs:
        if drug not in ABX_GUIDELINES:
            continue
        info = ABX_GUIDELINES[drug]
        dg = DrugUnderTest(name=drug, info=info, low=drug.lower(),
                           cls=info.get("class", "").lower(), result=cx.sir.get(drug))
        out = judge_drug(cx, dg, post_notes)
        if out.banned is not None:
            banned.append(out.banned)
        elif out.preg_item is not None:
            preg_warn_items.append(_finish_pregnancy(out))
        elif out.primary is not None:
            warned.append(_finish_caution(out))
        else:
            allowed.append({"name": drug, **info})

    buckets = (allowed, warned, banned, preg_warn_items)
    buckets = postprocess.apply_upper_uti(cx, *buckets)
    buckets = postprocess.apply_clinical_notes(cx, *buckets, post_notes)
    buckets = postprocess.flag_intermediate(cx, *buckets)
    buckets = postprocess.sort_by_priority(cx, *buckets)
    allowed, warned, banned, preg_warn_items = postprocess.apply_specimen_filter(cx, *buckets)
    return allowed, warned, banned, preg_warn_items, sorted(set(cx.alerts))
