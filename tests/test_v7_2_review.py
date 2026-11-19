"""v7.2 (2026-11-19): the second external review of v7.1 -- the points that were right.

What it pins:
  * A "do not treat" pathogenicity verdict (asymptomatic bacteriuria, contaminant,
    colonisation, rejected sputum) withholds the treatment lists on screen and in the
    text report, the PDF and the image -- unless the physician overrides, which is printed.
  * A pathogenicity result calculated for other inputs is stale and is not used.
  * A catheter / stone / stent without fever or flank pain is a complicated UTI ("cuti"),
    not a pyelonephritis: the bladder-only agents are cautions, not bans.
  * Blood cultures are judged by SETS, not bottles; SIRS is not sepsis (Sepsis-3).
  * The respiratory specimen (ETA / BAL / PSB) decides the quantitative threshold.
  * Under 2 years the AAP figures are catheter / SPA figures and need pyuria.
  * AST consistency: "verify" (cefotaxime / ceftriaxone, amox-clav / amp-sulbactam) is a
    warning; logical impossibilities stay errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.astqc.ast_consistency import check_consistency, format_issue  # noqa: E402
from cdss.common.case_context import build_case_context  # noqa: E402
from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.organisms import pathogenicity as PG  # noqa: E402
from cdss.organisms.pathogenicity import (  # noqa: E402
    BLOOD_SET_OPTIONS, assess_pathogenicity, blood_sets_state, gate_suppresses, treatment_gate)
from cdss.pipeline import duration_syndrome_key, run_analysis  # noqa: E402
from cdss.reports.report_service import generate_pdf_html_report, generate_report  # noqa: E402
from cdss.stewardship.duration import get_treatment_duration  # noqa: E402
from cdss.stewardship.syndrome import get_infection_syndrome  # noqa: E402
from cdss.therapy.therapy_rules import UTI_SYNDROME_OPTIONS, resolve_uti_syndrome  # noqa: E402

S, I, R = "S", "I", "R"
PAN = {"Ampicillin": S, "Amoxicillin + Clavulanic acid": S, "Cefazolin": S, "Ceftriaxone": S,
       "Ciprofloxacin": S, "Levofloxacin": S, "Gentamicin": S, "Amikacin": S,
       "Trimethoprim/Sulfamethoxazole": S, "Nitrofurantoin": S, "Fosfomycin": S,
       "Meropenem": S, "Ertapenem": S, "Piperacillin + Tazobactam": S}
MID = "Midstream clean-catch"
FOLEY = "Indwelling catheter (Foley)"


def _bucket(r, name):
    for b in ("allowed", "warned", "banned", "preg_warn"):
        for it in r[b]:
            if it.get("name") == name:
                return b, it
    return None, None


def _urine(**k):
    kw = dict(specimen="Urine", organism="Escherichia coli", colony_count_text=">10^5",
              culture_purity="Pure growth", symptoms=["Asymptomatic"], pus_cells_text="20",
              urinalysis_result="", gram_stain="", age=70, sex="Male", host_factors=[],
              collection_method=MID)
    kw.update(k)
    return assess_pathogenicity(**kw)


def _blood(org, sets, sirs=(), hosts=()):
    return assess_pathogenicity(specimen="Blood", organism=org, colony_count_text="",
                                culture_purity="Pure growth", symptoms=[], pus_cells_text="",
                                urinalysis_result="", gram_stain="", age=50, sex="Male",
                                host_factors=list(hosts), sirs_criteria=list(sirs),
                                blood_source=sets)


def _resp(spec, count, signs=("New infiltrate on chest imaging", "Fever (> 38°C)",
                              "Productive cough / Purulent sputum")):
    return assess_pathogenicity(specimen=spec, organism="Pseudomonas aeruginosa",
                                colony_count_text=count, culture_purity="Pure growth",
                                symptoms=list(signs), pus_cells_text="", urinalysis_result="",
                                gram_stain="", age=60, sex="Male",
                                host_factors=["Tracheostomy / Mechanical ventilation"])


# ── 1. The no-treatment gate ────────────────────────────────────────────────
def test_asymptomatic_bacteriuria_gates_the_recommendations():
    pa = _urine()
    assert pa["category"] == "ASB_NO_TREAT"
    g = treatment_gate(pa)
    assert g and gate_suppresses(g) and "IDSA 2019" in g["reason_en"]
    r = run_analysis(Patient(age_years=70, sex="Male"), "Escherichia coli", "Urine", PAN,
                     pathogenicity=pa)
    assert r["treatment_gate"]["category"] == "ASB_NO_TREAT"
    assert r["ranked"] == [] and r["duration"] is None
    assert r["allowed"], "the drug-safety buckets are still returned for an override"


def test_the_physician_override_shows_the_options_and_is_recorded():
    r = run_analysis(Patient(age_years=70, sex="Male"), "Escherichia coli", "Urine", PAN,
                     pathogenicity=_urine(), treat_override=True)
    assert r["treatment_gate"]["override"] is True and r["ranked"] and r["duration"]


@pytest.mark.parametrize("cat,gated", [("ASB_NO_TREAT", True), ("CONTAMINANT_OR_COLONISER", True),
                                       ("LIKELY_CONTAMINANT", True), ("COLONISATION", True),
                                       ("SPECIMEN_REJECT", True), ("ASB_TREAT", False),
                                       ("GBS_PREGNANCY_IAP", False), ("POSSIBLE_INFECTION", False),
                                       ("INSUFFICIENT_DATA", False), ("TRUE_INFECTION", False),
                                       ("LRTI_POSSIBLE", False),
                                       ("POSSIBLE_CONTAMINANT_STERILE_SITE", False)])
def test_only_do_not_treat_verdicts_gate(cat, gated):
    assert bool(treatment_gate({"category": cat, "verdict": "v"})) is gated
    assert treatment_gate(None) is None


def test_pregnant_asymptomatic_bacteriuria_is_not_gated():
    pa = _urine(sex="Female", age=28, host_factors=["Pregnant"])
    assert pa["category"] == "ASB_TREAT" and treatment_gate(pa) is None


def _report_kw(gate):
    r = run_analysis(Patient(age_years=70, sex="Male"), "Escherichia coli", "Urine", PAN)
    return dict(patient_name="X", age=70, sex="Male", weight=70, cl_cr=None, is_renal=False,
                is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
                banned=r["banned"], preg_warn_items=r["preg_warn"], organism="Escherichia coli",
                specimen="Urine", interactions=[], sir_map=dict(PAN), treatment_gate=gate)


def test_the_text_report_withholds_the_lists_or_prints_the_override():
    g = treatment_gate(_urine())
    t = generate_report(**_report_kw(g))
    assert "NO ANTIBIOTIC TREATMENT INDICATED" in t and "RECOMMENDED ANTIBIOTICS" not in t
    assert "SENSITIVITY RESULTS" in t, "the AST itself is still reported"
    t2 = generate_report(**_report_kw(treatment_gate(_urine(), override=True)))
    assert "RECOMMENDED ANTIBIOTICS" in t2 and "physician's request" in t2


def test_the_pdf_withholds_the_lists_or_prints_the_override():
    pdf_kw = _report_kw(treatment_gate(_urine()))
    rr = run_analysis(Patient(age_years=70, sex="Male"), "Escherichia coli", "Urine", PAN)
    extra = dict(mdr_result=rr["mdr"], esbl_result=rr["mechanism"], phenotypes=rr["phenotypes"],
                 return_html=True, lang="en",
                 duration_data={"label": "x", "standard_days": 5})
    h = generate_pdf_html_report(**pdf_kw, **extra)
    assert "NO ANTIBIOTIC TREATMENT INDICATED" in h and "FIRST-LINE" not in h
    assert "Not applicable" in h
    pdf_kw["treatment_gate"] = treatment_gate(_urine(), override=True)
    h2 = generate_pdf_html_report(**pdf_kw, **extra)
    assert "physician" in h2 and "NO ANTIBIOTIC TREATMENT INDICATED" not in h2


def test_the_page_withholds_the_lists_and_the_override_brings_them_back(monkeypatch):
    pytest.importorskip("PIL")
    from support.ui_harness import payload, rendered_text, run_page
    import cdss_ui.report_panels as RP
    seen = {}
    orig = RP.generate_decision_tree_image

    def spy(*a, **k):
        seen.clear()
        seen.update(k)
        return orig(*a, **k)
    monkeypatch.setattr(RP, "generate_decision_tree_image", spy)
    pl = payload("Escherichia coli", "Urine", PAN, age=70, sex="Male")
    script = {"patho_coll_sel": MID, "patho_symp_urine": ["Asymptomatic"],
              "patho_calc_btn": True}
    traces, _state, errors = run_page(pl, runs=2, script=script)
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "لا يوجد داعٍ لمضاد حيوي" in txt and "🏆 Smart Antibiotic Ranking" not in txt
    assert seen["preferred"] == [] and seen["first_line"][0].startswith("NO ANTIBIOTIC")
    script["treat_override_chk_ASB_NO_TREAT"] = True
    traces, _state, errors = run_page(pl, runs=3, script=script)
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "🏆 Smart Antibiotic Ranking" in txt and "بطلب الطبيب" in txt
    assert seen["preferred"] and seen["first_line"][0].startswith("Physician override")


# ── 2. A stale pathogenicity result is not used ─────────────────────────────
def test_a_result_for_other_inputs_is_stale():
    from support import fake_streamlit
    fake_streamlit.install()
    import cdss_ui.pathogenicity_panel as PP
    from cdss_ui.state import current_patho_result
    ss = fake_streamlit.session_state
    ss.clear()
    kw = dict(specimen="Urine", organism="Escherichia coli", colony_count_text=">10^5",
              culture_purity="Pure growth", symptoms=["Asymptomatic"], pus_cells_text="20",
              urinalysis_result="", gram_stain="", age=70, sex="Male", host_factors=[],
              collection_method=MID)
    assert PP._calc_and_track(kw, True) and current_patho_result()["category"] == "ASB_NO_TREAT"
    assert PP._calc_and_track(dict(kw), False), "same inputs: still current"
    kw2 = dict(kw, symptoms=["Fever (> 38°C)"])
    assert PP._calc_and_track(kw2, False) is False
    assert ss["patho_stale"] is True and current_patho_result() is None
    assert PP._calc_and_track(kw2, True) and current_patho_result()["category"] != "ASB_NO_TREAT"


# ── 3. Complicated UTI is not pyelonephritis ────────────────────────────────
def test_resolver_separates_cuti_from_pyelonephritis():
    auto, cyst, upper, cuti = UTI_SYNDROME_OPTIONS
    assert resolve_uti_syndrome(auto, [], catheter=True) == "cuti"
    assert resolve_uti_syndrome(auto, ["Flank pain / Loin pain"], catheter=True) == "upper"
    assert resolve_uti_syndrome(cuti, ["Fever (> 38°C)"]) == "cuti", "an explicit choice wins"
    assert resolve_uti_syndrome(upper, []) == "upper"
    assert resolve_uti_syndrome(cyst, [], catheter=True) == "lower"


def test_a_stent_makes_it_complicated_and_the_card_and_course_agree():
    hf = ["Urinary obstruction / Stone / Stent"]
    assert build_case_context("Urine", hf, MID).cuti_device
    r = run_analysis(Patient(age_years=40, sex="Female", host_factors=hf), "Escherichia coli",
                     "Urine", PAN)
    assert r["syndrome"]["sub_type"] == "Complicated UTI"
    assert r["duration"]["label"].startswith("Complicated UTI")
    assert _bucket(r, "Nitrofurantoin")[0] == "warned"
    assert _bucket(r, "Nitrofurantoin")[1]["warning_reason"] == "cuti_bladder_agent"
    assert "generally not appropriate" in (_bucket(r, "Nitrofurantoin")[1].get("clinical_note_en") or "")
    assert duration_syndrome_key({"syndrome": "UTI"}, "cuti", "Urine") == "complicated UTI"


def test_uncomplicated_cystitis_keeps_its_course():
    d = get_treatment_duration("Urine", "E. coli", "Urinary Tract Infection (UTI) | Uncomplicated UTI",
                               30, "Female", False, [], "mild")
    assert d["label"] == "Uncomplicated cystitis"


def test_the_catheter_card_stays_ca_uti():
    syn = get_infection_syndrome("Urine", "E. coli", 40, False, is_cath=True, complicated=True)
    assert syn["sub_type"] == "Catheter-associated UTI (CA-UTI)"


# ── 4. Blood: sets, not bottles; SIRS is not sepsis ─────────────────────────
def test_blood_set_options_read_as_sets():
    assert [blood_sets_state(o) for o in BLOOD_SET_OPTIONS] == [
        "unknown", "one_set", "single", "multiple", "multiple"]
    assert blood_sets_state("Multiple bottles positive") == "legacy_multi"
    assert blood_sets_state("Single bottle positive") == "single"


def test_cons_needs_two_separately_drawn_sets():
    sirs = ["Temp > 38°C or < 36°C", "Heart rate > 90 / min"]
    two = _blood("Staphylococcus epidermidis", BLOOD_SET_OPTIONS[3], sirs, ["Central line / PICC"])
    assert two["category"] == "TRUE_INFECTION"
    legacy = _blood("Staphylococcus epidermidis", "Multiple bottles positive", sirs)
    assert legacy["category"] != "TRUE_INFECTION"
    assert any("positive sets" in m for m in legacy["missing_inputs"])
    one = _blood("Staphylococcus epidermidis", BLOOD_SET_OPTIONS[1])
    assert one["category"] == "LIKELY_CONTAMINANT", "one set drawn: repeat, never 'do not treat'"
    single = _blood("Staphylococcus epidermidis", BLOOD_SET_OPTIONS[2])
    assert single["category"] == "CONTAMINANT_OR_COLONISER"


def test_sirs_three_is_not_called_sepsis():
    r = _blood("Escherichia coli", BLOOD_SET_OPTIONS[0],
               ["Temp > 38°C or < 36°C", "Heart rate > 90 / min", "Resp rate > 20 / min (or PaCO₂ < 32)"])
    txt = " ".join(r["factors_pos"])
    assert "Sepsis-3" in txt and "sepsis probable" not in txt.lower()
    import cdss_ui.pathogenicity_panel as PP
    src = Path(PP.__file__).read_text(encoding="utf-8")
    assert "sepsis probable" not in src and "Sepsis-3" in src


# ── 5. Respiratory: the specimen decides the threshold ──────────────────────
def test_bal_psb_eta_thresholds():
    assert _resp("Sputum — Bronchoalveolar lavage (BAL)", "10^3 CFU/mL")["category"] != "TRUE_INFECTION"
    assert _resp("Sputum — Bronchoalveolar lavage (BAL)", "10^4 CFU/mL")["category"] == "TRUE_INFECTION"
    assert _resp("Sputum — Protected specimen brush (PSB)", "10^3 CFU/mL")["category"] == "TRUE_INFECTION"
    eta = _resp("Sputum — Endotracheal aspirate (ETA)", "moderate growth")
    assert eta["category"] == "TRUE_INFECTION", "semi-quantitative ETA (ATS/IDSA 2016)"
    miss = _resp("Sputum — Bronchoalveolar lavage (BAL)", "")
    assert any("BAL / PSB" in m for m in miss["missing_inputs"])


def test_infiltrate_without_signs_is_capped():
    r = assess_pathogenicity(specimen="Sputum — Bronchoalveolar lavage (BAL)",
                             organism="Streptococcus pneumoniae", colony_count_text="10^5",
                             culture_purity="Pure growth",
                             symptoms=["New infiltrate on chest imaging"], pus_cells_text="",
                             urinalysis_result="", gram_stain="WBCs + Gram Positive Cocci",
                             age=60, sex="Male", host_factors=[])
    assert r["score"] >= 70, "strong culture evidence ..."
    assert r["category"] == "LRTI_POSSIBLE" and "NO_RESP_SIGNS" in r["special_flags"]


def test_the_panel_offers_the_respiratory_specimen_and_count():
    import cdss_ui.pathogenicity_panel as PP
    src = Path(PP.__file__).read_text(encoding="utf-8")
    assert "RESP_SPECIMEN_SUBTYPES" in src and "np_resp_cfu" in src
    assert PG.RESP_SPECIMEN_SUBTYPES[2].startswith("Bronchoalveolar")


# ── 6. Under 2 years: catheter / SPA figures, with pyuria ───────────────────
def _infant(**k):
    kw = dict(organism="Escherichia coli", colony_count_text="10^5", symptoms=["Fever (> 38°C)"],
              pus_cells_text="20", age=0.5, sex="Male",
              collection_method="Intermittent catheterisation (in-out / CIC)")
    kw.update(k)
    return _urine(**kw)


def test_infant_catheter_specimen_with_pyuria_is_a_uti():
    r = _infant()
    assert r["category"] == "TRUE_INFECTION" and "AAP 2011" in r["threshold"]


def test_infant_without_pyuria_or_with_unknown_pyuria_is_not_true_infection():
    no = _infant(pus_cells_text="1")
    assert no["category"] == "POSSIBLE_INFECTION" and "INFANT_NO_PYURIA" in no["special_flags"]
    unk = _infant(pus_cells_text="")
    assert unk["category"] == "POSSIBLE_INFECTION"
    assert "Urinalysis / pyuria (AAP)" in unk["missing_inputs"]


def test_infant_midstream_uses_ten_to_the_five_and_asks_for_a_catheter_specimen():
    r = _infant(collection_method=MID)
    assert "midstream" in r["threshold"].lower() and "10^5" in r["threshold"]
    assert "INFANT_MIDSTREAM" in r["special_flags"] and r["category"] != "TRUE_INFECTION"


def test_neonate_and_8_to_60_days_name_their_rule():
    assert "first 7 days" in _infant(age=3 / 365.25)["threshold"]
    assert "8-60 days" in _infant(age=30 / 365.25)["threshold"]


def test_the_infant_caption_no_longer_says_any_count_is_significant():
    src = (ROOT / "cdss_ui" / "inputs.py").read_text(encoding="utf-8")
    assert "أي عدد مستعمرات ذو دلالة" not in src and "Age (days)" in src
    from support import fake_streamlit
    fake_streamlit.install()
    from types import SimpleNamespace
    import cdss_ui.pathogenicity_panel as PP
    assert PP._patho_age(SimpleNamespace(age=0, age_months=0, age_days=5)) == pytest.approx(5 / 365.25)
    assert PP._patho_age(SimpleNamespace(age=0, age_months=6, age_days=None)) == pytest.approx(0.5)


# ── 7. Captions that contradicted the engine ────────────────────────────────
def test_csf_caption_and_organism_guidance_label():
    panel = (ROOT / "cdss_ui" / "pathogenicity_panel.py").read_text(encoding="utf-8")
    assert "أي نمو مرضي بالضرورة" not in panel
    inputs = (ROOT / "cdss_ui" / "inputs.py").read_text(encoding="utf-8")
    assert "NOT adjusted to this isolate's AST" in inputs


# ── 8. AST consistency: verify vs error ─────────────────────────────────────
def test_cefotaxime_ceftriaxone_split_is_verify_not_error():
    iss = check_consistency("Escherichia coli", {"Cefotaxime": S, "Ceftriaxone": R})
    assert len(iss) == 1 and iss[0]["severity"] == "warning" and iss[0]["category"] == "verify"
    assert format_issue(iss[0])["message"].startswith("🟠")
    assert "not possible" not in iss[0]["reason_en"]


def test_amox_clav_amp_sulbactam_split_is_verify_and_the_arabic_agrees():
    iss = check_consistency("Klebsiella pneumoniae",
                            {"Amoxicillin + Clavulanic acid": S, "Ampicillin/Sulbactam": R})
    assert len(iss) == 1 and iss[0]["severity"] == "warning"
    assert "خطأ معملي" not in iss[0]["reason_ar"].replace("لا خطأ معملي مؤكد", "")


def test_meropenem_r_ertapenem_s_is_verify_with_mic_and_carbapenemase_test():
    iss = check_consistency("Serratia marcescens", {"Meropenem": R, "Ertapenem": S})
    assert len(iss) == 1 and iss[0]["severity"] == "warning" and "MIC" in iss[0]["fix_en"]


@pytest.mark.parametrize("org,sir", [
    ("Staphylococcus aureus", {"Oxacillin": S, "Cefoxitin": R}),
    ("Escherichia coli", {"Ampicillin": S, "Amoxicillin + Clavulanic acid": R}),
    ("Pseudomonas aeruginosa", {"Piperacillin": S, "Piperacillin + Tazobactam": R}),
])
def test_impossibilities_stay_errors(org, sir):
    iss = check_consistency(org, sir)
    assert iss and all(i["severity"] == "error" for i in iss)
    assert format_issue(iss[0])["message"].startswith("🔴")


# ── 9. Registry ─────────────────────────────────────────────────────────────
def test_idsa_cuti_2025_is_a_registered_source_and_the_audit_header_counts_right():
    from cdss.guidelines import eucast_audit
    from cdss.guidelines.guideline_registry import SOURCES
    src = SOURCES["IDSA_CUTI"]
    assert src["url"].startswith("https://www.idsociety.org/") and "SECONDARY" in src["note"]
    assert "42" in eucast_audit.__doc__ and len(eucast_audit.AUDIT) == 42
