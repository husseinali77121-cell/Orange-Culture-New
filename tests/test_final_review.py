"""v6.6 — the defects found in the final clinical review (2026-11-13), each as a test.

Every case runs through run_analysis(), the path the clinician walks.
"""
import re

import pytest

from cdss.common.clinical_utils import Patient
from cdss.formulary.abx_guidelines import ABX_GUIDELINES, validate_abx_guidelines
from cdss.pipeline import run_analysis
from cdss.resistance.mdr import classify_mdr, mdr_display_label
from cdss.astqc.ast_consistency import check_consistency
from cdss.stewardship.combination import get_combination_therapy
from cdss.resistance.phenotypes import detect_resistance_phenotypes

ADULT = Patient(age_years=45, sex="Female")

ESBL = {"Ampicillin": "R", "Amoxicillin + Clavulanic acid": "R", "Cefuroxime": "R",
        "Ceftriaxone": "R", "Ceftazidime": "R", "Cefepime": "R", "Cefoxitin": "S",
        "Piperacillin + Tazobactam": "S", "Ertapenem": "S", "Meropenem": "S",
        "Imipenem/Cilastatin": "S", "Ciprofloxacin": "S", "Levofloxacin": "S",
        "Trimethoprim/Sulfamethoxazole": "S", "Gentamicin": "S", "Amikacin": "S",
        "Nitrofurantoin": "S", "Fosfomycin": "S"}
MRSA = {"Penicillin": "R", "Oxacillin": "R", "Cefoxitin": "R", "Vancomycin": "S",
        "Linezolid": "S", "Daptomycin": "S", "Trimethoprim/Sulfamethoxazole": "S",
        "Clindamycin": "S", "Erythromycin": "S", "Doxycycline": "S", "Gentamicin": "S"}


def ranked(org, spec, sir, **kw):
    return [d["name"] for d in run_analysis(ADULT, org, spec, sir, **kw)["ranked"]]


# ── 1. the ranked list follows the guideline for the mechanism and site ─────
def test_esbl_bacteraemia_starts_with_a_carbapenem_and_steps_down_orally():
    r = ranked("E. coli", "Blood", ESBL)
    assert r[:3] == ["Meropenem", "Imipenem/Cilastatin", "Ertapenem"]
    assert r.index("Ciprofloxacin") > 2 and r.index("Trimethoprim/Sulfamethoxazole") > 2


def test_esbl_cystitis_and_pyelonephritis_follow_idsa_2026():
    assert ranked("E. coli", "Urine", ESBL, uti_syndrome="lower")[0] == "Nitrofurantoin"
    upper = ranked("E. coli", "Urine", ESBL, uti_syndrome="upper")
    assert upper[:3] == ["Trimethoprim/Sulfamethoxazole", "Ciprofloxacin", "Levofloxacin"]
    assert "Nitrofurantoin" not in upper


def test_mrsa_pneumonia_and_bacteraemia():
    assert ranked("Staphylococcus aureus", "Sputum", MRSA)[:2] == ["Vancomycin", "Linezolid"]
    assert ranked("Staphylococcus aureus", "Blood", MRSA)[:2] == ["Vancomycin", "Daptomycin"]


def test_mrsa_abscess_keeps_access_oral_agents_ahead_of_reserve():
    r = ranked("Staphylococcus aureus", "Pus", MRSA)
    assert r.index("Daptomycin") > r.index("Doxycycline")
    assert r.index("Daptomycin") > r.index("Trimethoprim/Sulfamethoxazole")


def test_strep_pyogenes_wound_amoxicillin_before_vancomycin():
    r = ranked("Streptococcus pyogenes (Group A)", "Wound Swab",
               {"Penicillin": "S", "Amoxicillin": "S", "Vancomycin": "S", "Clindamycin": "S"})
    assert r.index("Amoxicillin") < r.index("Vancomycin")


def test_ampc_organism_bacteraemia_starts_with_cefepime():
    r = ranked("Enterobacter cloacae", "Blood",
               {"Ceftriaxone": "S", "Cefepime": "S", "Meropenem": "S",
                "Ciprofloxacin": "S", "Trimethoprim/Sulfamethoxazole": "S"})
    assert r[0] == "Cefepime" and r.index("Ciprofloxacin") > r.index("Meropenem")


CRE = {"Ceftriaxone": "R", "Ceftazidime": "R", "Cefepime": "R", "Ertapenem": "R",
       "Meropenem": "R", "Imipenem/Cilastatin": "R", "Ceftazidime + Avibactam": "S",
       "Meropenem + Vaborbactam": "S", "Imipenem + Relebactam": "S"}


def test_kpc_order_is_idsa_2026():
    assert ranked("Klebsiella spp.", "Blood", CRE, carbapenemase_type="KPC")[:3] == [
        "Meropenem + Vaborbactam", "Ceftazidime + Avibactam", "Imipenem + Relebactam"]
    combo = get_combination_therapy(detect_resistance_phenotypes("Klebsiella spp.", CRE),
                                    organism="Klebsiella spp.", carbapenemase_type="KPC")
    cre = next(c for c in combo if c["phenotype"] == "CRE")
    assert cre["data"]["options"][0]["combo"].startswith("Meropenem-Vaborbactam")


def test_dtr_pseudomonas_pneumonia_ceftolozane_first():
    sir = {d: "R" for d in ("Piperacillin + Tazobactam", "Ceftazidime", "Cefepime", "Aztreonam",
                            "Meropenem", "Imipenem/Cilastatin", "Ciprofloxacin", "Levofloxacin")}
    sir.update({"Ceftolozane + Tazobactam": "S", "Ceftazidime + Avibactam": "S",
                "Imipenem + Relebactam": "S"})
    assert ranked("Pseudomonas aeruginosa", "Sputum", sir)[0] == "Ceftolozane + Tazobactam"


def test_crab_sulbactam_durlobactam_first():
    sir = {"Meropenem": "R", "Imipenem/Cilastatin": "R", "Ampicillin/Sulbactam": "R",
           "Sulbactam + Durlobactam": "S", "Minocycline": "S"}
    assert ranked("Acinetobacter baumannii", "Sputum", sir)[0] == "Sulbactam + Durlobactam"


def test_the_pdf_first_line_is_the_guideline_choice():
    from cdss.reports.report_service import generate_pdf_html_report
    r = run_analysis(ADULT, "E. coli", "Blood", ESBL)
    html = generate_pdf_html_report(
        patient_name="T", age=45, sex="Female", weight=70, cl_cr=95, is_renal=False,
        is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
        banned=r["banned"], preg_warn_items=r["preg_warn"], organism="E. coli",
        specimen="Blood", sir_map=ESBL, interactions=r["interactions"],
        mdr_result=r["mdr"], esbl_result=r["mechanism"], phenotypes=r["phenotypes"],
        return_html=True, lang="en") or ""
    text = re.sub(r"<[^>]+>", " ", html)
    first, _, rest = text.partition("ALTERNATIVE")
    assert "FIRST-LINE" in first and "Meropenem" in first
    assert "Trimethoprim/Sulfamethoxazole" not in first


# ── 2. a dose note is not a reason to drop the drug of choice ───────────────
def test_listeria_meningitis_ampicillin_recommended_vancomycin_not():
    r = run_analysis(ADULT, "Listeria monocytogenes", "CSF",
                     {"Ampicillin": "S", "Penicillin": "S", "Trimethoprim/Sulfamethoxazole": "S",
                      "Meropenem": "S", "Vancomycin": "S"})
    allowed = {d["name"]: d for d in r["allowed"]}
    assert "Ampicillin" in allowed and allowed["Ampicillin"].get("gate_dose_note")
    assert "Vancomycin" in {d["name"] for d in r["banned"]}
    assert r["ranked"][0]["name"] in ("Penicillin", "Ampicillin")


def test_mssa_meningitis_oxacillin_first():
    r = run_analysis(ADULT, "Staphylococcus aureus", "CSF",
                     {"Penicillin": "R", "Oxacillin": "S", "Cefoxitin": "S", "Vancomycin": "S"})
    assert r["ranked"][0]["name"] == "Oxacillin"


def test_a_dose_note_does_not_hide_a_real_caution():
    # Ampicillin/Sulbactam in CSF is a genuine caution (limited data) and stays one.
    r = run_analysis(ADULT, "Acinetobacter baumannii", "CSF", {"Ampicillin/Sulbactam": "S"})
    assert "Ampicillin/Sulbactam" in {d["name"] for d in r["warned"]}


# ── 3. screening surrogates are not treatment options ───────────────────────
def test_cefoxitin_is_never_offered_for_staphylococci():
    for org in ("Staphylococcus aureus", "Coagulase-negative Staphylococci", "Staphylococcus spp."):
        r = run_analysis(ADULT, org, "Blood", {"Oxacillin": "S", "Cefoxitin": "S", "Cefazolin": "S"})
        assert "Cefoxitin" not in {d["name"] for d in r["allowed"] + r["warned"]}, org


def test_cefoxitin_still_offered_where_it_is_a_drug():
    r = run_analysis(ADULT, "E. coli", "Wound Swab", {"Cefoxitin": "S"})
    assert "Cefoxitin" in {d["name"] for d in r["allowed"] + r["warned"]}


# ── 4. AST QC ───────────────────────────────────────────────────────────────
def _ids(org, sir):
    return {i["id"].split(":")[0] for i in check_consistency(org, sir)}


def test_qc_new_contradictions():
    assert "hier_van_vs_tei_enterococcus" in _ids("Enterococcus faecium",
                                                 {"Vancomycin": "S", "Teicoplanin": "R"})
    assert "hier_van_vs_tei_enterococcus" not in _ids("Enterococcus faecium",
                                                     {"Vancomycin": "R", "Teicoplanin": "S"})
    assert "hier_pen_vs_cro_pneumococcus" in _ids("Streptococcus pneumoniae",
                                                 {"Penicillin": "S", "Ceftriaxone": "R"})
    assert not _ids("Streptococcus pneumoniae", {"Penicillin": "R", "Ceftriaxone": "S"})


def test_qc_unusual_ceftazidime_avibactam_pattern_is_a_warning():
    iss = [i for i in check_consistency("Klebsiella spp.",
                                        {"Ceftazidime + Avibactam": "R", "Meropenem": "S"})
           if i["id"].startswith("unusual_czav")]
    assert iss and iss[0]["severity"] == "warning"
    assert not [i for i in check_consistency("Klebsiella spp.",
                                             {"Ceftazidime + Avibactam": "R", "Meropenem": "R",
                                              "Meropenem + Vaborbactam": "S"})
                if i["id"].startswith("unusual_czav")]


# ── 5. WHO AWaRe ────────────────────────────────────────────────────────────
def test_cefoperazone_sulbactam_is_who_not_recommended():
    assert ABX_GUIDELINES["Cefoperazone + Sulbactam"]["aware"] == "Not Recommended"
    assert ABX_GUIDELINES["Cefoperazone"]["aware"] == "Watch"
    assert not [i for i in validate_abx_guidelines() if "invalid AWaRe" in i]


# ── 6. MDR / XDR / PDR ──────────────────────────────────────────────────────
def test_xdr_with_untested_categories_is_possible_xdr():
    kpc = {"Amoxicillin + Clavulanic acid": "R", "Cefuroxime": "R", "Ceftriaxone": "R",
           "Ceftazidime": "R", "Cefepime": "R", "Piperacillin + Tazobactam": "R",
           "Ertapenem": "R", "Meropenem": "R", "Imipenem/Cilastatin": "R",
           "Ciprofloxacin": "R", "Trimethoprim/Sulfamethoxazole": "R", "Gentamicin": "R",
           "Amikacin": "S", "Colistin": "S", "Tigecycline": "S"}
    m = classify_mdr("Klebsiella spp.", kpc)
    assert m["level"] == "XDR" and m["provisional"]
    assert "Monobactams" in m["untested_categories"]
    assert mdr_display_label(m).startswith("Possible XDR")


def test_acinetobacter_uses_magiorakos_table_5():
    crab = {"Ampicillin/Sulbactam": "R", "Piperacillin + Tazobactam": "R", "Ceftazidime": "R",
            "Cefepime": "R", "Meropenem": "R", "Imipenem/Cilastatin": "R",
            "Ciprofloxacin": "R", "Levofloxacin": "R", "Trimethoprim/Sulfamethoxazole": "R",
            "Gentamicin": "R", "Amikacin": "R", "Colistin": "S", "Minocycline": "S",
            "Tigecycline": "S"}
    m = classify_mdr("Acinetobacter baumannii", crab)
    assert "Glycylcyclines" not in m["resistant_categories"] + m["susceptible_categories"]
    assert m["level"] == "XDR" and not m["provisional"]
    assert mdr_display_label(m).startswith("XDR")


def test_pseudomonas_fosfomycin_does_not_make_xdr_provisional():
    dtr = {d: "R" for d in ("Piperacillin + Tazobactam", "Ceftazidime", "Cefepime", "Aztreonam",
                            "Meropenem", "Imipenem/Cilastatin", "Ciprofloxacin", "Levofloxacin",
                            "Tobramycin")}
    dtr.update({"Amikacin": "S", "Colistin": "S"})
    m = classify_mdr("Pseudomonas aeruginosa", dtr)
    assert m["level"] == "XDR" and not m["provisional"], m["untested_categories"]


# ── 7. found by the independent check of these fixes ────────────────────────
def test_cre_pyelonephritis_oral_agents_before_reserve():
    sir = dict(CRE, **{"Trimethoprim/Sulfamethoxazole": "S", "Ciprofloxacin": "S"})
    r = ranked("Klebsiella spp.", "Urine", sir, carbapenemase_type="KPC", uti_syndrome="upper")
    assert r[:2] == ["Trimethoprim/Sulfamethoxazole", "Ciprofloxacin"]
    assert r.index("Meropenem + Vaborbactam") < r.index("Ceftazidime + Avibactam")


def test_meningitis_third_generation_cephalosporin_before_tmp_smx():
    r = ranked("Klebsiella spp.", "CSF", {"Trimethoprim/Sulfamethoxazole": "S", "Ceftriaxone": "S",
                                         "Cefepime": "S", "Meropenem": "S"})
    assert r[0] == "Ceftriaxone"
    r = ranked("Streptococcus pneumoniae", "Blood", {"Penicillin": "S", "Ceftriaxone": "S",
                                                     "Trimethoprim/Sulfamethoxazole": "S"})
    assert r.index("Ceftriaxone") < r.index("Trimethoprim/Sulfamethoxazole")


def test_penicillin_is_shown_iv_for_csf():
    from cdss.stewardship.ranking import route_label
    pen = dict(ABX_GUIDELINES["Penicillin"], name="Penicillin")
    assert route_label(pen, "CSF") == "IV" and route_label(pen, "Wound Swab") == "PO"


def test_superficial_sites_keep_the_stewardship_order():
    assert ranked("E. coli", "Wound Swab", ESBL)[0] == "Trimethoprim/Sulfamethoxazole"
    assert ranked("Enterobacter cloacae", "Wound Swab",
                  {"Cefepime": "S", "Trimethoprim/Sulfamethoxazole": "S"})[0] == \
        "Trimethoprim/Sulfamethoxazole"
    assert ranked("Staphylococcus aureus", "Throat swab", MRSA)[0] != "Vancomycin"


def test_daptomycin_not_offered_under_12_months():
    infant = Patient(age_years=0, age_months=6, sex="Male")
    r = run_analysis(infant, "Staphylococcus aureus", "Blood", MRSA)
    assert "Daptomycin" in {d["name"] for d in r["banned"]}
    card = next(c for c in r["combinations"] if c["phenotype"] == "MRSA")
    dap = [o for o in card["data"]["options"] if "daptomycin" in o["combo"].lower()]
    assert dap and all("12" in o.get("caution", "") for o in dap)


def test_reports_say_possible_xdr_and_print_the_dose_note():
    from cdss.reports.report_service import generate_pdf_html_report, generate_report
    sir = {"Amoxicillin + Clavulanic acid": "R", "Cefuroxime": "R", "Ceftriaxone": "R",
           "Ceftazidime": "R", "Cefepime": "R", "Piperacillin + Tazobactam": "R",
           "Ertapenem": "R", "Meropenem": "R", "Imipenem/Cilastatin": "R",
           "Ciprofloxacin": "R", "Trimethoprim/Sulfamethoxazole": "R", "Gentamicin": "R",
           "Amikacin": "S", "Colistin": "S", "Tigecycline": "S"}
    r = run_analysis(ADULT, "Klebsiella spp.", "Blood", sir)
    html = generate_pdf_html_report(
        patient_name="T", age=45, sex="Female", weight=70, cl_cr=95, is_renal=False,
        is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
        banned=r["banned"], preg_warn_items=r["preg_warn"], organism="Klebsiella spp.",
        specimen="Blood", sir_map=sir, interactions=r["interactions"], mdr_result=r["mdr"],
        esbl_result=r["mechanism"], phenotypes=r["phenotypes"], return_html=True, lang="en") or ""
    assert "possible XDR" in html and "Possible XDR" in html
    lis = {"Ampicillin": "S", "Penicillin": "S"}
    r = run_analysis(ADULT, "Listeria monocytogenes", "CSF", lis)
    txt = generate_report("T", 45, "Female", 70, 95, False, False, False, r["allowed"], r["warned"],
                          r["banned"], r["preg_warn"], "Listeria monocytogenes", "CSF",
                          r["interactions"], lis)
    assert "Dose      : [site] high-dose IV" in txt


def test_qc_refinements():
    iss = [i for i in check_consistency("Klebsiella spp.",
                                        {"Ceftazidime + Avibactam": "R", "Meropenem": "S"})
           if i["id"].startswith("unusual_czav")]
    assert "MBL" in iss[0]["reason_en"] or "metallo" in iss[0]["reason_en"]
    assert "hier_pen_vs_cro_pneumococcus" not in _ids(
        "Streptococcus pneumoniae", {"Penicillin (non-meningitis)": "S", "Ceftriaxone": "R"})
