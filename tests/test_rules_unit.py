# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""Each rule tested on its own: one context, one drug, one Outcome.

This is what the decomposition buys: a rule can be exercised without running
the other 38, the pipeline, the gate or the page.
"""
import pytest

from cdss.therapy.outcome import Outcome
from cdss.therapy.rules import age, host, mechanism, organism, panel, pregnancy, specific
from support.cases import apply, context, drug


# ── panel ───────────────────────────────────────────────────────────────────
def test_resistant_is_banned():
    out = apply(panel.rule_resistant, context(sir={"Ciprofloxacin": "R"}), drug("Ciprofloxacin", "R"))
    assert out.banned["category"] == "resistant"


def test_unreadable_result_is_never_assumed_susceptible():
    cx = context(sir={"Ciprofloxacin": "?"})
    out = apply(panel.rule_unreadable, cx, drug("Ciprofloxacin", None))
    assert out.banned["category"] == "unreadable"


def test_susceptible_passes_the_panel_rules():
    cx = context(sir={"Ciprofloxacin": "S"})
    for rule in (panel.rule_unreadable, panel.rule_resistant):
        assert apply(rule, cx, drug("Ciprofloxacin", "S")).banned is None


# ── age ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,age_years,banned", [
    ("Ciprofloxacin", 10, True),       # fluoroquinolone under 18
    ("Ciprofloxacin", 18, False),
    ("Tetracycline", 6, True),         # tooth staining: under 8
    ("Tetracycline", 12, False),       # from 8 years an ordinary agent
    ("Doxycycline", 5, False),         # AAP Red Book 2024: short courses at any age
    ("Amikacin", 3, False),
])
def test_child_rule(name, age_years, banned):
    out = apply(age.rule_child, context(age=age_years), drug(name))
    assert (out.banned is not None) == banned
    if banned:
        assert out.banned["category"] == "child"


def test_neonate_ceftriaxone_is_banned_and_unknown_months_is_a_caution():
    newborn = apply(age.rule_neonate, context(age=0, age_months=0), drug("Ceftriaxone"))
    assert newborn.banned["category"] == "neonate"
    unknown = apply(age.rule_neonate, context(age=0, age_months=None), drug("Ceftriaxone"))
    assert unknown.banned is None and unknown.primary["warning_reason"] == "neonate"
    adult = apply(age.rule_neonate, context(age=30), drug("Ceftriaxone"))
    assert adult.banned is None and adult.primary is None


# ── pregnancy ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["Doxycycline", "Tetracycline", "Tigecycline", "Clarithromycin"])
def test_pregnancy_absolute_contraindications(name):
    out = apply(pregnancy.rule_pregnancy, context(sex="Female", is_preg=True), drug(name))
    assert out.banned["category"] == "pregnancy"


def test_pregnancy_caution_is_recorded_not_final():
    out = apply(pregnancy.rule_pregnancy, context(sex="Female", is_preg=True), drug("Gentamicin"))
    assert out.banned is None and out.preg_item["name"] == "Gentamicin"
    assert out.preg_item.get("preg_note")


def test_pregnancy_rule_is_silent_when_not_pregnant_or_safe():
    assert apply(pregnancy.rule_pregnancy, context(sex="Female"), drug("Doxycycline")).banned is None
    safe = apply(pregnancy.rule_pregnancy, context(sex="Female", is_preg=True), drug("Cephalexin"))
    assert safe.banned is None and safe.preg_item is None


# ── host: hepatic / renal / intermediate ────────────────────────────────────
def test_hepatic_avoid_bans():
    cx = context(is_hepatic=True, child_pugh="C")
    assert apply(host.rule_hepatic, cx, drug("Nitrofurantoin")).banned["category"] == "hepatic"


def test_hepatic_adjustment_is_a_caution():
    cx = context(is_hepatic=True, child_pugh="C")
    out = apply(host.rule_hepatic, cx, drug("Ceftriaxone"))
    assert out.primary["warning_reason"] == "hepatic_adjustment" and out.primary["hepatic_level"]


@pytest.mark.parametrize("grade", ["", None, "x", "D", "  "])
def test_unknown_child_pugh_fails_closed_to_grade_c(grade):
    cx = context(is_hepatic=True, child_pugh=grade)
    assert apply(host.rule_hepatic, cx, drug("Nitrofurantoin")).banned is not None


def test_hepatic_fact_is_added_to_an_existing_caution_not_dropped():
    cx = context(is_hepatic=True, child_pugh="C")
    out = Outcome({})
    out.caution({"name": "Ceftriaxone", "warning_reason": "possible_mrsa"})
    apply(host.rule_hepatic, cx, drug("Ceftriaxone"), out)
    assert out.primary["warning_reason"] == "possible_mrsa"          # reason unchanged
    assert out.primary["hepatic_level"] and any("Hepatic" in x for x in out.extra)


def test_hepatic_fact_travels_with_a_pregnancy_caution():
    cx = context(sex="Female", is_preg=True, is_hepatic=True, child_pugh="C")
    out = Outcome({})
    out.preg_item = {"name": "Ceftriaxone", "preg_note": "x"}
    apply(host.rule_hepatic, cx, drug("Ceftriaxone"), out)
    assert out.primary is None and any("Hepatic" in x for x in out.preg_extra)


def test_renal_adjustment_only_when_flagged_and_below_the_limit():
    d = drug("Cefixime")                                             # renal_limit 60
    assert apply(host.rule_renal_adjustment, context(is_renal=True, cl_cr=20), d).primary[
        "warning_reason"] == "renal_adjustment"
    assert apply(host.rule_renal_adjustment, context(is_renal=True, cl_cr=90), d).primary is None
    assert apply(host.rule_renal_adjustment, context(is_renal=False, cl_cr=20), d).primary is None


def test_renal_flag_without_a_creatinine_is_not_read_as_normal():
    out = apply(host.rule_renal_adjustment, context(is_renal=True, cl_cr=None), drug("Cefixime"))
    assert out.primary is not None and out.primary["crcl_measured"] is False


def test_intermediate_is_a_caution_unless_one_already_exists():
    cx = context(sir={"Ciprofloxacin": "I"})
    assert apply(host.rule_intermediate, cx, drug("Ciprofloxacin", "I")).primary[
        "warning_reason"] == "intermediate_culture"
    out = Outcome({})
    out.caution({"name": "Ciprofloxacin", "warning_reason": "renal_adjustment"})
    apply(host.rule_intermediate, cx, drug("Ciprofloxacin", "I"), out)
    assert out.primary["warning_reason"] == "renal_adjustment" and not out.secondary


# ── organism ────────────────────────────────────────────────────────────────
def test_mrsa_bans_beta_lactams_but_not_ceftaroline():
    cx = context("Staphylococcus aureus", "Blood", {"Oxacillin": "R", "Cefazolin": "S", "Ceftaroline": "S"})
    assert cx.is_mrsa
    assert apply(organism.rule_mrsa, cx, drug("Cefazolin")).banned is not None
    assert apply(organism.rule_mrsa, cx, drug("Ceftaroline")).banned is None
    assert apply(organism.rule_mrsa, cx, drug("Vancomycin")).banned is None


def test_intrinsic_resistance_bans_whatever_the_disk_says():
    cx = context("Pseudomonas aeruginosa", "Sputum", {"Ceftriaxone": "S"})
    assert apply(organism.rule_intrinsic, cx, drug("Ceftriaxone")).banned["category"] == "organism"


def test_enterococcus_fluoroquinolone_is_urinary_only():
    blood = context("Enterococcus faecalis", "Blood", {"Ciprofloxacin": "S"})
    urine = context("Enterococcus faecalis", "Urine", {"Ciprofloxacin": "S"})
    assert apply(organism.rule_enterococci, blood, drug("Ciprofloxacin")).banned is not None
    assert apply(organism.rule_enterococci, urine, drug("Ciprofloxacin")).banned is None


def test_erythromycin_r_predicts_the_other_macrolides():
    cx = context("Streptococcus pyogenes", "Throat Swab", {"Erythromycin": "R", "Azithromycin": "S"})
    assert apply(organism.rule_macrolide_cross_resistance, cx, drug("Azithromycin")).banned is not None


# ── mechanism ───────────────────────────────────────────────────────────────
ESBL = {"Ceftriaxone": "R", "Cefotaxime": "R", "Ceftazidime": "R", "Piperacillin + Tazobactam": "S",
        "Cefepime": "S", "Meropenem": "S"}


def test_esbl_piptazo_is_banned_in_blood_and_cautioned_in_cystitis():
    blood, urine = context("E. coli", "Blood", ESBL), context("E. coli", "Urine", ESBL)
    assert blood.is_esbl_like and urine.is_esbl_like
    assert apply(mechanism.rule_esbl_or_carbapenemase_bli, blood, drug("Piperacillin + Tazobactam")).banned
    out = apply(mechanism.rule_esbl_or_carbapenemase_bli, urine, drug("Piperacillin + Tazobactam"))
    assert out.banned is None and out.primary["warning_reason"] == "esbl_bli_uti_only"


def test_esbl_cefepime_has_one_verdict_only():
    urine = context("E. coli", "Urine", ESBL)
    out = apply(mechanism.rule_esbl_cefepime, urine, drug("Cefepime"))
    assert out.primary is not None and out.skip_mech is True
    apply(mechanism.rule_esbl_or_carbapenemase_betalactam, urine, drug("Cefepime"), out)
    assert not out.secondary


def test_confirmed_carbapenemase_bans_a_carbapenem_that_tests_s():
    cx = context("Klebsiella spp.", "Blood", {"Ertapenem": "R", "Imipenem/Cilastatin": "R", "Meropenem": "S"})
    assert cx.is_carbapenemase
    assert apply(mechanism.rule_carbapenemase_carbapenem, cx, drug("Meropenem")).banned is not None


def test_a_single_carbapenem_r_is_a_suspicion_not_a_lockdown():
    cx = context("Klebsiella spp.", "Blood", {"Ertapenem": "R", "Meropenem": "S", "Ceftriaxone": "S"})
    assert cx.is_possible_carb and not cx.is_carbapenemase
    out = apply(mechanism.rule_possible_carbapenemase_betalactam, cx, drug("Ceftriaxone"))
    assert out.banned is None and out.primary["warning_reason"] == "possible_carbapenemase"


# ── single-agent rules ──────────────────────────────────────────────────────
def test_nitrofurantoin_renal_threshold():
    low = context(is_renal=True, cl_cr=30)
    assert apply(specific.rule_nitrofurantoin_renal, low, drug("Nitrofurantoin")).banned["category"] == "renal"
    ok = context(is_renal=True, cl_cr=60)
    assert apply(specific.rule_nitrofurantoin_renal, ok, drug("Nitrofurantoin")).banned is None


def test_enterococcus_tmp_smx_is_never_relied_on():
    cx = context("Enterococcus faecalis", "Urine", {"Trimethoprim/Sulfamethoxazole": "S"})
    assert apply(specific.rule_enterococcus_tmp_smx, cx, drug("Trimethoprim/Sulfamethoxazole")).banned


# ── novel beta-lactam agents are Gram-negative agents ───────────────────────
def test_novel_agents_have_no_role_against_any_gram_positive_on_the_pick_list():
    """Regression: 'Gram-positive cocci (unidentified)' was missed by the Gram-positive
    gate and the reserve Gram-negative agents were offered for it."""
    from cdss.common.catalog import BACTERIA_TYPES
    from cdss.therapy.therapy_rules import NOVEL_BL_AGENTS, novel_agent_verdict
    gram_positive = [b for b in BACTERIA_TYPES if any(
        k in b.lower() for k in ("staph", "strep", "enterococc", "listeria", "mrsa", "vre",
                                 "gram-positive"))]
    assert "Gram-positive cocci (unidentified)" in gram_positive and len(gram_positive) >= 15
    for org in gram_positive:
        for agent in NOVEL_BL_AGENTS:
            verdict, _note = novel_agent_verdict(agent, org, {}, None, {agent: "S"})
            assert verdict == "ban", f"{agent} vs {org}: {verdict}"


# ── phenotypes stated by the organism name ──────────────────────────────────
def test_organism_reported_as_mrsa_or_vre_gets_its_phenotype_card():
    """'MRSA' and 'VRE' are pick-list names; the card must not depend on the marker
    drug happening to be on the panel."""
    from cdss.resistance.phenotypes import detect_resistance_phenotypes as detect
    names = lambda org, sir: [p["phenotype"] for p in detect(org, sir)]      # noqa: E731
    assert "MRSA" in names("MRSA", {"Vancomycin": "S"})
    assert "VRE" in names("VRE", {"Linezolid": "S"})
    assert names("MRSA", {"Oxacillin": "R"}).count("MRSA") == 1               # not doubled
    # a marker reported S contradicts the name: not asserted, left to QC
    assert "MRSA" not in names("MRSA", {"Oxacillin": "S"})
    assert "VRE" not in names("VRE", {"Vancomycin": "S"})
    # and the name must be the WORD, not a substring
    assert "MRSA" not in names("Staphylococcus aureus", {"Vancomycin": "S"})
