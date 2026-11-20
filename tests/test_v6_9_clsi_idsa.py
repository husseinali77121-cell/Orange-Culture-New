"""v6.9 (2026-11-14): the program reads by CLSI M100 Ed36 and IDSA AMR Guidance 2026.

The lab owner's decisions on the v6.8 decisions document:
  D1  CLSI M100 Ed36 everywhere (I = CLSI Intermediate; Acinetobacter rows;
      EUCAST-only QC rules retired; CLSI-first references)
  D2  Klebsiella aerogenes is its own organism, an IDSA moderate-risk AmpC
  D3  ciprofloxacin / levofloxacin in a child: a caution (AAP 2016), not a ban
  D4  SDD (susceptible-dose dependent) is entered and shown as its own result
  D5  pivmecillinam, sulopenem, gepotidacin, cefepime-enmetazobactam and IV
      fosfomycin join the formulary with their IDSA 2026 positions
Each test names the decision it holds.
"""
from pathlib import Path

import pytest

from cdss.common.clinical_utils import Patient
from cdss.pipeline import run_analysis

ROOT = Path(__file__).resolve().parents[1]


def _run(org, spec, sir, age=45, sex="Female", **kw):
    host = {k: kw.pop(k) for k in ("is_pregnant", "is_renal", "cl_cr", "weight_kg") if k in kw}
    return run_analysis(Patient(age_years=age, sex=sex, **host), org, spec, sir, **kw)


def _names(items):
    return {d["name"] for d in items}


def _item(items, name):
    return next(d for d in items if d["name"] == name)


# ── D1: CLSI Intermediate ───────────────────────────────────────────────────
@pytest.mark.parametrize("drug,cls,spec,upper,expect", [
    ("Cefazolin", "Cephalosporin", "urine", False, "acceptable for cystitis"),
    ("Cefazolin", "Cephalosporin", "blood", False, "higher-than-normal dose"),
    ("Ciprofloxacin", "Fluoroquinolone", "urine", False, "concentrated in urine"),
    ("Ciprofloxacin", "Fluoroquinolone", "urine", True, "uncertain efficacy"),
    ("Gentamicin", "Aminoglycoside", "blood", False, "uncertain efficacy"),
])
def test_clsi_intermediate_depends_on_class_and_site(drug, cls, spec, upper, expect):
    from cdss.therapy.clsi_categories import intermediate_note
    ar, en = intermediate_note(drug, cls, spec, upper)
    assert expect in en and "CLSI M100" in en and "CLSI M100" in ar
    assert "increased exposure" not in en


def test_an_i_result_carries_the_clsi_note_and_stays_a_caution():
    sir = {"Ampicillin": "R", "Ceftriaxone": "S", "Cefazolin": "I", "Gentamicin": "S",
           "Nitrofurantoin": "S", "Trimethoprim/Sulfamethoxazole": "S"}
    r = _run("Escherichia coli", "Urine", sir)
    it = _item(r["warned"], "Cefazolin")
    assert it["warning_reason"] == "intermediate_culture" and it["culture_sdd"] is False
    assert "acceptable for cystitis" in it["intermediate_note_en"]
    from cdss.therapy.notes import warned_note_for
    assert "CLSI M100" in warned_note_for(it, "en") and "CLSI M100" in warned_note_for(it, "ar")


# ── D4: SDD ──────────────────────────────────────────────────────────────────
def test_sdd_is_read_as_i_but_names_its_regimen():
    sir = {"Ampicillin": "R", "Ceftriaxone": "S", "Ceftazidime": "S", "Meropenem": "S",
           "Piperacillin + Tazobactam": "SDD", "Gentamicin": "S"}
    r = _run("Escherichia coli", "Urine", sir, uti_syndrome="pyelonephritis")
    it = _item(r["warned"], "Piperacillin + Tazobactam")
    assert it["culture_sdd"] is True and it["warning_reason"] == "intermediate_culture"
    assert "4.5 g IV q6h over 3 h" in it["intermediate_note_en"]
    assert "Piperacillin + Tazobactam" not in _names(r["allowed"])


def test_sdd_outside_its_clsi_pairs_asks_to_check_the_reading():
    from cdss.therapy.clsi_categories import intermediate_note
    _ar, en = intermediate_note("Ceftriaxone", "Cephalosporin", "blood", False, sdd=True,
                                organism="Escherichia coli")
    assert "check the reading" in en


def test_sdd_never_reads_as_susceptible_anywhere():
    from cdss.stewardship.duration import _sir_lookup
    from cdss.therapy.clinical_matrix import evaluate
    from cdss.therapy.clsi_categories import canonical_panel, is_sdd, sdd_drugs
    assert is_sdd("SDD") and is_sdd("susceptible-dose dependent") and not is_sdd("S")
    assert canonical_panel({"Cefepime": "SDD", "Meropenem": "S"}) == {"Cefepime": "I", "Meropenem": "S"}
    assert sdd_drugs({" Cefepime ": "SDD"}) == {"Cefepime"}
    assert _sir_lookup("Cefepime", {"Cefepime": "SDD"}) == "I"
    v = evaluate("Cefepime", "Escherichia coli", "Urine", sir="SDD")
    assert v.level != "allow"


def test_ocr_keeps_sdd_and_the_panel_offers_it():
    from cdss.ocr.detect import classify_sir_from_line
    from cdss.ocr.ocr_parsing import normalize_sir_value
    assert classify_sir_from_line("Cefepime  SDD") == "SDD"
    assert normalize_sir_value("SDD") == "I"
    # v7.6: D4 revised (SDD offered only where CLSI defines it). v7.7: revised
    # again by the owner -- the form offers S / I / R only; the laboratory SDD
    # the OCR keeps is shown as I with a note, and stays SDD for the engine.
    from cdss.therapy.clsi_categories import panel_display, sir_options_for
    assert sir_options_for("Cefepime", "Escherichia coli") == ["S", "I", "R"]
    shown, level, note = panel_display("Cefepime", "Escherichia coli", "SDD")
    assert (shown, level) == ("I", "info") and "SDD" in note
    src = (ROOT / "cdss_ui" / "panel_editor.py").read_text(encoding="utf-8")
    assert "page.sir_map = canonical_panel(edited_sir)" in src


# ── D1: Acinetobacter and the retired EUCAST-only QC rules ─────────────────
def test_acinetobacter_by_clsi():
    from cdss.astqc.ast_reportability import check_reportability
    sir = {"Meropenem": "S", "Ampicillin/Sulbactam": "S", "Ceftriaxone": "S", "Doxycycline": "S",
           "Tetracycline": "S", "Minocycline": "S", "Amikacin": "S"}
    r = _run("Acinetobacter baumannii", "Blood", sir)
    banned = {d["name"]: d["category"] for d in r["banned"]}
    assert banned.get("Doxycycline") == "no_breakpoint" and banned.get("Tetracycline") == "no_breakpoint"
    assert _item(r["warned"], "Ceftriaxone")["warning_reason"] == "organism_caution"
    assert "Minocycline" in _names(r["allowed"]) | _names(r["warned"])
    qc = check_reportability("Acinetobacter baumannii", sir)
    ids = {i.get("rule_id") or i.get("id") for i in (qc if isinstance(qc, list) else qc.get("issues", []))}
    assert not any("intr_acinetobacter" in str(i) for i in ids if i)


def test_eucast_only_no_breakpoint_rules_are_retired():
    from cdss.astqc import ast_reportability as RP
    from cdss.guidelines.guideline_registry import RULES
    ids = {r["id"] for r in RP.NO_BREAKPOINT_RULES}
    for gone in ("nobp_nitrofurantoin_non_ecoli", "nobp_imipenem_proteae"):
        assert gone not in ids and gone not in RULES
    assert "nobp_tetracycline_doxycycline_acinetobacter" in ids
    row = RULES["intr_acinetobacter"]
    assert "countersigned_by" not in row and "signature_withdrawn" in row
    assert "NOT a clinician countersignature" in row["owner_approved"]


def test_references_put_clsi_first():
    for f, needle in (("cdss_ui/app.py", "CLSI M100 Ed36 | IDSA AMR Guidance 2026"),
                      ("cdss/reports/pdf_sections.py", "References:</b> CLSI M100 Ed36"),
                      ("cdss/reports/report_service.py", "Guidelines: CLSI M100 Ed36 (breakpoints)")):
        assert needle in (ROOT / f).read_text(encoding="utf-8"), f


# ── D2: Klebsiella aerogenes ────────────────────────────────────────────────
def test_klebsiella_aerogenes_is_an_ampc_organism():
    from cdss.ocr.detect import detect_organism
    from cdss.organisms.organism_profile import ORGANISM_PROFILE
    assert "Klebsiella aerogenes" in ORGANISM_PROFILE
    assert detect_organism("growth of enterobacter aerogenes") == "Klebsiella aerogenes"
    sir = {"Ampicillin": "R", "Cefoxitin": "S", "Ceftriaxone": "S", "Cefepime": "S", "Meropenem": "S"}
    r = _run("Klebsiella aerogenes", "Blood", sir)
    assert {d["name"]: d["category"] for d in r["banned"]}.get("Cefoxitin") == "organism"
    assert _item(r["warned"], "Ceftriaxone")["warning_reason"] == "organism_caution"
    assert [d["name"] for d in r["ranked"]][0] == "Cefepime"


# ── D3: paediatric fluoroquinolones ─────────────────────────────────────────
def test_child_ciprofloxacin_is_an_aap_caution_and_moxifloxacin_stays_out():
    sir = {"Ciprofloxacin": "S", "Moxifloxacin": "S", "Ceftriaxone": "R", "Meropenem": "S"}
    r = _run("Pseudomonas aeruginosa", "Urine", sir, age=9, weight_kg=28)
    cip = _item(r["warned"], "Ciprofloxacin")
    assert cip["warning_reason"] == "child_fq" and "AAP 2016" in cip["clinical_note_en"]
    assert {d["name"]: d["category"] for d in r["banned"]}.get("Moxifloxacin") == "child"


def test_english_note_carries_every_merged_reason():
    sir = {"Ciprofloxacin": "S", "Oxacillin": "S", "Cefazolin": "S", "Vancomycin": "S"}
    r = _run("Staphylococcus aureus", "Blood", sir, age=5)
    cip = _item(r["warned"], "Ciprofloxacin")
    assert "AAP 2016" in cip["clinical_note_en"]


# ── D5: the five IDSA 2026 agents ───────────────────────────────────────────
_NEW = {"Pivmecillinam": "S", "Sulopenem": "S", "Gepotidacin": "S",
        "Cefepime + Enmetazobactam": "S", "Fosfomycin IV": "S"}
_ESBL = {"Ampicillin": "R", "Ceftriaxone": "R", "Ceftazidime": "R", "Cefepime": "R", "Aztreonam": "R",
         "Meropenem": "S", "Ertapenem": "S", "Ciprofloxacin": "R", "Trimethoprim/Sulfamethoxazole": "R",
         "Nitrofurantoin": "S", "Gentamicin": "S", "Fosfomycin": "S"}


def test_esbl_cystitis_ranks_the_idsa_preferred_oral_agents():
    r = _run("Escherichia coli", "Urine", {**_ESBL, **_NEW})
    ranked = [d["name"] for d in r["ranked"]]
    for d in ("Pivmecillinam", "Gepotidacin", "Sulopenem"):
        assert ranked.index(d) < ranked.index("Fosfomycin") < ranked.index("Ertapenem")
    assert "Pivmecillinam" not in {d["name"] for d in r["banned"]}   # an ESBL-stable penicillin


def test_pyelonephritis_keeps_the_cystitis_agents_out():
    r = _run("Escherichia coli", "Urine", {**_ESBL, **_NEW}, uti_syndrome="pyelonephritis")
    banned = {d["name"]: d["category"] for d in r["banned"]}
    assert banned.get("Pivmecillinam") == "uti_upper" and banned.get("Gepotidacin") == "uti_upper"
    # v7.1 (external review): banned for upper UTI -- FDA excludes cUTI and IV
    # step-down, and the program cannot verify IDSA's step-down condition.
    assert banned.get("Sulopenem") == "specimen"
    assert [d["name"] for d in r["ranked"]].index("Cefepime + Enmetazobactam") < 3


def test_carbapenemase_decides_the_new_agents():
    cre = {**_ESBL, "Meropenem": "R", "Ertapenem": "R", "Imipenem/Cilastatin": "R"}
    kpc = _run("Escherichia coli", "Urine", {**cre, **_NEW}, carbapenemase_type="KPC")
    banned = {d["name"] for d in kpc["banned"]}
    assert {"Pivmecillinam", "Sulopenem", "Cefepime + Enmetazobactam"} <= banned
    oxa = _run("Escherichia coli", "Urine", {**cre, **_NEW}, carbapenemase_type="OXA-48")
    assert _item(oxa["warned"], "Pivmecillinam")["warning_reason"] == "idsa_new_agent"


def test_breakpoint_scope_of_the_new_agents():
    kp = _run("Klebsiella spp.", "Urine", {**_ESBL, **_NEW})
    assert _item(kp["warned"], "Pivmecillinam")["warning_reason"] == "no_breakpoint"   # CLSI: E. coli only
    pa = _run("Pseudomonas aeruginosa", "Urine", {"Meropenem": "S", **_NEW})
    pab = {d["name"]: d["category"] for d in pa["banned"]}
    assert pab.get("Pivmecillinam") == "no_breakpoint" and pab.get("Gepotidacin") == "no_breakpoint"
    assert "Cefepime + Enmetazobactam" in _names(pa["allowed"])


def test_iv_fosfomycin_outside_the_urine_is_combination_only():
    r = _run("Escherichia coli", "Blood", {**_ESBL, **_NEW})
    assert "Fosfomycin IV" in _names(r["warned"]) and "Fosfomycin IV" not in _names(r["allowed"])
    from cdss.organisms.clinical_data import INTRINSIC_RESISTANCE
    assert all("Fosfomycin IV" in row for row in INTRINSIC_RESISTANCE.values() if "Fosfomycin" in row)


def test_gepotidacin_from_twelve_and_its_renal_limit():
    r14 = _run("Escherichia coli", "Urine", {**_ESBL, **_NEW}, age=14, weight_kg=45)
    assert "Gepotidacin" in _names(r14["allowed"])
    r10 = _run("Escherichia coli", "Urine", {**_ESBL, **_NEW}, age=10, weight_kg=30)
    assert {d["name"]: d["category"] for d in r10["banned"]}.get("Gepotidacin") == "child"
    ckd = _run("Escherichia coli", "Urine", {**_ESBL, **_NEW}, age=70, is_renal=True, cl_cr=20)
    assert "Gepotidacin" in _names(ckd["banned"])


def test_label_population_note_for_a_man():
    r = _run("Escherichia coli", "Urine", {**_ESBL, **_NEW}, sex="Male")
    piv = _item(r["allowed"], "Pivmecillinam")
    assert "women" in piv["clinical_note_en"]


def test_every_new_agent_has_its_tables():
    from cdss.formulary.abx_guidelines import ABX_GUIDELINES, validate_abx_guidelines
    from cdss.formulary.pregnancy_en import PREG_NOTE_EN
    from cdss.therapy.clinical_matrix import SITE_PENETRATION, SITES
    assert not validate_abx_guidelines()
    for d in _NEW:
        assert d in ABX_GUIDELINES and d in PREG_NOTE_EN
        assert set(SITE_PENETRATION[d]) == set(SITES)
        assert "NOT a clinician countersignature" in ABX_GUIDELINES[d]["dose_owner_approved"]


def test_ampc_cefepime_sdd_follows_idsa_2026():
    """IDSA 2026 (Q2.3): cefepime stays preferred for AmpC-E while the MIC is <=8 (S or SDD)
    unless an ESBL gene is identified -- the 2024 'SDD means co-ESBL, use a carbapenem' is gone.
    It stays a caution: an SDD needs the high-exposure regimen."""
    sir = {"Ampicillin": "R", "Cefoxitin": "R", "Ceftriaxone": "R", "Ceftazidime": "R",
           "Cefepime": "SDD", "Meropenem": "S", "Ciprofloxacin": "R", "Trimethoprim/Sulfamethoxazole": "R"}
    r = _run("Enterobacter cloacae", "Blood", sir)
    fep = _item(r["warned"], "Cefepime")
    assert fep["culture_sdd"] is True
    assert "2 g q8h" in fep["clinical_note_en"] and "preferred" in fep["clinical_note_en"]
    assert "co-ESBL" not in fep["clinical_note_en"]
    for f in ("cdss/stewardship/combination.py", "cdss/resistance/phenotypes.py",
              "cdss/organisms/organism_profile.py", "cdss/therapy/context.py"):
        assert "SDD/I" not in (ROOT / f).read_text(encoding="utf-8"), f
