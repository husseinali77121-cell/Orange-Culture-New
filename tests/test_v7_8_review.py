"""v7.8 (2026-11-20): protection against conflicting inputs and conflicting rules,
and the external review of v7.7.

The owner's request: the rules must not break or contradict each other while a
case and its culture are entered, and the inputs must not contradict each other.

  INPUTS (data_consistency.check_case_inputs -> data_issues -> V10)
    impossible (blocks, cannot be confirmed): pregnancy for a male or under 10;
      the "Pregnant" host factor without the pregnancy flag (the score assumed
      pregnancy, the drug-safety gates did not); a negative CrCl; "Asymptomatic"
      together with symptoms
    implausible (blocks until THAT issue is confirmed): weight for age, CrCl >
      250, pregnancy outside 12-55, and the entry disagreeing with the report
      the OCR read (organism, specimen, sex, age, "no growth")
  RULES
    V16 the rule base itself: matrix proofs, an OCR alias naming two drugs, a
        line-listed drug the organism resists, SDD / PL3 tables disagreeing
    V17 every case's FINAL lists keep the core facts: no intrinsic resistance,
        nothing the site / host matrix denies; a check that cannot run fails closed
  REVIEW OF v7.7 (each confirmed on the code first)
    OCR read by position + review + mandatory confirmation (V15) -- see
    tests/test_v7_8_ocr.py; registry counters split; the auth store restricted
    with a verified NTFS ACL on Windows; test groups with JUnit XML; stale SDD
    comments and the redundant page.sdd_read removed.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.common.data_consistency import check_case_inputs, same_organism  # noqa: E402
from cdss.common.util import best_default_index  # noqa: E402
from cdss.pipeline import run_analysis  # noqa: E402
from cdss.validation import case_validator as CV  # noqa: E402
from cdss.validation.case_validator import rule_base_integrity, validate_case  # noqa: E402

S, R = "S", "R"
PANEL = {"Nitrofurantoin": S, "Amikacin": S, "Ciprofloxacin": R, "Imipenem/Cilastatin": S}
EXPORTS = ("TXT", "Download PDF", "تنزيل الصورة")


def _codes(issues):
    return {i["code"]: i["blocking"] for i in issues}


def _page(panel=PANEL, org="E. coli", spec="Urine", script=None, report=None):
    from support.ui_harness import payload, run_page
    pl = payload(org, spec, panel, age=40, sex="Female")
    pl["patient"].update(report or {})
    return run_page(pl, runs=2, script=script)


def _downloads(trace):
    from support.ui_harness import calls
    return [c[1][0] for c in calls(trace, "download_button") if any(k in c[1][0] for k in EXPORTS)]


# ═════════════════════════ INPUT CONFLICTS ══════════════════════════════════
@pytest.mark.parametrize("patient,kw,code,confirmable", [
    (Patient(age_years=30, sex="Male", is_pregnant=True), {}, "INPUT_PREGNANCY_MALE", False),
    (Patient(age_years=5, sex="Female", is_pregnant=True), {}, "INPUT_PREGNANCY_AGE", False),
    (Patient(age_years=58, sex="Female", is_pregnant=True), {}, "INPUT_PREGNANCY_AGE_UNUSUAL", True),
    (Patient(age_years=30, sex="Female", host_factors=["Pregnant"]), {},
     "INPUT_PREGNANT_HOST_ONLY", False),
    (Patient(age_years=4, sex="Male", weight_kg=95), {}, "INPUT_WEIGHT_AGE", True),
    (Patient(age_years=40, sex="Male", weight_kg=8), {}, "INPUT_WEIGHT_AGE", True),
    (Patient(age_years=40, sex="Male", cl_cr=-5), {}, "INPUT_CRCL_NEGATIVE", False),
    (Patient(age_years=40, sex="Male", cl_cr=400), {}, "INPUT_CRCL_HIGH", True),
    (Patient(age_years=40, sex="Female"), {"symptoms": ["Asymptomatic", "Fever (> 38°C)"]},
     "INPUT_SYMPTOMS_CONTRADICT", False),
    (Patient(age_years=40, sex="Female"), {"report": {"Organism": "Klebsiella pneumoniae"}},
     "INPUT_REPORT_ORGANISM", True),
    (Patient(age_years=40, sex="Female"), {"report": {"Specimen": "Blood"}},
     "INPUT_REPORT_SPECIMEN", True),
    (Patient(age_years=40, sex="Female"), {"report": {"Sex": "Male"}}, "INPUT_REPORT_SEX", True),
    (Patient(age_years=40, sex="Female"), {"report": {"Age": 72}}, "INPUT_REPORT_AGE", True),
    (Patient(age_years=40, sex="Female"), {"report": {"NoGrowth": True}},
     "INPUT_REPORT_NO_GROWTH", True),
])
def test_each_input_conflict_blocks_and_only_the_plausible_ones_can_be_confirmed(
        patient, kw, code, confirmable):
    r = run_analysis(patient, "E. coli", "Urine", dict(PANEL),
                     symptoms=kw.get("symptoms"), report_fields=kw.get("report"))
    assert r["data_blocked"] and _codes(r["data_issues"]).get(code) is True
    r2 = run_analysis(patient, "E. coli", "Urine", dict(PANEL), symptoms=kw.get("symptoms"),
                      report_fields=kw.get("report"), consistency_confirmed={code})
    assert _codes(r2["data_issues"])[code] is (not confirmable)
    if confirmable:
        assert not r2["data_blocked"]
        line = [x for x in r2["data_issues"] if x["code"] == code][0]
        assert line["confirmed"] and "confirmed by the physician" in line["confirmed_en"]


def test_a_coherent_case_raises_nothing():
    pt = Patient(age_years=40, sex="Female", weight_kg=68, cl_cr=90, is_pregnant=True,
                 host_factors=["Pregnant"])
    r = run_analysis(pt, "E. coli", "Urine", dict(PANEL), symptoms=["Dysuria / Frequency / Urgency"],
                     report_fields={"Organism": "Escherichia coli", "Specimen": "Urine (Mid stream)",
                                    "Sex": "Female", "Age": 40})
    assert r["data_issues"] == [] and not r["data_blocked"]


def test_confirming_one_issue_does_not_confirm_another():
    pt = Patient(age_years=4, sex="Male", weight_kg=95)
    rep = {"Organism": "Klebsiella pneumoniae"}
    r = run_analysis(pt, "E. coli", "Urine", dict(PANEL), report_fields=rep,
                     consistency_confirmed={"INPUT_WEIGHT_AGE"})
    assert _codes(r["data_issues"]) == {"INPUT_WEIGHT_AGE": False, "INPUT_REPORT_ORGANISM": True}
    assert r["data_blocked"]


def test_same_organism_reads_names_the_way_reports_write_them():
    assert same_organism("E. coli", "Escherichia coli")
    assert same_organism("Klebsiella pneumoniae", "Klebsiella spp.")
    assert not same_organism("Klebsiella pneumoniae", "E. coli")
    assert not same_organism("Staphylococcus aureus", "Staphylococcus epidermidis")


def test_the_report_default_is_chosen_by_meaning_never_silently_the_first_option():
    # it used to need the exact string: "Wound swab" opened as Urine (the first option)
    import support.ui_harness  # noqa: F401  (installs the fake streamlit first)
    from cdss_ui.inputs import _same_specimen
    specimens = ["Urine", "Blood", "Sputum", "Wound Swab", "Pus"]
    assert best_default_index(specimens, "Wound swab") == 3
    assert best_default_index(specimens, "wound swab (left leg)", match=_same_specimen) == 3
    orgs = ["E. coli", "Klebsiella spp.", "Staphylococcus aureus", "Staphylococcus epidermidis"]
    assert best_default_index(orgs, "Klebsiella pneumoniae", match=same_organism) == 1
    # two candidates: no guess -- index 0, and the input check flags the difference
    assert best_default_index(orgs, "Staphylococcus", match=same_organism) == 0
    assert _codes(check_case_inputs(Patient(age_years=40), organism="E. coli",
                                    report={"Organism": "Staphylococcus"}))


def test_the_page_blocks_a_pregnant_host_factor_without_the_pregnancy_flag():
    from support.ui_harness import rendered_text
    traces, state, errors = _page(script={"patho_host_sel": ["Pregnant"]})
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "قواعد أمان الأدوية في الحمل مش شغالة" in txt
    assert "مفيش تأكيد يحل محل التصحيح" in txt and _downloads(traces[-1]) == []


def test_the_page_releases_a_report_mismatch_only_after_that_issue_is_confirmed():
    # the page seeds the sex from the report; the operator then changes it
    from support.ui_harness import FILE_HASH, rendered_text
    sex_key = {f"sex_sel_{FILE_HASH[:8]}": "Male"}
    traces, state, errors = _page(script=sex_key)
    assert not errors, errors
    assert "التقرير مكتوب فيه Female" in rendered_text(traces[-1]) and _downloads(traces[-1]) == []
    label = ("أؤكد إكلينيكياً صحة الإدخال رغم التعارض: التقرير مكتوب فيه Female، والمريض متسجّل "
             "Male. (يُطبع في التقرير)")
    traces, state, errors = _page(script={**sex_key, label: True})
    assert not errors, errors
    assert _downloads(traces[-1])
    assert "confirmed by the physician" in (state.get("_rpt_text") or "")


# ═════════════════════════ OCR REVIEW (V15) ═════════════════════════════════
def test_results_read_from_an_image_need_the_operators_review():
    from cdss_ui.panel_editor import OCR_REVIEW_LABEL
    from support.ui_harness import rendered_text
    traces, state, errors = _page(script={OCR_REVIEW_LABEL: False})
    assert not errors, errors
    assert "not confirmed against the image" in rendered_text(traces[-1])
    assert _downloads(traces[-1]) == []
    traces, state, errors = _page(script={OCR_REVIEW_LABEL: True})
    assert _downloads(traces[-1])


def test_the_page_says_why_an_ocr_result_was_left_empty():
    from support.ui_harness import payload, rendered_text, run_page
    pl = payload("E. coli", "Urine", {"Amikacin": S, "Imipenem/Cilastatin": S}, age=40, sex="Female")
    pl["drugs"] = ["Amikacin", "Imipenem/Cilastatin", "Ciprofloxacin", "Gentamicin"]
    pl["ocr_review"] = {"layout": "cells", "sources": {"Amikacin": "both"},
                        "conflicts": {"Ciprofloxacin": "the report prints it twice: S and R"},
                        "unresolved": {"Gentamicin": "result cell not readable"}}
    traces, state, errors = run_page(pl, runs=2)
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "قراءتين مختلفتين" in txt and "Ciprofloxacin" in txt
    assert "النتيجة مش واضحة" in txt
    assert "Ciprofloxacin" not in state["sir_map_edited"]          # never resolved for you


# ═════════════════════════ RULE CONFLICTS ═══════════════════════════════════
@pytest.fixture
def fresh_rule_base(monkeypatch):
    monkeypatch.setattr(CV, "_RULE_BASE", None)
    yield
    CV._RULE_BASE = None


def test_the_rule_base_is_coherent_today(fresh_rule_base):
    assert rule_base_integrity() == []


def test_an_alias_naming_two_drugs_breaks_the_rule_base(fresh_rule_base, monkeypatch):
    import cdss.ocr.ocr_parsing as OP
    monkeypatch.setattr(OP, "_ABX_ALIAS_SORTED",
                        list(OP._ABX_ALIAS_SORTED) + [("cipro", "Ceftriaxone"), ("cipro", "Ciprofloxacin")])
    found = rule_base_integrity()
    assert any(v["id"] == "V16" and "'cipro'" in v["message"] for v in found)
    assert any(v["id"] == "V16" for v in validate_case({}, specimen="Urine", sir_map={}))


def test_a_first_line_drug_the_organism_resists_breaks_the_rule_base(fresh_rule_base, monkeypatch):
    from cdss.organisms.organism_profile import ORGANISM_PROFILE
    prof = dict(ORGANISM_PROFILE["Klebsiella spp."])
    prof["first_line"] = list(prof.get("first_line") or []) + ["Ampicillin"]
    monkeypatch.setitem(ORGANISM_PROFILE, "Klebsiella spp.", prof)
    assert any("Ampicillin is first-line for Klebsiella spp." in v["message"]
               for v in rule_base_integrity())


def test_sdd_and_pl3_tables_disagreeing_breaks_the_rule_base(fresh_rule_base, monkeypatch):
    import cdss.astqc.phenotype_plausibility as PP
    monkeypatch.setitem(PP.NO_I_PAIRS, "Daptomycin", ("enterococcus faecium", "e. faecium", "vre"))
    assert any("disagree on Daptomycin" in v["message"] for v in rule_base_integrity())


def test_a_rule_base_check_that_crashes_fails_closed(fresh_rule_base, monkeypatch):
    monkeypatch.setattr(CV, "_rule_base_findings", lambda: 1 / 0)
    found = rule_base_integrity()
    assert found and found[0]["id"] == "V16" and "could not run" in found[0]["message"]


HOST = {"age_years": 40, "is_pregnant": False, "is_lactating": False, "cl_cr": None,
        "is_renal": False, "is_hepatic": False, "child_pugh": None}


def _v17(result, specimen):
    return [v["message"] for v in validate_case(dict(result, host=HOST), specimen=specimen,
                                                sir_map={}) if v["id"] == "V17"]


def test_v17_catches_intrinsic_resistance_and_site_denial_in_the_final_lists():
    assert any("intrinsically" in m for m in
               _v17({"allowed": [{"name": "Ampicillin"}], "organism": "Klebsiella spp."}, "Urine"))
    assert any("Nitrofurantoin" in m and "denies" in m for m in
               _v17({"warned": [{"name": "Nitrofurantoin"}], "organism": "E. coli"}, "Blood"))
    assert not _v17({"allowed": [{"name": "Nitrofurantoin"}], "organism": "E. coli"}, "Urine")


def test_v17_fails_closed_when_the_check_cannot_run(monkeypatch):
    import cdss.therapy.clinical_matrix as M

    def boom(*a, **k):
        raise RuntimeError("simulated")
    monkeypatch.setattr(M, "evaluate", boom)
    assert any("could not be re-checked" in m for m in
               _v17({"allowed": [{"name": "Amikacin"}], "organism": "E. coli"}, "Urine"))


def test_v17_checks_the_patient_too():
    preg = dict(HOST, is_pregnant=True)
    msgs = [v["message"] for v in validate_case(
        {"allowed": [{"name": "Doxycycline"}], "organism": "E. coli", "host": preg},
        specimen="Urine", sir_map={}) if v["id"] == "V17"]
    assert msgs, "a drug the matrix denies in pregnancy cannot be offered to a pregnant patient"


# ── the protection layer catches a rule that goes wrong (mutation testing) ──
ORGS = ["E. coli", "Klebsiella spp.", "Pseudomonas aeruginosa", "Proteus mirabilis"]
DRUGS = ["Ampicillin", "Ceftriaxone", "Cefepime", "Meropenem", "Imipenem/Cilastatin", "Amikacin",
         "Gentamicin", "Ciprofloxacin", "Nitrofurantoin", "Fosfomycin",
         "Trimethoprim/Sulfamethoxazole", "Piperacillin + Tazobactam"]


def _engine_case(rng):
    org, spec = rng.choice(ORGS), rng.choice(["Urine", "Blood", "Sputum"])
    panel = {d: rng.choice((S, S, R)) for d in rng.sample(DRUGS, 7)}
    r = run_analysis(Patient(age_years=45, sex="Female", weight_kg=70), org, spec, dict(panel))
    return dict(r, organism=org, host=HOST), spec, panel


@pytest.mark.parametrize("seed", range(4))
def test_real_engine_outputs_pass_and_every_injected_violation_is_caught(seed):
    rng = random.Random(7800 + seed)
    for _ in range(15):
        res, spec, panel = _engine_case(rng)
        clean = [v for v in validate_case(res, specimen=spec, sir_map=panel) if v["severity"] == "error"]
        assert not clean, (res["organism"], spec, panel, clean)
        # 1. a resistant agent slipped into the offered list
        rs = [d for d, v in panel.items() if v == R]
        if rs:
            bad = dict(res, allowed=list(res["allowed"]) + [{"name": rs[0]}])
            assert "V01" in {v["id"] for v in validate_case(bad, specimen=spec, sir_map=panel)}
        # 2. the same agent offered and avoided
        if res["banned"]:
            n = res["banned"][0]["name"]
            bad = dict(res, allowed=list(res["allowed"]) + [{"name": n}])
            ids = {v["id"] for v in validate_case(bad, specimen=spec, sir_map=panel)}
            assert ids & {"V01", "V08", "V17"}, n
        # 3. a urine-only agent offered outside urine
        if spec != "Urine":
            bad = dict(res, warned=list(res["warned"]) + [{"name": "Nitrofurantoin"}])
            assert "V17" in {v["id"] for v in validate_case(bad, specimen=spec, sir_map={})}


# ═════════════════════════ REVIEW OF v7.7 ═══════════════════════════════════
def test_registry_counts_keep_owner_approval_apart_from_clinician_signature():
    from cdss.guidelines.guideline_registry import RULES
    signed = [k for k, v in RULES.items() if v.get("countersigned_by")]
    owner_only = [k for k, v in RULES.items() if v.get("owner_approved") and not v.get("countersigned_by")]
    awaiting = [k for k, v in RULES.items() if not v.get("countersigned_by")]
    assert len(signed) + len(awaiting) == len(RULES)
    assert set(owner_only) <= set(awaiting)
    assert not [k for k in signed if "NOT a clinician" in str(RULES[k]["countersigned_by"])]
    src = (ROOT / "tests" / "legacy" / "test_guidelines.py").read_text(encoding="utf-8")
    for counter in ("primary_verified", "secondary_verified", "pending_heuristic",
                    "clinician_signed", "owner_approved_unsigned", "awaiting_countersignature"):
        assert counter in src


def test_the_auth_store_is_owner_only_and_verified_on_posix(tmp_path):
    import os
    from cdss.security import auth_service as A
    if os.name == "nt":
        pytest.skip("POSIX check")
    f = tmp_path / "store.json"
    f.write_text("{}")
    os.chmod(f, 0o644)
    assert A.restrict_to_owner(str(f)) is True and (os.stat(f).st_mode & 0o077) == 0


def test_the_auth_store_gets_a_verified_ntfs_acl_on_windows(tmp_path, monkeypatch):
    import subprocess
    from cdss.security import auth_service as A
    calls = []
    acl = {"text": "store.json PC\\lab:(F)\n NT AUTHORITY\\SYSTEM:(F)\n BUILTIN\\Administrators:(F)\n"}

    def fake_run(args, **kw):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=acl["text"] if len(args) == 2 else "ok", stderr="")
    monkeypatch.setattr(A, "_IS_WINDOWS", True)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("USERNAME", "lab")
    monkeypatch.setenv("USERDOMAIN", "PC")
    assert A.restrict_to_owner(str(tmp_path / "s.json")) is True
    grant = calls[0]
    assert grant[0] == "icacls" and "/inheritance:r" in grant and "PC\\lab:(F)" in grant
    assert "*S-1-5-18:(F)" in grant and "*S-1-5-32-544:(F)" in grant
    acl["text"] += " Everyone:(R)\n"                      # broader than the owner: not protected
    assert A.restrict_to_owner(str(tmp_path / "s.json")) is False


def test_every_test_file_is_in_exactly_one_group():
    sys.path.insert(0, str(ROOT / "tools"))
    import run_test_groups as G
    assert G.unassigned() == []
    assert "test_legacy_suites.py" in G.GROUPS["legacy"][1]


def test_the_stale_sdd_code_is_gone():
    for p in list((ROOT / "cdss").rglob("*.py")) + list((ROOT / "cdss_ui").rglob("*.py")):
        t = p.read_text(encoding="utf-8")
        assert "page.sdd_read =" not in t and "def reported_sdd" not in t, p
    from cdss.therapy.clsi_categories import sdd_drugs
    assert "never an entry choice" in (sdd_drugs.__doc__ or "") or "never one entered" in sdd_drugs.__doc__
