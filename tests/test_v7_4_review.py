"""v7.4 (2026-11-20): the external review of v7.3 and the external review of the E. coli / SCI case.

Every point was checked against the code before it was changed; each test below
fails on v7.3. What it pins:

  Case review (E. coli, lab report "Mid stream urine", app "Foley", paraplegia):
    * the laboratory report's collection method is read (OCR) and a disagreement
      with the entered case is a CRITICAL, release-blocking issue (printed when confirmed);
    * ESBL is "suspected" unless a confirmatory test is entered -- never "ESBL+";
    * MDR names every counted category and the QA sheet shows the calculation;
    * SCI / catheter symptoms count only when new / worse than baseline; pure growth,
      WBCs on the stain and the count weigh less with a catheter / neurogenic bladder;
    * the AST-QA counts reconcile (salt forms fill the same panel slot);
    * treatment options by site carry the isolate's result; no "()" left;
    * the pip-tazo note reads this isolate; TDM does not replace renal assessment;
    * the organism summary is tagged with the isolate's results, one entry per agent.
  Review of v7.3:
    * blood "never a contaminant / start treatment now" reworded;
    * fever / rigors alone = systemic / upper-tract syndrome, not proven pyelonephritis;
    * afebrile 8-60 days is not an AAP rule; capped at "possible";
    * piperacillin / pip-tazo hierarchy limited to groups with both CLSI breakpoints;
    * EUCAST carbapenem rules carry the v16.1 re-check note;
    * whole-case validation engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.astqc.ast_consistency import check_consistency  # noqa: E402
from cdss.astqc.ast_panel_completeness import check_panel_completeness  # noqa: E402
from cdss.astqc.confidence import compute_qa_confidence  # noqa: E402
from cdss.astqc.inline_qc import run_ast_qc  # noqa: E402
from cdss.astqc.reconciliation import mandatory_checks  # noqa: E402
from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.common.data_consistency import (check_case_consistency, collection_group,  # noqa: E402
                                          detect_collection_method)
from cdss.common.drug_names import tag_with_ast  # noqa: E402
from cdss.guidelines.guideline_registry import RULES, SOURCES  # noqa: E402
from cdss.organisms.organism_profile import ORGANISM_PROFILE  # noqa: E402
from cdss.organisms.pathogenicity import SYMPTOM_COURSE_OPTIONS, assess_pathogenicity  # noqa: E402
from cdss.pipeline import run_analysis  # noqa: E402
from cdss.reports.qa_pdf import generate_qa_report_pdf  # noqa: E402
from cdss.reports.report_service import generate_pdf_html_report, generate_report  # noqa: E402
from cdss.resistance.esbl_status import esbl_status  # noqa: E402
from cdss.resistance.mdr import classify_mdr, mdr_breakdown  # noqa: E402
from cdss.stewardship.combination import annotate_with_ast  # noqa: E402
from cdss.therapy.therapy_rules import UTI_SYNDROME_OPTIONS, classify_uti  # noqa: E402
from cdss.validation.case_validator import validate_case  # noqa: E402

S, R = "S", "R"
# The panel of the reviewed case, exactly as the laboratory reported it.
PANEL = {"Nitrofurantoin": S, "Amikacin": S, "Piperacillin + Tazobactam": S, "Doxycycline": S,
         "Cephalexin": S, "Imipenem/Cilastatin": S,
         "Tetracycline": R, "Trimethoprim/Sulfamethoxazole": R, "Amoxicillin + Clavulanic acid": R,
         "Ciprofloxacin": R, "Ofloxacin": R, "Cefuroxime sodium": R, "Ceftriaxone": R, "Cefotaxime": R}
PARA = ["Paraplegia (spinal cord injury)"]
MALAISE = "Malaise / Lethargy / Sense of unease (SCI)"
SYM = [MALAISE, "Cloudy / Foul-smelling urine only"]
FOLEY, MSU = "Indwelling catheter (Foley)", "Midstream clean-catch"
NOT_SET, NEW, BASELINE = SYMPTOM_COURSE_OPTIONS
LAB_TEXT = ("Urine Culture and Sensitivity\nMicroscopic Examination:\n Pus Cells : 40 - 50\n"
            "Culture:\n Sample : Mid stream urine\n Growth : E.coli\n Culture Condition : Aerobic\n"
            " Colony Count : More than 100,000 CFU/mL\n")


def _patho(coll=FOLEY, course="", sym=SYM, host=PARA, **kw):
    return assess_pathogenicity("Urine", "E. coli", "≥ 10^5 CFU/mL", "Pure growth", sym, "40 - 50",
                                "Pyuria (WBCs > 5/HPF)", "WBCs + Gram Negative Bacilli",
                                kw.pop("age", 23), kw.pop("sex", "Female"), host,
                                collection_method=coll, symptom_course=course, **kw)


def _run(coll=FOLEY, report=MSU, confirmed=False, panel=PANEL, **kw):
    pt = Patient(age_years=23, sex="Female", collection_method=coll, host_factors=list(PARA))
    return run_analysis(pt, "E. coli", "Urine", dict(panel), report_collection_method=report,
                        consistency_confirmed=confirmed, pathogenicity=kw.pop("patho", None), **kw)


def _common(r, panel=PANEL):
    return dict(patient_name="X", age=23, sex="Female", weight=60, cl_cr=None, is_renal=False,
                is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
                banned=r["banned"], preg_warn_items=r["preg_warn"], organism="E. coli",
                specimen="Urine", sir_map=panel, interactions=r["interactions"])


def _pdf(r, panel=PANEL, **kw):
    html = generate_pdf_html_report(**_common(r, panel), mdr_result=r["mdr"], esbl_result=r["mechanism"],
                                    phenotypes=r["phenotypes"], combo_suggestions=r["combinations"],
                                    lang="en", return_html=True, case=r["case"],
                                    data_issues=r.get("data_issues"), **kw)
    return html.decode() if isinstance(html, bytes) else html


# ── 1. Laboratory report vs entered case ────────────────────────────────────
def test_the_report_collection_method_is_read_from_the_lab_report():
    assert detect_collection_method(LAB_TEXT) == MSU
    assert detect_collection_method("Specimen: Urine (CSU)") == FOLEY
    assert detect_collection_method("Urine culture") is None


@pytest.mark.parametrize("text,group", [("Mid stream urine", "voided"), ("MSU", "voided"),
                                        ("Foley", "indwelling"), ("CSU", "indwelling"),
                                        ("In-out catheter", "intermittent"), ("Suprapubic aspirate", "spa"),
                                        ("suprapubic catheter", "suprapubic_catheter"), ("مش محدد", None)])
def test_collection_wording_is_grouped(text, group):
    assert collection_group(text) == group


def test_midstream_report_with_foley_entry_is_a_critical_blocking_issue():
    r = _run()
    assert r["data_blocked"] and r["data_issues"][0]["code"] == "SPECIMEN_COLLECTION_MISMATCH"
    assert r["data_issues"][0]["severity"] == "critical"
    assert any(v["id"] == "V10" for v in validate_case(r, specimen="Urine", sir_map=PANEL))


def test_a_confirmed_entry_is_released_and_printed():
    r = _run(confirmed=True)
    assert not r["data_blocked"]
    txt = generate_report(**_common(r), case=r["case"], data_issues=r["data_issues"])
    assert "physician confirmed" in txt and "Midstream clean-catch" in txt
    assert "Data check — physician confirmed" in _pdf(r)


def test_matching_entries_and_a_catheter_host_factor_with_a_voided_specimen():
    assert not _run(coll=MSU)["data_issues"]
    issues = check_case_consistency(specimen="Urine", report_collection=MSU, entered_collection="مش محدد",
                                    host_factors=["Urinary catheter"])
    # v7.5: also "not entered" -- the report states a method the case does not
    assert {i["code"] for i in issues} == {"SPECIMEN_VOIDED_WITH_CATHETER",
                                           "SPECIMEN_COLLECTION_NOT_ENTERED"}
    assert not check_case_consistency(specimen="Blood", report_collection=MSU,
                                      entered_collection=FOLEY)


def test_the_unconfirmed_pdf_says_do_not_release():
    assert "CRITICAL DATA MISMATCH — DO NOT RELEASE" in _pdf(_run())


# ── 2. ESBL: suspected vs confirmed; MDR shown in full ──────────────────────
def test_esbl_is_suspected_without_a_confirmatory_test():
    r = _run(coll=MSU)
    html = _pdf(r)
    assert "ESBL+" not in html and "SUSPECTED ESBL" in html
    assert esbl_status(r["mechanism"])["state"] == "suspected"


def test_a_positive_confirmatory_test_prints_confirmed_and_a_negative_one_says_so():
    r = _run(coll=MSU)
    html = _pdf(r, aux_tests={"ESBL confirmation": "Positive"})
    assert "ESBL CONFIRMED" in html and "SUSPECTED ESBL" not in html
    assert esbl_status(r["mechanism"], {"ESBL confirmation": "Negative"})["state"] == "test_negative"


def test_the_esbl_test_is_a_supplementary_test_not_a_drug():
    pt = Patient(age_years=23, sex="Female", collection_method=MSU)
    r = run_analysis(pt, "E. coli", "Urine", dict(PANEL, **{"ESBL confirmation": "Positive"}))
    assert "ESBL confirmation" not in {i["name"] for b in ("allowed", "warned", "banned") for i in r[b]}


def test_mdr_names_every_counted_category_and_the_qa_sheet_shows_the_count():
    m = classify_mdr("E. coli", PANEL)
    assert (m["level"], m["resistant_count"], m["total_tested"]) == ("MDR", 6, 9)
    rows = mdr_breakdown(m, PANEL)
    assert sum(r["non_susceptible"] for r in rows) == 6 and len(rows) == 9
    html = _pdf(_run(coll=MSU))
    for c in ("3rd/4th-gen cephalosporins", "1st/2nd-gen cephalosporins", "fluoroquinolones",
              "folate-pathway inhibitors", "penicillins+BLI", "tetracyclines"):
        assert c in html, c
    qc = run_ast_qc("E. coli", PANEL, specimen="Urine")
    qa = generate_qa_report_pdf("E. coli", "Urine", PANEL, qc, compute_qa_confidence(qc, PANEL, "E. coli"),
                                return_html=True)
    assert "MDR classification" in qa and "non-susceptible in 6 of 9" in qa


# ── 3. Pathogenicity in spinal cord injury / catheter ───────────────────────
def test_sci_symptoms_unconfirmed_are_possible_not_true_infection():
    p = _patho()
    assert p["category"] == "POSSIBLE_INFECTION" and p["score"] <= 65
    assert "SCI_SYMPTOMS_UNCONFIRMED" in p["special_flags"]
    assert any("NEW / worse than baseline" in r for r in p["recommendations_en"])


def test_new_symptoms_are_infection_and_baseline_ones_are_bacteriuria():
    assert _patho(course=NEW)["category"] == "TRUE_INFECTION"
    assert _patho(course=BASELINE)["category"] == "ASB_NO_TREAT"


def test_the_evidence_lists_only_the_symptoms_entered():
    txt = " ".join(_patho()["factors_pos"]).lower()
    assert "malaise" in txt
    for absent in ("spasticity", "dysreflexia", "leakage"):
        assert absent not in txt, absent


def test_pyuria_stain_and_pure_growth_weigh_less_with_a_catheter_or_neurogenic_bladder():
    ev = {e["domain"]: e for e in _patho(course=NEW)["evidence"]}
    assert ev["purity"]["points"] == 5 and ev["colony_count"]["points"] == 25
    assert ev["gram_stain"]["points"] in (0, 5)
    assert not any("inflammatory cells -- supports infection" in f
                   for f in _patho(course=NEW)["factors_pos"])
    plain = {e["domain"]: e["points"] for e in assess_pathogenicity(
        "Urine", "E. coli", "10^5", "Pure growth", ["Dysuria / Frequency / Urgency"], "40", "", "",
        30, "Female", [], collection_method=MSU)["evidence"]}
    assert plain["purity"] == 10 and plain["colony_count"] == 30


def test_fever_with_a_catheter_and_a_significant_count_is_never_do_not_treat():
    p = assess_pathogenicity("Urine", "MRSA", ">10^5", "Mixed growth", ["Fever (> 38°C)"], ">50", "",
                             "WBCs + Yeast cells", 70, "Male", [], collection_method=FOLEY)
    assert p["score"] >= 45 and p["category"] not in ("LIKELY_CONTAMINANT", "CONTAMINANT_OR_COLONISER")


def test_nidrr_is_quoted_as_a_bacteriuria_definition():
    p = _patho()
    assert "NIDRR" not in p["threshold"]
    assert any("definition of bacteriuria, not a diagnosis of UTI" in n for n in p["notes_en"])


def test_no_factor_is_cut_with_an_ellipsis_in_the_pdf():
    r = _run(coll=MSU, patho=_patho(coll=MSU))
    html = _pdf(r, patho_assessment=_patho(coll=MSU))
    assert "…" not in html.split("Pathogenicity Assessment", 1)[1].split("Treatment options", 1)[0]


# ── 4. AST-QA counts and names ──────────────────────────────────────────────
def test_panel_counts_reconcile_and_a_salt_form_fills_its_slot():
    pc = check_panel_completeness("E. coli", "Urine", PANEL)
    missing = pc.missing_primary + pc.missing_supplemental
    assert (pc.expected_total, pc.tested_count, len(missing), pc.total_tested) == (22, 11, 11, 14)
    assert sorted(pc.extra_tested) == ["Cephalexin", "Doxycycline", "Ofloxacin"]
    assert "Cefuroxime" not in missing and pc.covered_by["Cefuroxime"] == ["Cefuroxime sodium"]
    assert pc.reconciles()


def test_the_qa_sheet_prints_reconciled_counts():
    qc = run_ast_qc("E. coli", PANEL, specimen="Urine")
    html = generate_qa_report_pdf("E. coli", "Urine", PANEL, qc, compute_qa_confidence(qc, PANEL, "E. coli"),
                                  return_html=True)
    assert "Covered <b>11</b>" in html and "Total entered <b>14</b>" in html and "Tested <b>10" not in html


def test_duplicates_are_checked_before_confidence():
    assert not mandatory_checks("E. coli", "Urine", {"Cefuroxime": "I", "Cefuroxime sodium": "S"})
    bad = mandatory_checks("E. coli", "Urine", {"Cefuroxime": "S", "Cefuroxime sodium": "R"})
    assert bad and bad[0]["id"] == "REC-DUP-CONFLICT" and bad[0]["severity"] == "error"
    qc = run_ast_qc("E. coli", {**PANEL, "Cefuroxime": "S"}, specimen="Urine")
    assert compute_qa_confidence(qc, PANEL, "E. coli")["n_errors"] >= 1


# ── 5. Therapy text tied to this isolate ────────────────────────────────────
def test_treatment_options_carry_the_isolate_result_and_no_empty_brackets():
    t = annotate_with_ast("Pyelonephritis / cUTI: TMP-SMX, Ciprofloxacin or Levofloxacin", PANEL)
    assert t == "Pyelonephritis / cUTI: TMP-SMX [R], Ciprofloxacin [R] or Levofloxacin [not tested]"
    from cdss.reports.html_utils import pdf_glyph_guard
    html = pdf_glyph_guard(_pdf(_run(coll=MSU)))
    assert "Combination Therapy — MDR" not in html and "()" not in html
    assert "Meropenem [not tested]" in html and "Imipenem [S]" in html


def test_the_pip_tazo_note_reads_this_isolate_and_the_renal_function():
    r = _run()
    pt = next(i for i in r["warned"] if i["name"] == "Piperacillin + Tazobactam")
    n = pt["esbl_note_en"]
    assert "TMP-SMX R" in n and "Ciprofloxacin R" in n and "Levofloxacin not tested" in n
    assert "adjust to CrCl" in n and "preferred when susceptible" not in n


def test_low_muscle_mass_note_keeps_renal_assessment():
    r = _run(coll=MSU)
    ami = next(i for i in r["allowed"] if i["name"] == "Amikacin")
    assert "cystatin C" in ami["clinical_note_en"] and "remains necessary" in ami["clinical_note_en"]
    assert "not the estimated CrCl" not in ami["clinical_note_en"]


def test_the_pdf_says_what_the_ranking_was_built_for_and_marks_s_tested_avoids():
    html = _pdf(_run())
    assert "Ranked for: complicated UTI" in html and "TMP-SMX R" in html
    assert "Cephalexin</b> <span style=\"color:#1e8449;font-size:8.2pt;font-weight:bold\">S-tested" in html


def test_the_organism_summary_is_tagged_and_lists_each_agent_once():
    tags = tag_with_ast(ORGANISM_PROFILE["E. coli"]["second_line"], PANEL)
    assert "Cefuroxime [R as Cefuroxime sodium]" in tags
    assert not any(t.startswith("Cefuroxime sodium") for t in tags)
    assert "Fosfomycin [not tested]" in tag_with_ast(ORGANISM_PROFILE["E. coli"]["first_line"], PANEL)
    assert "ESBL-producing E. coli فقط" not in ORGANISM_PROFILE["E. coli"]["urine_note"]


def test_the_image_no_longer_calls_the_options_safe():
    src = (ROOT / "cdss" / "reports" / "report_service.py").read_text(encoding="utf-8")
    assert "PREFERRED (SAFE)" not in src and "[:3])}" not in src.split("NS: ")[0][-200:]


# ── 6. Review of v7.3 ───────────────────────────────────────────────────────
def test_blood_wording_is_not_absolute_and_not_an_order():
    p = assess_pathogenicity("Blood", "Staphylococcus aureus", "", "", [], "", "", "", 50, "Male", [])
    txt = " ".join(p["factors_pos"])
    assert "never a contaminant" not in txt and "Start treatment now" not in txt
    assert "presume clinically significant" in txt and p["score"] >= 75


def test_rigors_alone_are_a_systemic_syndrome_not_proven_pyelonephritis():
    uc = classify_uti(UTI_SYNDROME_OPTIONS[0], ["Rigors / Hypotension (sepsis)"])
    assert uc.value == "upper" and uc.basis == "systemic"
    assert classify_uti(UTI_SYNDROME_OPTIONS[0], ["Flank pain / Loin pain"]).basis == "flank"
    assert "جهازية" in UTI_SYNDROME_OPTIONS[2] and "حويضة" in UTI_SYNDROME_OPTIONS[2]


def test_the_afebrile_infant_is_not_an_aap_rule_and_stays_possible():
    p = assess_pathogenicity("Urine", "Escherichia coli", "10^5", "Pure growth", ["Nausea / Vomiting"],
                             "20", "Pyuria (WBCs > 5/HPF)", "", 30 / 365.25, "Male", [],
                             collection_method="Intermittent catheterisation (in-out / CIC)")
    assert "NOT an AAP recommendation" in p["threshold"] and "by analogy" not in p["threshold"]
    assert "INFANT_AFEBRILE_8_60" in p["special_flags"] and p["score"] <= 65
    assert any("not applicable without fever" in r for r in p["references"])


@pytest.mark.parametrize("org,fires", [("Escherichia coli", True), ("Pseudomonas aeruginosa", True),
                                       ("Acinetobacter baumannii", True),
                                       ("Staphylococcus aureus", False), ("Enterococcus faecalis", False)])
def test_pip_vs_pip_tazo_is_limited_to_groups_with_both_breakpoints(org, fires):
    ids = {i.get("id") for i in check_consistency(org, {"Piperacillin": "S",
                                                        "Piperacillin + Tazobactam": "R"})}
    assert any(str(i).startswith("hier_pip_vs_tzp") for i in ids) is fires


def test_the_changed_rule_is_back_in_the_signature_queue():
    row = RULES["hier_pip_vs_tzp"]
    assert "countersigned_by" not in row and "signature_withdrawn" in row
    assert "NOT a clinician countersignature" in row["owner_approved"]


def test_eucast_carbapenem_rules_carry_the_v16_1_recheck_and_the_documents_stay_separate():
    for rid in ("hier_mem_vs_etp", "QC003", "QC004", "QC004b", "unusual_czav_r_carbapenem_s"):
        assert "v16.1" in RULES[rid].get("recheck", ""), rid
    eucast = {k: v["version"] for k, v in SOURCES.items() if k.startswith("EUCAST")}
    assert set(eucast) == {"EUCAST_INTRINSIC", "EUCAST_EXPERT", "EUCAST_BP", "EUCAST_DETECT"}


# ── 7. Clinical decision validation engine (whole case) ─────────────────────
def _e2e(panel, *, sym, host, coll, renal=False, crcl=None, uti=None):
    pt = Patient(age_years=55, sex="Male", collection_method=coll, host_factors=host,
                 is_renal=renal, cl_cr=crcl)
    p = assess_pathogenicity("Urine", "Escherichia coli", "10^5", "Pure growth", sym, "30", "", "",
                             55, "Male", host, collection_method=coll)
    r = run_analysis(pt, "Escherichia coli", "Urine", panel, pathogenicity=p, uti_syndrome=uti)
    u = r["case"].cuti_device and "cuti" or uti
    if any(s.startswith(("Fever", "Rigors", "Flank")) for s in sym):
        u = "upper"
    txt = generate_report(patient_name="X", age=55, sex="Male", weight=70, cl_cr=crcl, is_renal=renal,
                          is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
                          banned=r["banned"], preg_warn_items=r["preg_warn"], organism="Escherichia coli",
                          specimen="Urine", interactions=r["interactions"], sir_map=panel,
                          patho_assessment=p, case=r["case"], treatment_gate=r["treatment_gate"])
    html = generate_pdf_html_report(patient_name="X", age=55, sex="Male", weight=70, cl_cr=crcl,
                                    is_renal=renal, is_preg=False, is_hepatic=False, allowed=r["allowed"],
                                    warned=r["warned"], banned=r["banned"], preg_warn_items=r["preg_warn"],
                                    organism="Escherichia coli", specimen="Urine", sir_map=panel,
                                    interactions=r["interactions"], mdr_result=r["mdr"],
                                    esbl_result=r["mechanism"], phenotypes=r["phenotypes"], lang="en",
                                    return_html=True, uti_syndrome=u, case=r["case"],
                                    treatment_gate=r["treatment_gate"])
    return r, u, txt, html


ESBL_LIMITED = {"Ceftriaxone": R, "Cefotaxime": R, "Ceftazidime": R, "Cefepime": R, "Ciprofloxacin": R,
                "Levofloxacin": R, "Trimethoprim/Sulfamethoxazole": R, "Amoxicillin + Clavulanic acid": R,
                "Nitrofurantoin": S, "Fosfomycin": S, "Gentamicin": S, "Amikacin": S,
                "Meropenem": S, "Ertapenem": S, "Piperacillin + Tazobactam": S}


@pytest.mark.parametrize("label,kw", [
    # The reviewer's example: Foley + E. coli + ESBL + fever + hypotension + low eGFR + limited S.
    ("foley_esbl_septic_low_egfr", dict(sym=["Fever (> 38°C)", "Rigors / Hypotension (sepsis)"],
                                        host=["Urinary catheter", HOST_Q := "Quadriplegia / Tetraplegia "
                                              "(cervical cord injury)"],
                                        coll=FOLEY, renal=True, crcl=25)),
    ("foley_no_fever", dict(sym=["Increased spasticity (SCI)"], host=["Urinary catheter"], coll=FOLEY)),
    ("voided_cystitis", dict(sym=["Dysuria / Frequency / Urgency"], host=[], coll=MSU, uti="lower")),
])
def test_whole_case_validation_passes_on_end_to_end_cases(label, kw):
    r, u, txt, html = _e2e(dict(ESBL_LIMITED), **kw)
    v = validate_case(r, specimen="Urine", sir_map=ESBL_LIMITED, uti_syndrome=u, report_text=txt,
                      pdf_html=html)
    assert not v, (label, v)
    if label == "foley_esbl_septic_low_egfr":
        offered = [i["name"] for i in r["ranked"] + r["allowed"] + r["warned"]]
        assert "Nitrofurantoin" not in offered and "Fosfomycin" not in offered
        # CrCl 25: the carbapenems are offered WITH their renal dose (caution), not dropped
        renal = {i["name"] for i in r["warned"] if i.get("warning_reason") == "renal_adjustment"}
        assert {"Meropenem", "Ertapenem"} <= renal


def test_the_validator_catches_what_it_is_for():
    r = _run(coll=MSU)
    r["ranked"] = r["ranked"] + [{"name": "Ciprofloxacin"}, {"name": "Levofloxacin"}]
    ids = {v["id"] for v in validate_case(r, specimen="Urine", sir_map=PANEL, uti_syndrome="upper",
                                          pdf_html="<p>ESBL+</p>")}
    assert {"V01", "V02", "V03", "V12"} <= ids


# ── 8. The page ─────────────────────────────────────────────────────────────
def test_the_page_blocks_the_reports_on_a_mismatch_and_releases_them_on_confirmation():
    from support.ui_harness import payload, rendered_text, run_page
    pl = payload("E. coli", "Urine", PANEL, age=23, sex="Female")
    pl["patient"]["CollectionMethod"] = MSU
    script = {"patho_coll_sel": FOLEY, "patho_host_sel": list(PARA), "patho_symp_urine": SYM}
    traces, state, errors = run_page(pl, runs=2, script=script)
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "CRITICAL" in txt and "التقرير النصي موقوف" in txt and not state.get("_rpt_text")
    _confirm = ("أؤكد إكلينيكياً أن طريقة الجمع المُدخلة هي الصحيحة رغم تقرير المعمل "
                "(يُطبع في التقرير) — بدون التأكيد أو التصحيح التقارير موقوفة")
    traces, state, errors = run_page(pl, runs=2, script={**script, _confirm: True})
    assert not errors, errors
    assert "physician confirmed" in (state.get("_rpt_text") or "")


def test_the_page_preselects_the_lab_reports_collection_method():
    from support.ui_harness import payload, rendered_text, run_page
    pl = payload("E. coli", "Urine", PANEL, age=23, sex="Female")
    pl["patient"]["CollectionMethod"] = MSU
    traces, state, errors = run_page(pl, runs=2)
    assert not errors, errors
    assert state.get("patho_collection") == MSU
    assert "CRITICAL" not in rendered_text(traces[-1])


def test_a_short_sheet_is_rendered_at_the_largest_size_that_fits(monkeypatch):
    from cdss.reports import fit_page

    class _Doc:
        def __init__(self, n):
            self.pages = [0] * n

        def write_pdf(self):
            return b"%PDF"
    seen = []

    class _HTML:
        def __init__(self, string):
            self.s = string

        def render(self):
            z = float(self.s.split("z=")[1].split(";")[0])
            return _Doc(1 if z <= 1.1 else 2)
    monkeypatch.setattr(fit_page, "_wp", type("W", (), {"HTML": _HTML}))
    monkeypatch.setattr(fit_page, "WEASYPRINT_AVAILABLE", True)

    def build(z):
        seen.append(z)
        return f"<html>z={z};</html>"
    assert fit_page.render_one_page(build) == b"%PDF"
    assert seen == [1.0, 1.18, 1.1]
