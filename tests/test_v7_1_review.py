"""v7.1 (2026-11-19): the second full review of the rules and recommendations, and of the
pathogenicity assessment, the lab owner asked for after v7.0.

What it pins:
  * IDSA cUTI 2025 -- a urinary catheter / intermittent catheterisation / nephrostomy
    makes a UTI complicated; male sex, age, diabetes and renal impairment do not.
  * ACOG 2023 -- pregnancy has its own cards and durations (no fluoroquinolone list).
  * Ranking -- the cystitis first line (IDSA/ESCMID 2011) and MSSA (anti-staphylococcal
    beta-lactam) lead their lists; TMP-SMX is not initial therapy for S. aureus
    bacteraemia (Paul, BMJ 2015).
  * Intrinsic -- metronidazole / tinidazole are never active against aerobes.
  * EUCAST is a labelled second source, used only where CLSI is silent (fusidic acid).
  * Pathogenicity -- condom-catheter, nephrostomy and SCI spontaneous-voiding thresholds
    say what the sources say.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.common.case_context import build_case_context  # noqa: E402
from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.organisms.pathogenicity import assess_pathogenicity  # noqa: E402
from cdss.pipeline import run_analysis  # noqa: E402
from cdss.stewardship.duration import get_treatment_duration  # noqa: E402
from cdss.stewardship.severity import suggest_severity  # noqa: E402
from cdss.stewardship.syndrome import get_infection_syndrome  # noqa: E402
from cdss.therapy.therapy_rules import resolve_uti_syndrome  # noqa: E402

S, I, R = "S", "I", "R"
PAN = {"Ampicillin": S, "Amoxicillin + Clavulanic acid": S, "Cefazolin": S, "Ceftriaxone": S,
       "Ciprofloxacin": S, "Levofloxacin": S, "Gentamicin": S, "Amikacin": S,
       "Trimethoprim/Sulfamethoxazole": S, "Nitrofurantoin": S, "Fosfomycin": S,
       "Meropenem": S, "Ertapenem": S, "Piperacillin + Tazobactam": S}
QUAD = "Quadriplegia / Tetraplegia (cervical cord injury)"


def _bucket(r, name):
    for b in ("allowed", "warned", "banned", "preg_warn"):
        for it in r[b]:
            if it.get("name") == name:
                return b, it
    return None, None


# ── IDSA cUTI 2025: what makes a UTI complicated ─────────────────────────────
@pytest.mark.parametrize("age,sex,renal,hf", [
    (30, "Male", False, []), (75, "Female", False, []), (40, "Female", True, []),
    (40, "Female", False, ["Diabetes"])])
def test_male_age_renal_diabetes_alone_are_not_complicated(age, sex, renal, hf):
    sv = suggest_severity("Urine", age, sex, False, renal, 25 if renal else None, hf, [])
    assert sv["suggested"] == "mild", sv


@pytest.mark.parametrize("hf,sym", [(["Urinary catheter"], []), ([], ["Fever (> 38°C)"]),
                                    (["Urinary obstruction / Stone / Stent"], [])])
def test_catheter_stent_or_fever_make_it_complicated(hf, sym):
    assert suggest_severity("Urine", 30, "Female", False, False, None, hf, sym)["suggested"] == "moderate"


def test_a_catheter_resolves_auto_mode_to_cuti_but_an_explicit_choice_wins():
    # v7.2 (second external review): complicated ("cuti"), not pyelonephritis ("upper")
    assert resolve_uti_syndrome("تلقائي (من الأعراض)", [], catheter=True) == "cuti"
    assert resolve_uti_syndrome("تلقائي (من الأعراض)", ["Fever (> 38°C)"], catheter=True) == "upper"
    # v7.3 (third review): a device keeps an explicit cystitis complicated
    assert resolve_uti_syndrome("التهاب مثانة (سفلي)", [], catheter=True) == "cuti"
    assert resolve_uti_syndrome("تلقائي (من الأعراض)", [], catheter=False) is None


@pytest.mark.parametrize("coll", ["Indwelling catheter (Foley)", "Intermittent catheterisation (in-out / CIC)",
                                  "Suprapubic catheter", "Nephrostomy / Ileal conduit"])
def test_pipeline_bans_bladder_only_agents_with_a_catheter(coll):
    # v7.2 (second external review): with a catheter and no fever / flank pain the
    # UTI is complicated, not a pyelonephritis -- the bladder-only agents are
    # CAUTIONS (IDSA cUTI 2025 "generally not appropriate"); fever bans them.
    p = Patient(age_years=40, sex="Female", collection_method=coll)
    r = run_analysis(p, "Escherichia coli", "Urine", PAN)
    assert build_case_context("Urine", [], coll).cuti_device
    for d in ("Nitrofurantoin", "Fosfomycin"):
        assert _bucket(r, d)[0] == "warned", (coll, d, _bucket(r, d)[0])
        assert _bucket(r, d)[1].get("warning_reason") == "cuti_bladder_agent"
    r_up = run_analysis(p, "Escherichia coli", "Urine", PAN, uti_syndrome="upper")
    for d in ("Nitrofurantoin", "Fosfomycin"):
        assert _bucket(r_up, d)[0] == "banned", (coll, d, _bucket(r_up, d)[0])


def test_a_mans_uti_has_its_own_card_and_seven_days():
    syn = get_infection_syndrome("Urine", "E. coli", 50, False, sex="Male")
    assert syn["sub_type"] == "UTI in men"
    d = get_treatment_duration("Urine", "E. coli", "UTI", 50, "Male", False, [], "mild")
    assert d["label"].startswith("UTI in men") and d["standard_days"] == 7


def test_an_older_woman_with_cystitis_is_not_complicated():
    assert get_infection_syndrome("Urine", "E. coli", 80, False, sex="Female")["sub_type"] == "Uncomplicated UTI"
    d = get_treatment_duration("Urine", "E. coli", "UTI", 80, "Female", True, [], "mild")
    assert d["label"] == "Uncomplicated cystitis"


# ── ACOG 2023: pregnancy ─────────────────────────────────────────────────────
def test_pregnancy_cards_never_list_a_fluoroquinolone():
    for kw in ({}, {"uti_upper": True}, {"is_cath": True}):
        syn = get_infection_syndrome("Urine", "E. coli", 28, True, sex="Female", **kw)
        assert not any("floxacin" in x for x in syn["first_choice"]), (kw, syn)
    assert get_infection_syndrome("Urine", "E. coli", 28, True, uti_upper=True)["sub_type"] == \
        "Pyelonephritis in pregnancy"


def test_pregnancy_durations():
    cyst = get_treatment_duration("Urine", "E. coli", "UTI", 28, "Female", False, [], "moderate", is_preg=True)
    pyelo = get_treatment_duration("Urine", "E. coli", "pyelonephritis", 28, "Female", False, [],
                                   "moderate", is_preg=True)
    assert "pregnancy" in cyst["label"].lower() and cyst["max_days"] == 7
    assert pyelo["label"] == "Pyelonephritis in pregnancy" and pyelo["standard_days"] == 14


# ── Ranking ──────────────────────────────────────────────────────────────────
def test_pan_susceptible_cystitis_starts_with_the_idsa_first_line():
    r = run_analysis(Patient(age_years=30, sex="Female"), "Escherichia coli", "Urine", PAN)
    assert r["ranked"][0]["name"] in ("Nitrofurantoin", "Trimethoprim/Sulfamethoxazole", "Fosfomycin")
    names = [i["name"] for i in r["ranked"]]
    assert names.index("Fosfomycin") < names.index("Amoxicillin + Clavulanic acid")
    assert names.index("Fosfomycin") < names.index("Gentamicin")


def test_mssa_starts_with_an_anti_staphylococcal_beta_lactam():
    panel = {"Oxacillin": S, "Cefoxitin": S, "Cefazolin": S, "Clindamycin": S, "Doxycycline": S,
             "Trimethoprim/Sulfamethoxazole": S, "Vancomycin": S, "Erythromycin": S}
    for spec in ("Blood", "Wound Swab", "Pus"):
        r = run_analysis(Patient(age_years=50), "Staphylococcus aureus", spec, panel)
        assert r["ranked"][0]["name"] in ("Cefazolin", "Oxacillin"), (spec, r["ranked"][0]["name"])


def test_tmp_smx_is_not_initial_therapy_for_s_aureus_bacteraemia():
    panel = {"Oxacillin": R, "Vancomycin": S, "Daptomycin": S, "Trimethoprim/Sulfamethoxazole": S}
    r = run_analysis(Patient(age_years=50), "MRSA", "Blood", panel)
    b, it = _bucket(r, "Trimethoprim/Sulfamethoxazole")
    assert b == "warned" and it["warning_reason"] == "saureus_bsi_tmp_smx"
    assert "Paul" in it["clinical_note_en"]
    # ...but it stays an ordinary option for an MRSA skin infection
    assert _bucket(run_analysis(Patient(age_years=50), "MRSA", "Wound Swab", panel),
                   "Trimethoprim/Sulfamethoxazole")[0] == "allowed"


# ── Intrinsic: nitroimidazoles and aerobes ───────────────────────────────────
@pytest.mark.parametrize("org,spec", [("Escherichia coli", "Blood"), ("Escherichia coli", "CSF"),
                                      ("Staphylococcus aureus", "Wound Swab"),
                                      ("Enterobacterales (unspeciated)", "Blood")])
def test_metronidazole_is_never_offered_against_an_aerobe(org, spec):
    r = run_analysis(Patient(age_years=40), org, spec, {"Metronidazole": S, "Meropenem": S})
    assert _bucket(r, "Metronidazole")[0] == "banned"


def test_metronidazole_stays_for_anaerobes():
    r = run_analysis(Patient(age_years=40), "Anaerobes (لاهوائيات)", "Blood", {"Metronidazole": S})
    assert _bucket(r, "Metronidazole")[0] == "allowed"


# ── EUCAST as a labelled second source ───────────────────────────────────────
def test_fusidic_acid_is_labelled_as_read_by_eucast():
    r = run_analysis(Patient(age_years=40), "Staphylococcus aureus", "Wound Swab",
                     {"Fusidic acid": S, "Oxacillin": S})
    b, it = _bucket(r, "Fusidic acid")
    assert b in ("allowed", "warned")
    assert "EUCAST" in it["clinical_note"] and "CLSI M100" in it["clinical_note_en"]


def test_oral_fosfomycin_note_names_no_other_organism():
    r = run_analysis(Patient(age_years=55), "Enterococcus faecium", "Urine", {"Fosfomycin": S})
    note = str(_bucket(r, "Fosfomycin")[1].get("clinical_note"))
    assert "Klebsiella" not in note and "CLSI M100" in note


# ── Syndrome devices: HAP/VAP and CRBSI are reachable ────────────────────────
def test_ventilator_names_hap_vap_and_its_duration():
    p = Patient(age_years=60, host_factors=["Tracheostomy / Mechanical ventilation"])
    r = run_analysis(p, "Pseudomonas aeruginosa", "Sputum", {"Ceftazidime": S, "Ciprofloxacin": S})
    assert r["syndrome"]["sub_type"] == "HAP/VAP" and r["duration"]["label"] == "HAP / VAP"


def test_central_line_names_crbsi():
    p = Patient(age_years=60, host_factors=["Central line / PICC"])
    r = run_analysis(p, "Escherichia coli", "Blood", {"Ceftriaxone": S})
    assert "CRBSI" in r["syndrome"]["sub_type"]


def test_cap_with_pseudomonas_or_acinetobacter_is_seven_days():
    r = run_analysis(Patient(age_years=40), "Acinetobacter baumannii", "Sputum",
                     {"Ampicillin/Sulbactam": S, "Meropenem": S})
    assert r["duration"]["standard_days"] == 7


# ── Pathogenicity thresholds ─────────────────────────────────────────────────
def _thr(coll, hf, sym, cfu="5x10^4"):
    return assess_pathogenicity("Urine", "Escherichia coli", cfu, "Pure growth", sym, "", "", "",
                                40, "Male", hf, collection_method=coll)


def test_condom_catheter_thresholds_say_what_the_sources_say():
    sci = _thr("Condom catheter", [QUAD], ["Increased spasticity (SCI)"])
    asym = _thr("Condom catheter", [QUAD], ["Asymptomatic"])
    nonsci = _thr("Condom catheter", [], ["Fever (> 38°C)"])
    assert "10^4" in sci["threshold"] and "NIDRR" in sci["threshold"]
    assert "10^5" in asym["threshold"] and "asymptomatic bacteriuria" in asym["threshold"]
    assert "gives no CA-UTI count" in nonsci["threshold"]
    assert "IDSA CA-UTI 2009" in nonsci["references"]
    assert any("NIDRR" in x for x in sci["references"])


def test_sci_thresholds_follow_nidrr_by_collection_method():
    # v7.1 (external review): applied, not only quoted in a borderline note
    sv = _thr("Midstream clean-catch", [QUAD], ["Fever (> 38°C)"], "10^4")
    ic = _thr("Intermittent catheterisation (in-out / CIC)", [QUAD], ["Increased spasticity (SCI)"], "500")
    assert "Spontaneous voiding in spinal cord injury" in sv["threshold"] and "10^5" in sv["threshold"]
    # v7.4: the factor names the threshold value ("meets the 100 CFU/mL threshold")
    assert "10^2" in ic["threshold"] and "meets the 100 CFU/mL threshold" in " ".join(ic["factors_pos"])
    ic_asym = _thr("Intermittent catheterisation (in-out / CIC)", [QUAD], ["Asymptomatic"], "500")
    assert "10^5" in ic_asym["threshold"]


def test_nephrostomy_threshold_is_by_analogy_not_an_idsa_figure():
    r = _thr("Nephrostomy / Ileal conduit", [], ["Fever (> 38°C)"], "10^4")
    assert "by analogy" in r["threshold"]


def test_vap_note_no_longer_demands_a_quantitative_culture():
    r = assess_pathogenicity("Tracheal aspirate", "Pseudomonas aeruginosa", "", "", [], "", "", "",
                             60, "Male", ["Tracheostomy / Mechanical ventilation"])
    assert any("semi-quantitative" in n for n in r["notes_en"])
    assert not any("+ quantitative culture" in n for n in r["notes_en"])


# ── Renal: "no options" is not what a dose adjustment means ──────────────────
def test_renal_only_cautions_are_reported_as_usable_at_the_adjusted_dose():
    from cdss.reports.report_service import generate_report
    esbl = {"Ceftriaxone": R, "Meropenem": S, "Ertapenem": S, "Nitrofurantoin": S}
    p = Patient(age_years=70, sex="Female", is_renal=True, cl_cr=20)
    r = run_analysis(p, "Escherichia coli", "Urine", esbl)
    assert not r["allowed"] and r["warned"]
    txt = generate_report(patient_name="T", age=70, sex="Female", weight=60, cl_cr=20, is_renal=True,
                          is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
                          banned=r["banned"], preg_warn_items=r["preg_warn"], organism="E. coli",
                          specimen="Urine", interactions=r["interactions"], sir_map=esbl)
    assert "No recommended options" not in txt and "can be used at that dose" in txt


# ═══ External review of v7.0 (2026-11-19, second reviewer) ═══════════════════
def _uri(sym, cfu="10^5", **kw):
    a = dict(specimen="Urine", organism="Escherichia coli", colony_count_text=cfu,
             culture_purity="Pure growth", symptoms=sym, pus_cells_text="20-25",
             urinalysis_result="Positive (nitrite / LE)",
             gram_stain="Gram-negative bacilli with WBCs", age=30, sex="Female", host_factors=[])
    a.update(kw)
    return assess_pathogenicity(**a)


def test_urine_without_symptoms_entered_is_insufficient_not_treat():
    r = _uri([])
    assert r["category"] == "INSUFFICIENT_DATA" and "Treat" not in r["verdict"]


def test_one_voided_specimen_in_a_woman_is_provisional_abu():
    r = _uri(["Asymptomatic"])
    assert r["category"] == "ASB_NO_TREAT" and "provisional" in r["verdict"]
    assert "two consecutive" in r["interpretation_en"]
    assert "provisional" not in _uri(["Asymptomatic"], sex="Male")["verdict"]


def test_infant_thresholds_name_the_right_aap_guideline():
    young = _uri(["Fever (> 38°C)"], "5x10^4", age=1 / 12, collection_method="Urethral catheter (in-out, infant)")
    older = _uri(["Fever (> 38°C)"], "5x10^4", age=1.0, collection_method="Urethral catheter (in-out, infant)")
    assert "AAP 2021" in young["threshold"] and "2-24 months" in older["threshold"]


def test_psb_reaches_the_respiratory_rules():
    r = assess_pathogenicity("PSB", "Pseudomonas aeruginosa", "10^3", "Pure growth",
                             ["New infiltrate on chest imaging", "Fever (> 38°C)"], "", "", "",
                             60, "Male", [])
    assert "Specimen type not recognised" not in r["missing_inputs"] and "PSB" in r["threshold"]


def test_sputum_without_an_infiltrate_is_never_true_infection():
    r = assess_pathogenicity("Sputum", "Pseudomonas aeruginosa", "Heavy growth", "Pure growth",
                             ["Productive cough / Purulent sputum", "Fever (> 38°C)"], "", "",
                             "Many Gram-negative bacilli", 60, "Male", [],
                             sputum_pus_cells="30", sputum_epithelial="5")
    assert r["category"] == "LRTI_POSSIBLE" and "NOT established" in r["verdict"]
    r2 = assess_pathogenicity("Sputum", "Pseudomonas aeruginosa", "Heavy growth", "Pure growth",
                              ["Productive cough / Purulent sputum", "Fever (> 38°C)",
                               "New infiltrate on chest imaging"], "", "",
                              "Many Gram-negative bacilli", 60, "Male", [],
                              sputum_pus_cells="30", sputum_epithelial="5")
    assert r2["category"] == "TRUE_INFECTION"


def test_dtr_is_confirmed_only_with_all_eight_tested():
    from cdss.resistance.mechanism import predict_esbl
    five = {"Piperacillin + Tazobactam": R, "Ceftazidime": R, "Cefepime": R, "Meropenem": R,
            "Ciprofloxacin": R}
    m = predict_esbl("Pseudomonas aeruginosa", five)
    assert m["dtr"] is False and m["dtr_possible"] is True
    assert set(m["dtr_untested"]) == {"Aztreonam", "Imipenem/Cilastatin", "Levofloxacin"}
    assert "POSSIBLE DTR" in m["mechanism"]
    full = dict(five, Aztreonam=R, **{"Imipenem/Cilastatin": I, "Levofloxacin": R})
    assert predict_esbl("Pseudomonas aeruginosa", full)["dtr"] is True


def test_a_confirmed_kpc_outranks_a_susceptible_carbapenem_panel():
    panel = {"Meropenem": S, "Ertapenem": S, "Ceftriaxone": R, "Sulopenem": S,
             "Cefepime + Enmetazobactam": S, "Pivmecillinam": S, "Gepotidacin": S}
    r = run_analysis(Patient(age_years=30, sex="Female"), "Escherichia coli", "Urine", panel,
                     carbapenemase_type="KPC")
    for d in ("Sulopenem", "Cefepime + Enmetazobactam", "Pivmecillinam", "Meropenem"):
        assert _bucket(r, d)[0] == "banned", d
    b, it = _bucket(r, "Gepotidacin")
    assert b == "warned" and "CRE" in it.get("clinical_note", "")


def test_new_agent_scope_is_by_species_and_taxonomy():
    from cdss.therapy.rules.new_agents import _in_scope, _is_enterobacterales
    assert _in_scope("Sulopenem", "klebsiella spp.", "Klebsiella spp.") == "enterobacterales"
    assert _in_scope("Sulopenem", "klebsiella pneumoniae", "Klebsiella pneumoniae") == "yes"
    assert _is_enterobacterales("pantoea agglomerans") and _is_enterobacterales("raoultella planticola")
    assert _in_scope("Cefepime + Enmetazobactam", "pantoea agglomerans", "Pantoea agglomerans") == "yes"


def test_gepotidacin_reads_the_weight():
    panel = {"Gepotidacin": S, "Nitrofurantoin": S}
    light = run_analysis(Patient(age_years=13, sex="Female", weight_kg=30), "Escherichia coli",
                         "Urine", panel)
    assert _bucket(light, "Gepotidacin")[0] == "banned"
    unknown = run_analysis(Patient(age_years=13, sex="Female"), "Escherichia coli", "Urine", panel)
    b, it = _bucket(unknown, "Gepotidacin")
    assert b == "warned" and "40 kg" in it.get("clinical_note", "")
    ok = run_analysis(Patient(age_years=13, sex="Female", weight_kg=45), "Escherichia coli",
                      "Urine", panel)
    assert _bucket(ok, "Gepotidacin")[0] == "allowed"


def test_sulopenem_is_not_offered_for_upper_uti():
    r = run_analysis(Patient(age_years=30, sex="Female"), "Escherichia coli", "Urine",
                     {"Sulopenem": S, "Ertapenem": S}, uti_syndrome="upper")
    b, it = _bucket(r, "Sulopenem")
    assert b == "banned" and it["category"] == "specimen"


def test_esbl_labels_never_suggest_confirmation():
    from cdss.resistance.mechanism import predict_esbl
    one = predict_esbl("Escherichia coli", {"Ceftriaxone": R})
    two = predict_esbl("Escherichia coli", {"Ceftriaxone": R, "Ceftazidime": R})
    assert "SUSPECTED" in one["mechanism"] and "not confirmed" in one["mechanism"]
    assert "HIGHLY SUGGESTIVE" in two["mechanism"] and "not molecularly confirmed" in two["mechanism"]


def test_the_score_is_labelled_as_evidence_not_probability():
    import inspect
    from cdss.reports import patho_pdf, report_service
    assert "Evidence score" in (ROOT / "cdss_ui" / "patho_view.py").read_text(encoding="utf-8")
    assert "not a probability" in inspect.getsource(patho_pdf)
    assert "not a probability" in inspect.getsource(report_service)
