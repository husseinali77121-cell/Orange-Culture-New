# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""Properties that must hold for EVERY case, checked on seeded random panels.

    partition          every panel drug lands in exactly one bucket
    R never offered    a resistant agent is always banned
    determinism        same input, same output
    order independence shuffling the panel changes nothing
    host monotonicity  adding a risk factor never relaxes any verdict
    purity             no clinical table is modified by an analysis

Set CDSS_FUZZ_CASES to run more cases (default 250; the release run used 20,000+).
"""
import json
import os
import random

import pytest

import cdss.organisms.clinical_data as clinical_data
import cdss.stewardship.combination as combination
import cdss.therapy.tables as tables
from cdss.common.catalog import SPECIMEN_TYPES
from cdss.common.clinical_utils import Patient
from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.pipeline import run_analysis

N = int(os.environ.get("CDSS_FUZZ_CASES", "250"))
RANK = {"allowed": 0, "warned": 1, "preg_warn": 1, "banned": 2}
DRUGS, ORGANISMS = list(ABX_GUIDELINES), list(ORGANISM_PROFILE)
HOST_STEPS = {
    "pregnant": dict(sex="Female", is_pregnant=True),
    "renal, CrCl 15": dict(is_renal=True, cl_cr=15),
    "renal, CrCl unknown": dict(is_renal=True, cl_cr=None),
    "hepatic C": dict(is_hepatic=True, child_pugh="C"),
    "hepatic A": dict(is_hepatic=True, child_pugh="A"),
    "child of 6": dict(age_years=6),
    "teenager": dict(age_years=15),
    "neonate": dict(age_years=0, age_months=0),
    "infant, 5 months": dict(age_years=0, age_months=5),
    "penicillin allergy": dict(allergies=["Penicillin"]),
    "on warfarin": dict(current_meds=["Warfarin (وارفارين)"]),
}


def _buckets(res):
    out = {}
    for b in RANK:
        for it in res[b]:
            out.setdefault(it["name"], []).append(b)
    return out


def _tables_snapshot():
    return json.dumps([ABX_GUIDELINES, ORGANISM_PROFILE, tables.HEPATIC_DOSING,
                       tables.NEONATAL_RESTRICTIONS, combination.COMBINATION_THERAPY,
                       clinical_data.INTRINSIC_RESISTANCE],
                      sort_keys=True, default=str, ensure_ascii=False)


def _cases():
    rng = random.Random(20261112)
    for i in range(N):
        drugs = rng.sample(DRUGS, rng.choice([4, 8, 14, 25, len(DRUGS)]))
        weights = rng.choice([(6, 1, 3), (3, 1, 6), (9, 1, 0), (2, 2, 2)])
        yield dict(
            i=i, organism=rng.choice(ORGANISMS), specimen=rng.choice(SPECIMEN_TYPES),
            sir={d: rng.choices(["S", "I", "R"], weights=weights)[0] for d in drugs},
            base=dict(age_years=rng.choice([25, 40, 70]), sex=rng.choice(["Male", "Female"])),
            opts=dict(uti_syndrome=rng.choice([None, None, "cystitis", "pyelonephritis"]),
                      carbapenemase_type=rng.choice([None, None, None, "KPC", "MBL", "OXA-48"])),
            shuffle_seed=rng.random())


def _run(case, **host):
    return run_analysis(Patient(**{**case["base"], **host}), case["organism"], case["specimen"],
                        dict(case["sir"]), **case["opts"])


@pytest.fixture(scope="module")
def results():
    before = _tables_snapshot()
    out = [(c, _run(c)) for c in _cases()]
    return out, before


def test_partition(results):
    for case, res in results[0]:
        b = _buckets(res)
        wrong = {d: b.get(d) for d in case["sir"] if len(b.get(d, [])) != 1}
        assert not wrong, f"case {case['i']} {case['organism']}/{case['specimen']}: {wrong}"


def test_resistant_is_never_offered(results):
    for case, res in results[0]:
        b = _buckets(res)
        offered = [d for d, v in case["sir"].items() if v == "R" and b[d] != ["banned"]]
        assert not offered, f"case {case['i']}: R but offered: {offered}"


def test_deterministic(results):
    for case, res in results[0][: max(40, N // 5)]:
        again = _run(case)
        assert json.dumps(res, sort_keys=True, default=str) == json.dumps(again, sort_keys=True, default=str)


def test_panel_order_does_not_matter(results):
    for case, res in results[0]:
        items = list(case["sir"].items())
        random.Random(case["shuffle_seed"]).shuffle(items)
        shuffled = run_analysis(Patient(**case["base"]), case["organism"], case["specimen"],
                                dict(items), **case["opts"])
        assert _buckets(shuffled) == _buckets(res), f"case {case['i']} depends on panel order"


@pytest.mark.parametrize("label", list(HOST_STEPS))
def test_a_risk_factor_never_relaxes_a_verdict(results, label):
    for case, res in results[0]:
        base, risk = _buckets(res), _buckets(_run(case, **HOST_STEPS[label]))
        laxer = {d: (base[d][0], risk[d][0]) for d in case["sir"]
                 if RANK[risk[d][0]] < RANK[base[d][0]]}
        assert not laxer, (f"case {case['i']} {case['organism']}/{case['specimen']}: "
                           f"'{label}' relaxed {laxer}")


def test_no_clinical_table_is_mutated(results):
    assert _tables_snapshot() == results[1], "an analysis modified a clinical table in place"
