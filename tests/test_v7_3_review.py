"""v7.3 (2026-11-19): the third external review (of v7.2) -- the points that were right.

What it pins:
  * UTI: the site (lower / upper) and the complicated status are separate. Fever, flank
    pain or rigors are not silenced by a manual "cystitis" / "cUTI without fever" choice
    unless the physician confirms a non-urinary source (printed); a catheter keeps a
    manual cystitis complicated.
  * The physician's "show the options anyway" belongs to one assessment (its signature).
  * BAL / PSB: a verbal growth report is not a quantitative count.
  * SIRS >= 3 is never printed as "sepsis probable" (screen, PDF, text).
  * AAP: the 8-60 day window is decided in days; 8-60 days is the FEBRILE-infant rule.
  * AST consistency severities match their registry rows; tetracycline / doxycycline is
    scoped; oxacillin / cefoxitin confirmation covers mecC; references are the right ones.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.astqc import ast_consistency as AC  # noqa: E402
from cdss.astqc.ast_consistency import check_consistency  # noqa: E402
from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.guidelines.guideline_registry import RULES  # noqa: E402
from cdss.organisms.pathogenicity import assess_pathogenicity  # noqa: E402
from cdss.pipeline import run_analysis  # noqa: E402
from cdss.reports.report_service import generate_report  # noqa: E402
from cdss.therapy.therapy_rules import UTI_SYNDROME_OPTIONS, classify_uti, resolve_uti_syndrome  # noqa: E402

S, I, R = "S", "I", "R"
AUTO, CYST, UPPER, CUTI = UTI_SYNDROME_OPTIONS
FEVER, FLANK, RIGORS = "Fever (> 38°C)", "Flank pain / Loin pain", "Rigors / Hypotension (sepsis)"
PAN = {"Nitrofurantoin": S, "Fosfomycin": S, "Ceftriaxone": S, "Ciprofloxacin": S,
       "Trimethoprim/Sulfamethoxazole": S, "Gentamicin": S}


def _bucket(r, name):
    for b in ("allowed", "warned", "banned", "preg_warn"):
        for it in r[b]:
            if it.get("name") == name:
                return b
    return None


# ── 1. UTI: site and complicated status ─────────────────────────────────────
@pytest.mark.parametrize("choice,sym", [(CYST, [FEVER]), (CUTI, [FLANK]), (CUTI, [RIGORS]),
                                        (CYST, [RIGORS]), (AUTO, [FEVER])])
def test_upper_tract_signs_are_not_silenced_by_a_manual_choice(choice, sym):
    uc = classify_uti(choice, sym)
    assert uc.value == "upper" and uc.site == "upper"
    assert uc.conflict is (choice != AUTO)


def test_a_confirmed_non_urinary_source_keeps_the_choice_and_is_recorded():
    uc = classify_uti(CYST, [FEVER], confirm_non_urinary=True)
    assert uc.value == "lower" and uc.conflict and uc.confirmed
    assert resolve_uti_syndrome(CUTI, [FEVER], confirm_non_urinary=True) == "cuti"


def test_site_and_complicated_status_are_separate():
    uc = classify_uti(CYST, [], catheter=True)
    assert (uc.site, uc.complicated, uc.value) == ("lower", True, "cuti")
    uc = classify_uti(UPPER, [], catheter=True)
    assert (uc.site, uc.complicated, uc.value) == ("upper", True, "upper")
    uc = classify_uti(AUTO, [], catheter=False)
    assert (uc.site, uc.complicated, uc.value) == (None, False, None)


def test_a_foley_with_a_manual_cystitis_never_leaves_bladder_agents_allowed():
    p = Patient(age_years=40, sex="Female", collection_method="Indwelling catheter (Foley)")
    r = run_analysis(p, "Escherichia coli", "Urine", PAN, uti_syndrome="lower")
    for d in ("Nitrofurantoin", "Fosfomycin"):
        assert _bucket(r, d) == "warned", (d, _bucket(r, d))


def test_the_page_warns_on_the_conflict_and_prints_the_decision():
    from support.ui_harness import payload, rendered_text, run_page
    pl = payload("Escherichia coli", "Urine", PAN, age=40, sex="Female")
    script = {"🫘 UTI syndrome (urine only)": CYST, "patho_symp_urine": [FEVER],
              "patho_coll_sel": "Midstream clean-catch"}
    traces, state, errors = run_page(pl, runs=2, script=script)
    assert not errors, errors
    assert "اخترت «التهاب مثانة»" in rendered_text(traces[-1])
    assert "treated as pyelonephritis" in (state.get("_rpt_text") or "")
    script["أؤكد إكلينيكياً: الحمى / الأعراض من مصدر غير بولي — اعتمد اختياري "
           "(يُطبع في التقرير)"] = True
    traces, state, errors = run_page(pl, runs=2, script=script)
    assert not errors, errors
    assert "physician kept 'cystitis'" in (state.get("_rpt_text") or "")


# ── 2. The override belongs to one assessment ───────────────────────────────
def test_the_override_key_follows_the_assessment_signature():
    from support import fake_streamlit
    fake_streamlit.install()
    from cdss_ui.state import treat_override_key
    ss = fake_streamlit.session_state
    ss.clear()
    ss["patho_sig"] = "a" * 32
    k1 = treat_override_key()
    ss[k1] = True                      # approved for assessment A
    ss["patho_sig"] = "b" * 32         # inputs changed -> assessment B
    k2 = treat_override_key()
    assert k1 != k2 and not ss.get(k2), "a new assessment must ask again"
    for f in ("analysis.py", "recommendations.py"):
        src = (ROOT / "cdss_ui" / f).read_text(encoding="utf-8")
        assert "treat_override_key()" in src and "treat_override_chk_{_g" not in src


# ── 3. BAL / PSB: verbal growth is not a count ──────────────────────────────
def _resp(spec, count):
    return assess_pathogenicity(specimen=spec, organism="Pseudomonas aeruginosa",
                                colony_count_text=count, culture_purity="Pure growth",
                                symptoms=["New infiltrate on chest imaging", FEVER],
                                pus_cells_text="", urinalysis_result="", gram_stain="",
                                age=60, sex="Male", host_factors=[])


@pytest.mark.parametrize("spec", ["Sputum — Bronchoalveolar lavage (BAL)",
                                  "Sputum — Protected specimen brush (PSB)"])
@pytest.mark.parametrize("count", ["moderate growth", "heavy growth", "+++"])
def test_bal_psb_verbal_growth_is_not_a_quantitative_count(spec, count):
    r = _resp(spec, count)
    assert not any("CFU/mL" in f for f in r["factors_pos"] + r["factors_neg"])
    assert any("BAL / PSB" in m for m in r["missing_inputs"])
    assert r["category"] != "TRUE_INFECTION"
    assert len(r["notes_en"]) == len(r["notes"])


def test_numeric_bal_and_semi_quantitative_eta_still_count():
    assert _resp("Sputum — Bronchoalveolar lavage (BAL)", "10^4 CFU/mL")["category"] == "TRUE_INFECTION"
    assert _resp("Sputum — Endotracheal aspirate (ETA)", "heavy growth")["category"] == "TRUE_INFECTION"
    low = _resp("Sputum — Endotracheal aspirate (ETA)", "scanty growth")
    assert not any("CFU/mL" in f for f in low["factors_neg"]), "no invented CFU figure"


# ── 4. SIRS is not sepsis anywhere ──────────────────────────────────────────
def test_no_output_prints_sepsis_probable():
    for d in ("cdss", "cdss_ui"):
        for f in (ROOT / d).rglob("*.py"):
            assert "sepsis probable" not in f.read_text(encoding="utf-8").lower(), f
    pa = assess_pathogenicity(specimen="Blood", organism="Escherichia coli", colony_count_text="",
                              culture_purity="Pure growth", symptoms=[], pus_cells_text="",
                              urinalysis_result="", gram_stain="", age=50, sex="Male",
                              host_factors=[], blood_source="",
                              sirs_criteria=["Temp > 38°C or < 36°C", "Heart rate > 90 / min",
                                             "Resp rate > 20 / min (or PaCO₂ < 32)"])
    assert "SIRS_HIGH" in pa["special_flags"]
    t = generate_report(patient_name="X", age=50, sex="Male", weight=70, cl_cr=None,
                        is_renal=False, is_preg=False, is_hepatic=False, allowed=[], warned=[],
                        banned=[], preg_warn_items=[], organism="Escherichia coli",
                        specimen="Blood", interactions=[], sir_map={}, patho_assessment=pa)
    assert "Sepsis-3" in t and "Sepsis Probable" not in t


# ── 5. AAP: days, and the febrile-infant rule ───────────────────────────────
def _infant(days, sym=(FEVER,)):
    return assess_pathogenicity(specimen="Urine", organism="Escherichia coli",
                                colony_count_text="10^5", culture_purity="Pure growth",
                                symptoms=list(sym), pus_cells_text="20", urinalysis_result="",
                                gram_stain="", age=days / 365.25, sex="Male", host_factors=[],
                                collection_method="Intermittent catheterisation (in-out / CIC)")


@pytest.mark.parametrize("days,rule", [(7, "first 7 days"), (8, "8-60 days"), (60, "8-60 days"),
                                       (61, "2-24 months"), (365.25 * 2 / 12, "2-24 months")])
def test_the_aap_window_is_decided_in_days(days, rule):
    assert rule in _infant(days)["threshold"]


def test_8_to_60_days_without_fever_says_the_febrile_rule_is_applied_by_analogy():
    t = _infant(30, sym=("Nausea / Vomiting",))["threshold"]
    assert "no fever entered" in t and "FEBRILE" in t
    assert _infant(30)["threshold"].startswith("Febrile infant 8-60 days")


def test_the_page_asks_for_days_up_to_two_months():
    src = (ROOT / "cdss_ui" / "inputs.py").read_text(encoding="utf-8")
    assert "page.age_months <= 2" in src and "max_value=91" in src
    from support import fake_streamlit
    fake_streamlit.install()
    import cdss_ui.pathogenicity_panel as PP
    assert PP._patho_age(SimpleNamespace(age=0, age_months=2, age_days=60)) == pytest.approx(60 / 365.25)


# ── 6. AST consistency: severity matches the registry ───────────────────────
def test_every_rule_the_registry_calls_verify_is_a_warning():
    rules = AC.EQUIVALENCE_RULES + AC.HIERARCHY_RULES
    for r in rules:
        row = RULES.get(r["id"], {})
        text = (str(row.get("note", "")) + " " + str(row.get("assertion", ""))).lower()
        text = text.replace("not a verify flag", "")          # equiv_oxa_fox: an error by design
        says_verify = bool(re.search(r"verify[- ]flag|verify rather|is verified|is to be repeated"
                                     r"|unexpected", text))
        if says_verify:
            assert r.get("severity") == "warning", r["id"]


@pytest.mark.parametrize("org,sir", [
    ("Escherichia coli", {"Ampicillin": S, "Amoxicillin + Clavulanic acid": R}),
    ("Pseudomonas aeruginosa", {"Piperacillin": S, "Piperacillin + Tazobactam": R}),
    ("Streptococcus pneumoniae", {"Penicillin": S, "Ceftriaxone": R}),
])
def test_inhibitor_and_pneumococcal_splits_are_verify(org, sir):
    iss = check_consistency(org, sir)
    assert iss and all(i["severity"] == "warning" for i in iss)
    assert "impossible" not in iss[0]["reason_en"].lower()


@pytest.mark.parametrize("org,flagged", [("Pseudomonas aeruginosa", False),
                                         ("Haemophilus influenzae", False),
                                         ("Staphylococcus aureus", True),
                                         ("Klebsiella pneumoniae", True),
                                         ("Enterococcus faecalis", True),
                                         ("Acinetobacter baumannii", True)])
def test_tetracycline_doxycycline_rule_is_scoped(org, flagged):
    iss = check_consistency(org, {"Tetracycline": S, "Doxycycline": R})
    assert bool(iss) is flagged


def test_oxacillin_cefoxitin_confirmation_covers_mecc():
    iss = check_consistency("Staphylococcus aureus", {"Oxacillin": S, "Cefoxitin": R})
    assert iss[0]["severity"] == "error"
    assert "mecC" in iss[0]["fix_en"] and "mecA-only PCR does not exclude mecC" in iss[0]["fix_en"]
    assert "one disk is wrong" not in iss[0]["reason_en"]
    assert "one disk is wrong" not in RULES["equiv_oxa_fox"]["assertion"]


def test_references_are_the_right_ones():
    lz = next(r for r in AC.EXCEPTIONAL_PHENOTYPES if r["id"] == "rare_linezolid_gram_pos")
    assert "tetracycline" not in lz["reference"].lower() and "linezolid" in lz["reference"].lower()
    vt = next(r for r in AC.HIERARCHY_RULES if r["id"] == "hier_van_vs_tei_enterococcus")
    assert "v3.2" not in vt["reference"]
    src = (ROOT / "cdss" / "therapy" / "intrinsic.py").read_text(encoding="utf-8")
    assert "authoritative EUCAST intrinsic-resistance table first" not in src
