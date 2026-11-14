"""v6.7 (2026-11-14): regression tests for the findings of the full logic review.

Each test names the defect it holds closed. See CHANGELOG_2026-11-12.md, section 9.
"""
import ast
import re
from pathlib import Path

import pytest

from cdss.common.clinical_utils import Patient
from cdss.pipeline import run_analysis

ROOT = Path(__file__).resolve().parents[1]
AR = re.compile(r"[؀-ۿ]")
FALLBACK = "A clinical note for this item is available in the Arabic report."
ADULT = Patient(age_years=45, sex="Female")


def _bucket(r, name):
    for k in ("allowed", "warned", "banned", "preg_warn"):
        if any(d.get("name") == name for d in r[k]):
            return k
    return None


def _pdf(r, organism, specimen, sir, patient, lang="en", **kw):
    from cdss.reports.report_service import generate_pdf_html_report
    return generate_pdf_html_report(
        patient_name="T", age=patient.age_years, sex=patient.sex, weight=70, cl_cr=patient.cl_cr or 95,
        is_renal=patient.is_renal, is_preg=patient.is_pregnant, is_hepatic=patient.is_hepatic,
        allowed=r["allowed"], warned=r["warned"], banned=r["banned"], preg_warn_items=r["preg_warn"],
        organism=organism, specimen=specimen, sir_map=sir, interactions=r["interactions"],
        mdr_result=r["mdr"], esbl_result=r["mechanism"], phenotypes=r["phenotypes"],
        child_pugh=patient.child_pugh if patient.is_hepatic else "", lang=lang, return_html=True, **kw) or ""


# ── 1. a ceftazidime allergy was ignored for ceftazidime itself ───────────────
def test_ceftazidime_allergy_bans_ceftazidime_and_warns_on_shared_side_chain():
    sir = {"Ceftazidime": "S", "Ceftazidime + Avibactam": "S", "Meropenem": "S", "Cefiderocol": "S",
           "Aztreonam": "S"}
    r = run_analysis(Patient(age_years=45, sex="Female", allergies=["Ceftazidime"]),
                     "Escherichia coli", "Blood", sir)
    assert _bucket(r, "Ceftazidime") == "banned"
    assert _bucket(r, "Ceftazidime + Avibactam") == "banned"
    assert _bucket(r, "Aztreonam") == "warned" and _bucket(r, "Cefiderocol") == "warned"
    assert _bucket(r, "Meropenem") == "allowed"


# ── 2. interaction alerts said WHICH pair, never WHAT it does ─────────────────
def test_interaction_alert_names_the_effect_in_both_languages():
    from cdss.formulary.interaction_effects import interaction_alert
    from cdss.reports.i18n_en import alert_en
    r = run_analysis(Patient(age_years=60, sex="Male", current_meds=["Warfarin (مضادات التخثر)",
                                                                       "Valproic acid (مضادات الصرع)"]),
                     "Klebsiella pneumoniae", "Blood", {"Ciprofloxacin": "S", "Meropenem": "S"})
    cip = next(a for a in r["interactions"] if "Ciprofloxacin" in a and "Warfarin" in a)
    assert "INR" in cip
    mer = next(a for a in r["interactions"] if "Meropenem" in a)
    assert "Valproate" in mer and "60-100%" in mer
    en = alert_en(mer)
    assert not AR.search(en) and "valproate" in en and en.startswith("⚡ Interaction: Meropenem with Valproic acid")
    assert "MHRA" in interaction_alert("Fusidic acid", "Statins (أدوية الكوليسترول)", "en")
    assert "CPK" in interaction_alert("Daptomycin", "Statins (أدوية الكوليسترول)", "en")


def test_every_declared_interaction_has_an_effect_sentence():
    from cdss.formulary.abx_guidelines import ABX_GUIDELINES
    from cdss.formulary.co_medications import _canon_med
    from cdss.formulary.interaction_effects import INTERACTION_EFFECTS
    missing = sorted({_canon_med(m) for v in ABX_GUIDELINES.values() for m in (v.get("interacts_with") or [])}
                     - set(INTERACTION_EFFECTS))
    assert not missing, f"declared interactions with no effect text: {missing}"


# ── 3. the English PDF fell back to "see the Arabic report" 1,779 times ──────
_GN = {d: "S" for d in ("Ampicillin", "Amoxicillin + Clavulanic acid", "Ceftriaxone", "Ceftazidime", "Cefepime",
                        "Piperacillin + Tazobactam", "Meropenem", "Ciprofloxacin", "Trimethoprim/Sulfamethoxazole",
                        "Gentamicin", "Nitrofurantoin", "Fosfomycin", "Ertapenem")}
_ESBL = dict(_GN, Ceftriaxone="R", Ceftazidime="R", Cefepime="R", Ampicillin="R")
_PA_CR = {"Meropenem": "R", "Imipenem/Cilastatin": "R", "Ceftazidime": "S", "Piperacillin + Tazobactam": "S",
          "Amikacin": "S"}
_POSS_MRSA = {"Penicillin": "R", "Amoxicillin + Clavulanic acid": "R", "Cefazolin": "S", "Vancomycin": "S",
              "Linezolid": "S"}


@pytest.mark.parametrize("organism,specimen,sir,patient", [
    ("Escherichia coli", "Urine", _GN, Patient(age_years=30, sex="Female", is_pregnant=True, is_hepatic=True,
                                               child_pugh="B", current_meds=["Warfarin (مضادات التخثر)",
                                                                             "ACE inhibitors (مثبطات ACE)"])),
    ("Escherichia coli", "Urine", _GN, Patient(age_years=0, age_months=2, sex="Male")),
    ("Escherichia coli", "Urine", _GN, Patient(age_years=0, sex="Male")),
    ("Escherichia coli", "Blood", _ESBL, ADULT),
    ("Enterobacter cloacae", "Blood", _ESBL, ADULT),
    ("Klebsiella pneumoniae", "Blood", dict(_ESBL, Meropenem="R", Ertapenem="R"), ADULT),
    ("Escherichia coli", "Blood", dict(_GN, Ertapenem="R"), ADULT),
    ("Pseudomonas aeruginosa", "Blood", _PA_CR, ADULT),
    ("Staphylococcus aureus", "Blood", _POSS_MRSA, ADULT),
])
def test_english_pdf_has_no_arabic_and_no_fallback(organism, specimen, sir, patient):
    r = run_analysis(patient, organism, specimen, sir)
    html = _pdf(r, organism, specimen, sir, patient)
    assert FALLBACK not in html
    assert "Pregnancy: not a first-line agent. Use only when no safer" not in html
    body = html.replace("@@PTNAME@@", "")
    assert not AR.search(re.sub(r"<style>.*?</style>", "", body, flags=re.S))


def test_mechanism_details_all_have_an_english_form():
    tree = ast.parse((ROOT / "cdss" / "resistance" / "mechanism.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            if "detail" in keys:
                assert "detail_en" in keys, f"mechanism.py line {node.lineno}: detail without detail_en"


def test_pregnancy_notes_exist_in_english_for_every_caution_agent():
    from cdss.formulary.abx_guidelines import ABX_GUIDELINES
    from cdss.formulary.pregnancy_en import PREG_NOTE_EN
    from cdss.therapy.tables import preg_status_of
    need = [k for k, v in ABX_GUIDELINES.items() if preg_status_of(v) == "Warn"]
    assert need and not [k for k in need if k not in PREG_NOTE_EN]
    for note in PREG_NOTE_EN.values():
        assert not AR.search(note)
    assert "3rd trimester" in PREG_NOTE_EN["Nitrofurantoin"] and "kernicterus" in \
        PREG_NOTE_EN["Trimethoprim/Sulfamethoxazole"]


def test_preterm_ceftriaxone_note_reaches_the_english_report():
    p = Patient(age_years=0, age_months=2, sex="Male")
    sir = {"Ceftriaxone": "S", "Cefotaxime": "S", "Ampicillin": "S"}
    r = run_analysis(p, "Escherichia coli", "Blood", sir)
    item = next(d for d in r["warned"] if d["name"] == "Ceftriaxone")
    from cdss.therapy.notes import warned_note_for
    en = warned_note_for(item, "en")
    assert "41 weeks postmenstrual" in en and not AR.search(en)


def test_possible_mrsa_note_has_an_english_form():
    r = run_analysis(ADULT, "Staphylococcus aureus", "Blood", _POSS_MRSA)
    item = next(d for d in r["warned"] if d["name"] == "Cefazolin")
    from cdss.therapy.notes import warned_note_for
    en = warned_note_for(item, "en")
    assert "cefoxitin" in en.lower() and not AR.search(en)


# ── 4. pathogenicity ─────────────────────────────────────────────────────────
def _patho(**kw):
    from cdss.organisms.pathogenicity import assess_pathogenicity
    base = dict(specimen="Blood", organism="Staphylococcus epidermidis", colony_count_text="",
                culture_purity="Pure growth", symptoms=["Fever (> 38°C)"], pus_cells_text="",
                urinalysis_result="", gram_stain="", age=60, sex="Male", host_factors=[])
    base.update(kw)
    return assess_pathogenicity(**base)


def test_single_cons_bottle_with_a_central_line_is_not_dismissed():
    r = _patho(host_factors=["Central line / PICC"], blood_source="Single bottle positive")
    assert r["score"] >= 45 and "SKIN_FLORA_DEVICE_UNRESOLVED" in r["special_flags"]
    assert any("CRBSI" in x for x in r["recommendations_en"])


def test_cons_with_unknown_bottle_count_says_repeat_not_do_not_treat():
    r = _patho(blood_source="مش محدد")
    assert r["category"] == "LIKELY_CONTAMINANT" and "Repeat" in r["verdict"]
    assert any("positive sets" in m for m in r["missing_inputs"])


def test_aspirated_abscess_is_a_purulent_infection():
    r = _patho(specimen="Pus", organism="Staphylococcus aureus", symptoms=[],
               wound_type="Abscess (aspirated pus)")
    assert r["category"] == "TRUE_INFECTION"


def test_count_parser_honours_less_than_and_more_than():
    from cdss.organisms.pathogenicity import _parse_pus
    assert _parse_pus("<5") < 5 and _parse_pus("<10") < 10
    assert _parse_pus(">10") > 10 and _parse_pus("10+") > 10
    assert _parse_pus("5-10") == 10 and _parse_pus("أقل من 5") < 5


def test_gbs_bacteriuria_in_pregnancy_is_never_called_a_contaminant():
    r = _patho(specimen="Urine", organism="Streptococcus agalactiae", colony_count_text="10^4", symptoms=[],
               host_factors=["Pregnant"], sex="Female", age=28)
    assert r["category"] == "GBS_PREGNANCY_IAP" and "INTRAPARTUM" in r["verdict"]
    assert "CONTAMINANT" not in r["verdict"]
    # The final checklist knows the category: it must not read as "supports treatment".
    src = (ROOT / "cdss" / "astqc" / "final_checklist.py").read_text(encoding="utf-8")
    assert '"GBS_PREGNANCY_IAP"' in src


def test_never_contaminant_factor_is_english():
    r = _patho(organism="Staphylococcus aureus", blood_source="Single bottle positive")
    assert r["factors_pos"] and not any(AR.search(f) for f in r["factors_pos"])


# ── 5. stewardship panels ────────────────────────────────────────────────────
def test_iv_ampicillin_steps_down_to_oral_amoxicillin():
    from cdss.stewardship.iv_po import evaluate_iv_po_switch
    r = evaluate_iv_po_switch("Ampicillin", "Urinary Tract Infection", True, True, True, 3)
    assert r["can_switch"] and r["matched_drug"] == "Amoxicillin"
    r = evaluate_iv_po_switch("Cefazolin", "Skin", True, True, True, 3)
    assert r["matched_drug"] == "Cephalexin"


def test_severity_reads_the_host_factor_labels_the_ui_sends():
    from cdss.stewardship.severity import suggest_severity
    assert suggest_severity("Urine", 30, "Female", False, False, None, ["Neutropenia"], [])["suggested"] == "severe"
    assert suggest_severity("Urine", 30, "Female", False, False, None, ["Renal transplant"], [])["suggested"] \
        == "moderate"
    assert suggest_severity("Urine", 30, "Female", False, False, None,
                            ["Urinary obstruction / Stone / Stent"], [])["suggested"] == "moderate"
    assert suggest_severity("Urine", 30, "Female", False, False, None, [], [])["suggested"] == "mild"
