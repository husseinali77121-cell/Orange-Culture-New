"""v7.9 (2026-11-21): external review of a real case run on v7.8.

The case: Klebsiella spp. >= 10^5 CFU/mL, urine from a suprapubic catheter,
30-year-old woman with tetraplegia; "autonomic dysreflexia, new" entered on the
strength of sweating above the injury level. Panel exactly as the laboratory
reported it (Orange Lab, 15-Nov-2026): ofloxacin, pip-tazo, gentamicin,
aztreonam S; cefepime, doxycycline, amikacin, norfloxacin, ertapenem I
("Moderate"); nitrofurantoin, amox-clav, cephradine, tetracycline, cefaclor,
TMP-SMX, cefuroxime, cefoperazone, cephalexin R.

Every point was checked against the code before it was changed; each test
fails on v7.8. What it pins:
  * MDR vs XDR: one level in every report -- MDR established, XDR "not
    confirmed" (4 Magiorakos categories untested). The QA sheet printed XDR.
  * Carbapenem I triggers a carbapenemase test; it is not "a carbapenemase
    until proven otherwise". The advisory note for ertapenem I says so.
  * Cefepime "I" (CLSI has no I) is marked unverified in the MDR count, and
    the level is shown not to rest on it.
  * Autonomic dysreflexia entered on sweating alone is "possible" with
    moderate confidence; confirmed (BP rise) counts; explained by another
    trigger does not count. The emergency management line comes first.
  * The catheter sampling site is asked; bag / skin-site urine is rejected.
  * Ofloxacin S keeps its S in the image; the quinolone note is a
    possibility, not a gyrA mutation.
  * Gentamicin is a potential option, not "best available" / "PRIMARY".
  * Fosfomycin is not "missing" for Klebsiella (no CLSI breakpoint).
  * Klebsiella identified to genus only is flagged (K. aerogenes AmpC).
"""
from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.astqc.ast_panel_completeness import check_panel_completeness  # noqa: E402
from cdss.astqc.confidence import compute_qa_confidence  # noqa: E402
from cdss.astqc.inline_qc import run_ast_qc  # noqa: E402
from cdss.astqc.phenotype_plausibility import check_plausibility  # noqa: E402
from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.organisms.pathogenicity import (AD_ASSESSMENT_OPTIONS, CATHETER_SAMPLE_SITES,  # noqa: E402
                                          HOST_SCI_QUAD, SYMPTOM_COURSE_OPTIONS,
                                          assess_pathogenicity, treatment_gate)
from cdss.pipeline import run_analysis  # noqa: E402
from cdss.reports.qa_pdf import generate_qa_report_pdf  # noqa: E402
from cdss.reports.report_service import generate_pdf_html_report, generate_report  # noqa: E402
from cdss.reports.html_utils import caution_label, top_option_line  # noqa: E402
from cdss.resistance.mdr import classify_mdr  # noqa: E402
from cdss.resistance.esbl_status import (mdr_heading, mdr_without_unverified,  # noqa: E402
                                        mdr_xdr_note, unverified_results)

S, I, R = "S", "I", "R"
ORG, SPC = "Klebsiella spp.", "Suprapubic catheter"
PANEL = {"Ofloxacin": S, "Piperacillin + Tazobactam": S, "Gentamicin": S, "Aztreonam": S,
         "Cefepime": I, "Doxycycline": I, "Amikacin": I, "Norfloxacin": I, "Ertapenem": I,
         "Nitrofurantoin": R, "Amoxicillin + Clavulanic acid": R, "Cephradine": R, "Tetracycline": R,
         "Cefaclor": R, "Trimethoprim/Sulfamethoxazole": R, "Cefuroxime sodium": R,
         "Cefoperazone": R, "Cephalexin": R}
AD = ["Autonomic dysreflexia (SCI)"]
NOT_SET, NEW, _BASE = SYMPTOM_COURSE_OPTIONS
AD_NOT_SET, AD_CONFIRMED, AD_SUSPECTED, AD_OTHER = AD_ASSESSMENT_OPTIONS
SITE_NOT_SET, PORT, FRESH, BAG, SKIN = CATHETER_SAMPLE_SITES


def _txt(h) -> str:
    h = h.decode() if isinstance(h, bytes) else h
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)))


def _patho(sym=AD, course=NEW, **kw):
    return assess_pathogenicity("Urine", ORG, "≥ 10^5 CFU/mL", "Pure growth", sym, "40 - 50",
                                "Pyuria (WBCs > 5/HPF)", "WBCs + Gram Negative Bacilli", 30, "Female",
                                [HOST_SCI_QUAD], collection_method=kw.pop("coll", SPC),
                                symptom_course=course, **kw)


def _run(patho=None):
    pt = Patient(age_years=30, sex="Female", collection_method=SPC, host_factors=[HOST_SCI_QUAD])
    return run_analysis(pt, ORG, "Urine", dict(PANEL), pathogenicity=patho)


def _qa():
    qc = run_ast_qc(ORG, dict(PANEL), specimen="Urine")
    return qc, _txt(generate_qa_report_pdf(ORG, "Urine", dict(PANEL), qc,
                                           compute_qa_confidence(qc, dict(PANEL), ORG),
                                           return_html=True))


def _pdf(r, p=None):
    return _txt(generate_pdf_html_report(
        patient_name="X", age=30, sex="Female", weight=None, cl_cr=None, is_renal=False, is_preg=False,
        is_hepatic=False, allowed=r["allowed"], warned=r["warned"], banned=r["banned"],
        preg_warn_items=r["preg_warn"], organism=ORG, specimen="Urine", sir_map=dict(PANEL),
        interactions=r["interactions"], mdr_result=r["mdr"], esbl_result=r["mechanism"],
        phenotypes=r["phenotypes"], lang="en", return_html=True, case=r["case"],
        patho_assessment=p, treatment_gate=r["treatment_gate"]))


# ── 1. MDR / XDR: one level everywhere ──────────────────────────────────────
def test_the_engine_calls_it_possible_xdr_and_every_report_prints_mdr():
    m = classify_mdr(ORG, PANEL)
    assert (m["level"], m["provisional"], m["resistant_count"], m["total_tested"]) == ("XDR", True, 8, 10)
    assert set(m["untested_categories"]) == {"Cephamycins", "Fosfomycins", "Glycylcyclines", "Polymyxins"}
    assert mdr_heading(m).startswith("MDR — non-susceptible in 8 of 10")
    assert "NOT confirmed" in mdr_xdr_note(m) and "4 Magiorakos categories" in mdr_xdr_note(m)
    _qc, qa = _qa()
    assert "MDR classification: MDR — non-susceptible in 8 of 10" in qa
    assert "XDR: non-susceptible" not in qa and "established level is MDR" in qa
    pdf = _pdf(_run())
    assert "MDR — NS in 8 of 10" in pdf and "XDR pattern in the tested categories, NOT confirmed" in pdf
    r = _run()
    txt = generate_report(patient_name="X", age=30, sex="Female", weight=60, cl_cr=None, is_renal=False,
                          is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
                          banned=r["banned"], preg_warn_items=r["preg_warn"], organism=ORG,
                          specimen="Urine", interactions=r["interactions"], sir_map=dict(PANEL))
    assert "MDR -- Multi-Drug Resistant" in txt and "NOT confirmed" in txt and "Polymyxins" in txt


def test_a_fully_tested_xdr_is_not_softened():
    m = {"level": "XDR", "provisional": False, "resistant_count": 9, "total_tested": 11}
    assert mdr_xdr_note(m) == "" and mdr_heading(m).startswith("XDR —")


def test_cefepime_i_is_marked_unverified_and_the_level_does_not_rest_on_it():
    m = classify_mdr(ORG, PANEL)
    assert unverified_results(ORG, PANEL) == ["Cefepime"]
    assert unverified_results(ORG, PANEL, sdd={"Cefepime"}) == []          # a lab SDD is not "I"
    u = mdr_without_unverified(ORG, PANEL, m, ["Cefepime"])
    assert not u["changed"] and u["categories_resting_on_unverified"] == []
    # cefepime alone in its category: the category rests on it, and that is said
    alone = {k: v for k, v in PANEL.items() if k != "Cefoperazone"}
    u2 = mdr_without_unverified(ORG, alone, classify_mdr(ORG, alone), ["Cefepime"])
    assert u2["categories_resting_on_unverified"] == ["Extended-Sp Cephalosporins"]
    _qc, qa = _qa()
    assert "Cefepime I (unverified)" in qa and "the level stands either way" in qa


# ── 2. Carbapenem non-susceptibility is a trigger, not a diagnosis ──────────
def test_the_qa_finding_no_longer_calls_it_a_carbapenemase():
    pl2 = next(f for f in check_plausibility(ORG, PANEL) if f["id"] == "PL2:ertapenem_ns")
    assert "until proven otherwise" not in pl2["detail_en"]
    assert "does not by itself prove a carbapenemase" in pl2["detail_en"]
    assert "porin loss" in pl2["detail_en"] and "حتى يثبت العكس" not in pl2["detail_ar"]
    assert "eCIM is read only when the mCIM is positive" in pl2["action_en"]


def test_ertapenem_i_gets_the_carbapenem_note_not_the_generic_beta_lactam_text():
    r = _run()
    it = next(i for i in r["warned"] if i["name"] == "Ertapenem")
    en = it["intermediate_note_en"]
    assert "carbapenem non-susceptibility" in en and "Not proof of a carbapenemase" in en
    assert "meropenem MIC" in en and "1 g once daily" in en
    assert "higher-than-normal dose" not in en
    # a carbapenem I in a non-Enterobacterales keeps the general text
    from cdss.therapy.clsi_categories import intermediate_note
    assert "carbapenemase" not in intermediate_note("Meropenem", "Carbapenem (IV)", "blood", False,
                                                    organism="Pseudomonas aeruginosa")[1]


# ── 3. Autonomic dysreflexia ────────────────────────────────────────────────
def test_sweating_only_dysreflexia_is_possible_with_moderate_confidence():
    for ad in (AD_NOT_SET, AD_SUSPECTED):
        p = _patho(ad_assessment=ad)
        assert p["category"] == "POSSIBLE_INFECTION" and p["score"] <= 65, ad
        assert p["confidence"] != "high"
        assert any("Confirm autonomic dysreflexia" in x for x in p["recommendations_en"])
        assert "AD_UNCONFIRMED" in p["special_flags"]


def test_confirmed_dysreflexia_counts_but_is_not_called_proof():
    p = _patho(ad_assessment=AD_CONFIRMED)
    assert p["category"] == "TRUE_INFECTION"
    assert any("supports, but does not prove" in f for f in p["factors_pos"])


def test_dysreflexia_explained_by_another_trigger_is_not_a_uti_symptom():
    p = _patho(ad_assessment=AD_OTHER)
    assert p["category"] in ("ASB_NO_TREAT", "POSSIBLE_INFECTION", "LIKELY_CONTAMINANT")
    assert p["category"] != "TRUE_INFECTION"
    assert any("not attributed to UTI" in f for f in p["factors_neg"])
    # another new SCI symptom still counts
    p2 = _patho(sym=AD + ["Increased spasticity (SCI)"], ad_assessment=AD_OTHER)
    assert any("increased spasticity" in f for f in p2["factors_pos"])


def test_the_emergency_line_comes_first_whatever_the_verdict():
    for ad in AD_ASSESSMENT_OPTIONS:
        p = _patho(ad_assessment=ad)
        assert p["recommendations_en"][0].startswith("🚨 Autonomic dysreflexia is an emergency")
        assert p["recommendations"][0].startswith("🚨")
    assert not any("emergency" in x for x in _patho(sym=["Fever (> 38°C)"])["recommendations_en"])


# ── 4. Catheter sampling site ───────────────────────────────────────────────
@pytest.mark.parametrize("site", [BAG, SKIN])
def test_bag_or_skin_site_urine_is_rejected_and_gates_the_treatment(site):
    p = _patho(ad_assessment=AD_CONFIRMED, catheter_sample_site=site)
    assert p["category"] == "URINE_SPECIMEN_REJECT"
    g = treatment_gate(p)
    assert g and "re-collect" in g["reason_en"].lower()
    assert any("sampling port" in x for x in p["recommendations_en"])


def test_the_sampling_site_is_noted_when_not_given_and_accepted_from_the_port():
    assert any("sampling site not recorded" in n for n in _patho(ad_assessment=AD_CONFIRMED)["notes_en"])
    for site in (PORT, FRESH):
        p = _patho(ad_assessment=AD_CONFIRMED, catheter_sample_site=site)
        assert p["category"] == "TRUE_INFECTION"
        assert not any("not recorded" in n for n in p["notes_en"])
    # a midstream specimen is not asked about a catheter
    p = _patho(coll="Midstream clean-catch", sym=["Dysuria / Frequency / Urgency"])
    assert not any("Catheter sampling site" in n for n in p["notes_en"])


# ── 5. Labels: ofloxacin, ertapenem, cefepime, gentamicin ──────────────────
def test_tree_labels_keep_the_result_and_name_the_pending_test():
    r = _run()
    lab = {i["name"]: caution_label(i, ORG, PANEL) for i in r["warned"]}
    assert lab["Ofloxacin"] == "Ofloxacin (S · confirm by CIP/LEV)"
    assert lab["Ertapenem"] == "Ertapenem (I · carbapenemase test)"
    assert lab["Cefepime"] == "Cefepime (I unverified · MIC)"
    assert lab["Amikacin"] == "Amikacin (I)"
    assert lab["Piperacillin + Tazobactam"] == "Piperacillin + Tazobactam (ESBL not excluded)"
    assert caution_label({"name": "Cefepime", "warning_reason": "intermediate_culture"}, ORG, PANEL,
                         sdd_drugs={"Cefepime"}) == "Cefepime (SDD)"
    assert top_option_line("Gentamicin", "IV").startswith("Potential option: Gentamicin [IV]")
    assert "Best available" not in top_option_line("Gentamicin", "IV")


def test_no_report_states_a_gyra_mutation_or_primary():
    r = _run()
    pdf = _pdf(r, _patho())
    _qc, qa = _qa()
    for t in (pdf, qa):
        assert "gyrA mutation" not in t and "first-step gyrA" not in t
    assert "mechanism not confirmed" in pdf and "mechanism not confirmed" in qa
    assert "POTENTIAL PREFERRED OPTION" in pdf and " PRIMARY " not in f" {pdf} "


# ── 6. Panel completeness and identification ───────────────────────────────
def test_fosfomycin_is_not_missing_for_klebsiella_but_still_is_for_e_coli():
    kp = check_panel_completeness(ORG, "Urine", dict(PANEL))
    assert "Fosfomycin" not in kp.missing_primary + kp.missing_supplemental
    assert "Meropenem" in kp.missing_primary                        # required by ertapenem I
    ec = check_panel_completeness("Escherichia coli", "Urine", {"Ampicillin": "R"})
    assert "Fosfomycin" in ec.missing_supplemental


def test_klebsiella_to_genus_only_is_flagged_and_a_species_is_not():
    ids = {f["id"] for f in check_plausibility(ORG, PANEL)}
    assert "PL5:klebsiella_genus_only" in ids
    for sp in ("Klebsiella pneumoniae", "Klebsiella aerogenes", "Klebsiella oxytoca"):
        assert "PL5:klebsiella_genus_only" not in {f["id"] for f in check_plausibility(sp, PANEL)}
    # no beta-lactam result to read: nothing to flag
    assert not any(f["id"].startswith("PL5") for f in check_plausibility(ORG, {"Gentamicin": "S"}))
    kp = check_panel_completeness(ORG, "Urine", dict(PANEL))
    assert not any("Species" in d for d in kp.missing_primary + kp.missing_supplemental)
