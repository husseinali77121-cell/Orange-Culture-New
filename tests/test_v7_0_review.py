"""v7.0 (2026-11-19): the external review of a catheter-associated UTI, the EUCAST
audit, the phenotype-plausibility module and the one-page QA / pathogenicity sheets.

The reviewer's case: Klebsiella spp., urine from a Foley catheter, 30-year-old
quadriplegic woman, fever + increased spasticity; panel cephalosporins R/I,
aztreonam S, pip-tazo S, ertapenem I, cefepime "I", gentamicin S, amikacin I,
ofloxacin S, norfloxacin I, nitrofurantoin R, TMP-SMX R.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.pipeline import run_analysis  # noqa: E402

ORG = "Klebsiella spp."
CASE = {"Ampicillin": "R", "Amoxicillin + Clavulanic acid": "R", "Cefazolin": "R", "Cefuroxime": "R",
        "Ceftriaxone": "R", "Cefotaxime": "R", "Ceftazidime": "I", "Cefepime": "I", "Cefoperazone": "R",
        "Aztreonam": "S", "Piperacillin + Tazobactam": "S", "Ertapenem": "I",
        "Gentamicin": "S", "Amikacin": "I", "Ofloxacin": "S", "Norfloxacin": "I",
        "Nitrofurantoin": "R", "Trimethoprim/Sulfamethoxazole": "R"}
HOST = ["Urinary catheter", "Quadriplegia / Tetraplegia (cervical cord injury)"]
FOLEY = "Indwelling catheter (Foley)"


def _case():
    p = Patient(age_years=30, sex="Female", host_factors=list(HOST), collection_method=FOLEY)
    return run_analysis(p, ORG, "Urine", CASE, uti_syndrome="upper")


def _names(items):
    return [i["name"] for i in items]


def _item(r, name):
    for b in ("allowed", "warned", "banned"):
        for i in r[b]:
            if i["name"] == name:
                return b, i
    return None, {}


# ── 1. EUCAST audit ─────────────────────────────────────────────────────────
def test_every_eucast_sourced_rule_has_an_audit_decision():
    from cdss.guidelines.eucast_audit import AUDIT, DECISIONS
    from cdss.guidelines.guideline_registry import RULES
    eucast = {k for k, v in RULES.items() if str(v.get("source", "")).startswith("EUCAST")}
    assert eucast and eucast <= set(AUDIT), sorted(eucast - set(AUDIT))
    assert set(AUDIT) <= set(RULES)
    for k, a in AUDIT.items():
        assert a["decision"] in DECISIONS and a["why"], k
        if a["decision"] != "eucast_only":
            assert a["clsi"].startswith("CLSI"), k


def test_concordant_rules_are_cited_clsi_first():
    from cdss.guidelines.guideline_registry import citation_line
    for rid in ("QC006", "intr_pseudomonas", "rare_colistin_disc", "intr_serratia"):
        assert citation_line(rid).startswith("CLSI"), (rid, citation_line(rid))
    # EUCAST-only logic keeps its EUCAST citation
    assert citation_line("equiv_amc_sam").startswith("EUCAST")


def test_eucast_table_numbers_are_corrected():
    from cdss.guidelines.guideline_registry import RULES
    assert "Table 1" in RULES["intr_serratia"]["locus"]          # v3.3: 1 = Enterobacterales
    assert "Table 2" in RULES["intr_pseudomonas"]["locus"]        # 2 = non-fermenters


def test_serratia_tetracyclines_reported_as_tested_with_caution():
    from cdss.astqc.ast_reportability import check_reportability
    from support.cases import analyse
    ids = {i["id"].split(":")[0] for i in check_reportability(
        "Serratia marcescens", {"Tetracycline": "S", "Doxycycline": "S"})}
    assert "intr_serratia" not in ids
    r = analyse("Serratia marcescens", "Sputum", {"Doxycycline": "S", "Meropenem": "S"})
    b, it = _item(r, "Doxycycline")
    assert b == "warned" and "EUCAST" in (it.get("clinical_note") or it.get("reason_short") or "")


def test_cefoperazone_follows_clsi():
    from cdss.astqc.ast_reportability import check_reportability
    from support.cases import analyse

    def ids(org, panel):
        return {i["id"].split(":")[0] for i in check_reportability(org, panel)}
    assert "nobp_cefoperazone" not in ids(ORG, {"Cefoperazone": "R"})            # CLSI criterion
    assert not ids(ORG, {"Cefoperazone": "R"}) & {"nobp_cefoperazone_non_enterobacterales"}
    assert "nobp_cefoperazone" in ids(ORG, {"Cefoperazone + Sulbactam": "S"})      # no criteria anywhere
    assert "nobp_cefoperazone_non_enterobacterales" in ids("Pseudomonas aeruginosa",
                                                           {"Cefoperazone": "S"})
    r = analyse("Escherichia coli", "Blood", {"Cefoperazone": "S", "Meropenem": "S"})
    assert _item(r, "Cefoperazone")[1].get("warning_reason") == "legacy_breakpoint"


# ── 2. QC flags reach the advisory ──────────────────────────────────────────
def test_no_breakpoint_flags_propagate_to_the_advisory():
    from support.cases import analyse
    r = analyse("Pseudomonas aeruginosa", "Blood", {"Cefoperazone + Sulbactam": "S", "Meropenem": "S"})
    b, it = _item(r, "Cefoperazone + Sulbactam")
    assert b == "banned" and it["category"] == "no_breakpoint"
    # an R with no breakpoint is "uninterpretable", not "MIC above the threshold"
    r = analyse("Pseudomonas aeruginosa", "Urine", {"Gentamicin": "R", "Meropenem": "S"})
    b, it = _item(r, "Gentamicin")
    assert b == "banned" and it["category"] == "no_breakpoint"
    # a guideline-named agent without breakpoint stays a caution
    r = analyse("Stenotrophomonas maltophilia", "Blood", {"Aztreonam + Avibactam": "S"})
    assert _item(r, "Aztreonam + Avibactam")[0] == "warned"


# ── 3. Gram stain wording ───────────────────────────────────────────────────
def test_gram_negative_bacilli_is_offered_for_e_coli_and_klebsiella():
    from cdss.organisms.pathogenicity import gram_choice_in, gram_options_for
    for org in ("Escherichia coli", "E. coli", "Klebsiella spp.", "Klebsiella pneumoniae"):
        assert "WBCs + Gram Negative Bacilli" in gram_options_for(org), org
    opts = gram_options_for("Klebsiella spp.")
    assert gram_choice_in("WBCs + Gram Negative Rods", opts) == "WBCs + Gram Negative Bacilli"
    assert gram_choice_in("WBCs + Gram Positive Cocci", gram_options_for("Escherichia coli")) in (
        None, "WBCs + Gram Positive Cocci")
    assert gram_choice_in("not an option", opts) is None


# ── 4. Phenotype plausibility ───────────────────────────────────────────────
def test_reviewer_panel_triggers_every_plausibility_rule():
    from cdss.astqc.phenotype_plausibility import check_plausibility, reflex_tests
    ids = {f["id"].split(":")[0] for f in check_plausibility(ORG, CASE)}
    # v7.9: PL5 -- the reviewer's isolate is "Klebsiella spp." (genus only)
    assert ids == {"PL1", "PL2", "PL3", "PL4", "PL5"}
    assert {"Meropenem", "Ciprofloxacin", "Levofloxacin"} <= set(reflex_tests(ORG, CASE))
    # a lab-reported SDD is not flagged as "I"
    assert not any(f["id"] == "PL3:Cefepime" for f in check_plausibility(ORG, CASE, sdd={"Cefepime"}))


def test_aztreonam_s_alone_is_the_mbl_pattern_not_implausible():
    from cdss.astqc.phenotype_plausibility import check_plausibility
    mbl = dict(CASE, **{"Piperacillin + Tazobactam": "R", "Ertapenem": "R"})
    ids = {f["id"].split(":")[0] for f in check_plausibility(ORG, mbl)}
    assert "PL1" not in ids and "PL2" in ids


def test_qa_engine_and_completeness_show_the_findings():
    from cdss.astqc.ast_panel_completeness import check_panel_completeness
    from cdss.astqc.ast_qa_engine import run_ast_qa_engine
    from cdss.astqc.inline_qc import run_ast_qc
    cats = {i.category for i in run_ast_qa_engine(ORG, "Urine", CASE)}
    assert "Phenotype Plausibility" in cats
    assert sum(1 for i in run_ast_qc(ORG, CASE, "Urine") if i["severity"] == "error") >= 2
    pc = check_panel_completeness(ORG, "Urine", CASE)
    assert {"Meropenem", "Ciprofloxacin"} <= set(pc.reflex_missing) <= set(pc.missing_primary)


def test_cefepime_i_on_a_no_i_pair_stays_i_and_asks_for_the_mic():
    # v7.0 read this I as SDD. v7.1 (external review): the breakpoint version
    # behind it is unknown -- an old-CLSI I is R today -- so it stays I, is
    # never dosed as SDD on the label alone, and the note asks for the MIC.
    from cdss.therapy.clsi_categories import intermediate_note, sdd_drugs
    assert "Cefepime" not in sdd_drugs(CASE, ORG)
    assert sdd_drugs({"Cefepime": "SDD"}, ORG) == {"Cefepime"}      # what the lab wrote
    ar, en = intermediate_note("Cefepime", "cephalosporin", "urine", True, False, ORG)
    assert "no I category" in en and "MIC" in en and "SDD" in ar
    r = run_analysis(Patient(age_years=40, sex="Female"), "Klebsiella pneumoniae", "Blood",
                     {"Ceftriaxone": "S", "Cefepime": "I", "Meropenem": "S"})
    it = next(i for i in r["warned"] if i["name"] == "Cefepime")
    assert "no I category" in it.get("intermediate_note_en", "") and not it.get("culture_sdd")


# ── 5. The case through the engine ──────────────────────────────────────────
def test_case_engine_output_is_consistent():
    r = _case()
    assert _names(r["allowed"]) == ["Gentamicin"]
    assert _item(r, "Ofloxacin")[1].get("warning_reason") == "fq_low_level"
    # syndrome card follows the catheter and the resolved upper UTI
    assert r["syndrome"]["sub_type"] == "Catheter-associated UTI (CA-UTI)"
    assert "Nitrofurantoin" not in r["syndrome"]["first_choice"]
    # duration follows the route of the agent actually chosen
    d = r["duration"]
    assert d["label"].startswith("Catheter-associated") and d["po_days"] == 0 and d["iv_days"] >= 7
    # low muscle mass: creatinine overestimates GFR -> TDM note on the aminoglycoside
    g = _item(r, "Gentamicin")[1]
    # v7.4: short form beside the agent; the full note (with "monitoring") stays in clinical_note_en
    assert g.get("tdm_note_en") and "TDM" in g["tdm_note_en"] and "monitoring" in g["clinical_note_en"]
    assert r["case"].collection_label == FOLEY


def test_ranking_uses_idsa_alternatives_after_preferred():
    from cdss.stewardship.ranking import rank_sensitive_antibiotics
    r = _case()
    items = r["allowed"] + [i for i in r["warned"] if i["name"] == "Ofloxacin"]
    ranked = rank_sensitive_antibiotics(items, "Urine", ORG, CASE, r["phenotypes"], uti_syndrome="upper")
    assert ranked[0]["name"] == "Gentamicin" and ranked[0]["_guideline_alternative"]
    assert not ranked[0]["_guideline_preferred"]


def test_references_follow_the_patient():
    from cdss.organisms.pathogenicity import assess_pathogenicity
    kw = dict(specimen="Urine", organism=ORG, colony_count_text=">10^5", culture_purity="Pure growth",
              symptoms=["Fever (> 38°C)"], pus_cells_text="40-50", urinalysis_result="", gram_stain="",
              sex="Female")
    adult = assess_pathogenicity(age=30, host_factors=list(HOST), collection_method=FOLEY, **kw)
    assert not any("AAP" in x for x in adult["references"])
    assert any("CA-UTI" in x for x in adult["references"])
    child = assess_pathogenicity(age=1, host_factors=[], collection_method="", **kw)
    assert any("AAP" in x for x in child["references"])
    assert not any("CA-UTI" in x for x in child["references"])


def test_physician_reports_say_mdr_and_name_the_usable_agents():
    from cdss.resistance.mdr import mdr_display_label, physician_mdr_categories, physician_mdr_level
    r = _case()
    if r["mdr"].get("provisional"):
        assert "Possible" in mdr_display_label(r["mdr"])
        assert physician_mdr_level(r["mdr"]) == "MDR"
    cats = physician_mdr_categories(r["mdr"], CASE, {"Gentamicin"})
    assert any(c.startswith("Aminoglycosides (Gentamicin S)") for c in cats)


def test_text_report_uses_the_case_record():
    from cdss.reports.report_service import generate_report
    r = _case()
    txt = generate_report("T", 30, "Female", 60, 95, False, False, False, r["allowed"], r["warned"],
                          r["banned"], r["preg_warn"], ORG, "Urine", r["interactions"], CASE,
                          case=r["case"])
    assert f"Specimen : Urine / {FOLEY}" in txt and "Mid-Stream" not in txt
    assert "Creatinine normal*" in txt
    first = [ln for ln in txt.splitlines() if ln.startswith("First-line :")]
    assert first and not any(d in first[0] for d in ("Amoxicillin + Clavulanic acid", "Cefuroxime"))


# ── 6. Technical ────────────────────────────────────────────────────────────
def test_image_guard_drops_what_the_font_cannot_draw():
    from cdss.reports.image_parts import image_glyph_guard
    out = image_glyph_guard("⁦Klebsiella⁩ ⛔ ok ≥ 10⁵ مرحبا")
    assert "⁦" not in out and "⁩" not in out and "Klebsiella" in out and "≥" in out
    assert "م" in out


def test_bidi_isolates_english_runs_in_arabic_text_only():
    from cdss.reports.html_utils import bidi_isolate
    t = bidi_isolate("مقاومة جوهرية (CLSI M100 Appendix B1): Colistin.")
    assert "⁦(CLSI M100 Appendix B1): Colistin.⁩" in t
    assert bidi_isolate("English only (x)") == "English only (x)"
    t = bidi_isolate("لا breakpoints لـ Klebsiella (fosA كروموسومي).")
    assert "(⁦fosA⁩" in t             # the unmatched bracket stays outside the isolate


def test_sulphamethazone_is_read_as_tmp_smx_and_flagged():
    from cdss.ocr.ocr_parsing import ocr_name_warnings, parse_result_line
    assert parse_result_line("Sulphamethazone   R") == [("Trimethoprim/Sulfamethoxazole", "R")]
    assert ocr_name_warnings("Sulphamethazone R") and not ocr_name_warnings("Ciprofloxacin S")


# ── 7. One-page sheets ──────────────────────────────────────────────────────
def test_render_one_page_shrinks_until_it_fits(monkeypatch):
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
            return _Doc(1 if z <= 0.81 else 2)

    monkeypatch.setattr(fit_page, "_wp", type("W", (), {"HTML": _HTML}))
    monkeypatch.setattr(fit_page, "WEASYPRINT_AVAILABLE", True)

    def build(z):
        seen.append(z)
        return f"<html>z={z};</html>"
    assert fit_page.render_one_page(build) == b"%PDF"
    assert seen == [1.0, 0.93, 0.86, 0.8]          # stopped at the first scale that fits


def test_sheets_scale_their_type():
    from cdss.astqc.confidence import compute_qa_confidence
    from cdss.astqc.inline_qc import run_ast_qc
    from cdss.organisms.pathogenicity import assess_pathogenicity
    from cdss.reports.patho_pdf import generate_patho_report_pdf
    from cdss.reports.qa_pdf import generate_qa_report_pdf
    qc = run_ast_qc(ORG, CASE, "Urine")
    conf = compute_qa_confidence(qc, CASE, ORG)
    h1 = generate_qa_report_pdf(ORG, "Urine", CASE, qc, conf, return_html=True, scale=1.0)
    h2 = generate_qa_report_pdf(ORG, "Urine", CASE, qc, conf, return_html=True, scale=0.8)
    assert "font-size:8.60pt" in h1 and "font-size:6.88pt" in h2
    assert "Implausible beta-lactam phenotype" in h1 and "Required by another result" in h1
    pa = assess_pathogenicity(specimen="Urine", organism=ORG, colony_count_text=">10^5",
                              culture_purity="Pure growth", symptoms=["Fever (> 38°C)"],
                              pus_cells_text="40-50", urinalysis_result="", gram_stain="", age=30,
                              sex="Female", host_factors=list(HOST), collection_method=FOLEY)
    p1 = generate_patho_report_pdf(pa, ORG, "Urine", return_html=True, scale=1.0)
    p2 = generate_patho_report_pdf(pa, ORG, "Urine", return_html=True, scale=0.7)
    assert "font-size:9.00pt" in p1 and "font-size:6.30pt" in p2


# ── 8. The page itself ──────────────────────────────────────────────────────
def test_page_passes_one_case_record_to_the_image(monkeypatch):
    pytest.importorskip("PIL")
    from support.ui_harness import payload, run_page
    import cdss_ui.report_panels as RP
    seen = {}
    orig = RP.generate_decision_tree_image

    def spy(*a, **k):
        seen.update(k)
        return orig(*a, **k)
    monkeypatch.setattr(RP, "generate_decision_tree_image", spy)
    pl = payload(ORG, "Urine", CASE, age=30, sex="Female")
    script = {"patho_coll_sel": FOLEY, "patho_host_sel": list(HOST),
              "patho_symp_urine": ["Fever (> 38°C)"], "patho_calc_btn": True}
    _traces, _state, errors = run_page(pl, runs=3, script=script)
    assert not errors
    assert seen["case"].collection_label == FOLEY and seen["case"].low_muscle_mass
    assert any("Test now" in s for s in seen["first_line"])
    assert any("[A · IV]" in s for s in seen["preferred"])
    # v7.4 (external case review): a tested-S agent that is not appropriate here
    # carries its S result -- it is not a resistant agent.
    assert any("Aztreonam (S · ESBL)" == s for s in seen["contraindicated"])
    # v7.9: the S result is kept and the tag says what settles it (no "R", no gyrA)
    assert "Ofloxacin (S · confirm by CIP/LEV)" in seen["use_caution"]
