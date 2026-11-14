"""Golden output of the renderers and of the pathogenicity engine (v6.7).

generate_pdf_html_report() (1,000 lines) and assess_pathogenicity() (890 lines)
were split into section / per-specimen functions on 2026-11-14. The split was
verified byte-for-byte against the pre-split code on 600 report cases (English
and Arabic HTML, text report, decision-tree image) and 40,000 random
pathogenicity inputs. This test keeps that guarantee for later edits: a
renderer or a score that changes shows up here, case by case.

A change that is MEANT to alter the output (new wording, a clinical fix) is
recorded with:

    python tests/test_report_split.py --update

and the diff of tests/golden_outputs.json is reviewed with the change.

Images are not in the snapshot: their bytes depend on the fonts installed on
the machine, so they would differ between this container, GitHub and Windows.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLDEN = Path(__file__).with_name("golden_outputs.json")

_GN = ("Ampicillin", "Amoxicillin + Clavulanic acid", "Cefuroxime sodium", "Ceftriaxone", "Ceftazidime",
       "Cefepime", "Piperacillin + Tazobactam", "Ertapenem", "Meropenem", "Ciprofloxacin", "Levofloxacin",
       "Trimethoprim/Sulfamethoxazole", "Gentamicin", "Amikacin", "Nitrofurantoin", "Fosfomycin",
       "Tigecycline", "Colistin", "Aztreonam", "Ceftazidime + Avibactam", "Doxycycline",
       "Imipenem/Cilastatin", "Cefoperazone + Sulbactam", "Cefixime")
_GP = ("Penicillin", "Oxacillin", "Cefoxitin", "Vancomycin", "Linezolid", "Clindamycin", "Erythromycin",
       "Trimethoprim/Sulfamethoxazole", "Doxycycline", "Fusidic acid", "Rifampicin", "Gentamicin",
       "Ciprofloxacin", "Nitrofurantoin", "Daptomycin", "Teicoplanin", "Ampicillin", "Levofloxacin",
       "Tetracycline", "Cefazolin")
_PA = ("Piperacillin + Tazobactam", "Ceftazidime", "Cefepime", "Aztreonam", "Meropenem",
       "Imipenem/Cilastatin", "Ciprofloxacin", "Levofloxacin", "Amikacin", "Gentamicin", "Tobramycin",
       "Colistin", "Ceftolozane + Tazobactam")


def _panels():
    gn = {d: "S" for d in _GN}
    esbl = dict(gn, **{d: "R" for d in ("Ampicillin", "Cefuroxime sodium", "Ceftriaxone", "Ceftazidime",
                                        "Cefepime", "Aztreonam", "Ciprofloxacin", "Levofloxacin")})
    cre = dict(esbl, **{d: "R" for d in ("Ertapenem", "Meropenem", "Imipenem/Cilastatin",
                                         "Piperacillin + Tazobactam", "Amoxicillin + Clavulanic acid")})
    gp = {d: "S" for d in _GP}
    mrsa = dict(gp, **{d: "R" for d in ("Penicillin", "Oxacillin", "Cefoxitin", "Erythromycin")})
    pa = {d: "S" for d in _PA}
    ab = {d: "R" for d in ("Meropenem", "Imipenem/Cilastatin", "Ampicillin/Sulbactam", "Ceftazidime",
                           "Cefepime", "Ciprofloxacin", "Piperacillin + Tazobactam")}
    ab.update({"Colistin": "S", "Minocycline": "S", "Tigecycline": "S", "Sulbactam + Durlobactam": "S",
               "Amikacin": "I"})
    dtr = dict({d: "R" for d in _PA}, **{"Ceftolozane + Tazobactam": "S", "Colistin": "S", "Cefiderocol": "S"})
    return [("Escherichia coli", gn), ("Escherichia coli", esbl), ("Klebsiella pneumoniae", cre),
            ("Staphylococcus aureus", gp), ("Staphylococcus aureus", mrsa), ("Pseudomonas aeruginosa", pa),
            ("Acinetobacter baumannii", ab), ("Enterococcus faecalis", gp), ("Streptococcus pneumoniae", gp),
            ("Staphylococcus epidermidis", mrsa), ("Enterobacter cloacae", esbl), ("Proteus mirabilis", gn),
            ("Streptococcus agalactiae", gp), ("Pseudomonas aeruginosa", dtr),
            ("Escherichia coli", dict(gn, Ertapenem="R"))]


def _sha(v) -> str:
    return hashlib.sha256((v if isinstance(v, bytes) else str(v).encode("utf-8"))).hexdigest()[:20]


def report_hashes() -> dict:
    import cdss.reports.report_service as RS
    from cdss.common.clinical_utils import Patient
    from cdss.formulary.co_medications import COMMON_MEDS
    from cdss.organisms.pathogenicity import assess_pathogenicity
    from cdss.pipeline import duration_syndrome_key, run_analysis
    from cdss.stewardship.combination import get_combination_therapy
    from cdss.stewardship.duration import get_treatment_duration
    from cdss.stewardship.hepatic import get_hepatic_recommendations

    class _Fixed(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 14, 10, 30)

    hosts = [("adult", {}), ("preg", {"is_pregnant": True}), ("hepC", {"is_hepatic": True, "child_pugh": "C"}),
             ("renal20", {"is_renal": True, "cl_cr": 20}), ("child5", {"age_years": 5}),
             ("infant", {"age_years": 0, "age_months": 2}),
             ("meds_hepB", {"is_hepatic": True, "child_pugh": "B", "current_meds": list(COMMON_MEDS)}),
             ("preg_renal", {"is_pregnant": True, "is_renal": True, "cl_cr": 35,
                             "allergies": ["Penicillin — mild / delayed rash"]})]
    rng = random.Random(7)
    out = {}
    saved = RS.datetime
    RS.datetime = _Fixed
    try:
        for n, ((org, sir), spec, (hl, hk)) in enumerate(
                itertools.product(_panels(), ["Urine", "Blood", "Sputum", "CSF", "Pus"], hosts)):
            uti = rng.choice([None, "upper", "cystitis"]) if spec == "Urine" else None
            carb = rng.choice([None, "KPC", "OXA-48", "MBL"])
            sev = rng.choice(["mild", "moderate", "severe"])
            cc, sym, pus = (rng.choice(["10^5", "10^4", "", "Heavy growth"]),
                            rng.choice([[], ["Fever"], ["Fever", "Dysuria"]]), rng.choice(["<5", "20-25", ""]))
            if n % 4:
                continue                     # every 4th case: 150 of the 600 verified at the split
            p = Patient(**{"age_years": 45, "sex": "Female", **hk})
            r = run_analysis(p, org, spec, sir, uti_syndrome=uti, carbapenemase_type=carb)
            dur = get_treatment_duration(specimen=spec, organism=org,
                                         syndrome=duration_syndrome_key(r.get("syndrome"), uti, spec),
                                         age=p.age_years, sex="Female", is_renal=p.is_renal,
                                         phenotypes=r["phenotypes"], severity=sev)
            combo = get_combination_therapy(r["phenotypes"], is_pregnant=p.is_pregnant, age_years=p.age_years,
                                            age_months=p.age_months, is_renal=p.is_renal, cl_cr=p.cl_cr,
                                            is_hepatic=p.is_hepatic, organism=org, carbapenemase_type=carb)
            hep = get_hepatic_recommendations(r["allowed"], p.child_pugh) if p.is_hepatic else None
            patho = assess_pathogenicity(specimen=spec, organism=org, colony_count_text=cc, culture_purity="Pure",
                                         symptoms=sym, pus_cells_text=pus, urinalysis_result="", gram_stain="",
                                         age=p.age_years, sex="Female",
                                         host_factors=(["Pregnant"] if p.is_pregnant else []))
            common = dict(patient_name="Test Patient", age=p.age_years, sex="Female", weight=70,
                          cl_cr=p.cl_cr or 95, is_renal=p.is_renal, is_preg=p.is_pregnant,
                          is_hepatic=p.is_hepatic, allowed=r["allowed"], warned=r["warned"], banned=r["banned"],
                          preg_warn_items=r["preg_warn"], organism=org, specimen=spec, sir_map=sir,
                          interactions=r["interactions"], colony_count="10^5", date_in="2026-11-14",
                          pus_cells="20-25", rbcs="3-5", lab_name="Orange Lab", lab_city="6 October")
            key = f"{n:04d}|{org}|{spec}|{hl}|{uti}|{carb}"
            row = {}
            for lang in ("en", "ar"):
                row["pdf_" + lang] = _sha(RS.generate_pdf_html_report(
                    **common, mdr_result=r["mdr"], esbl_result=r["mechanism"], phenotypes=r["phenotypes"],
                    duration_data=dur if n % 3 else None, combo_suggestions=combo if n % 2 else None,
                    child_pugh=p.child_pugh if p.is_hepatic else "", hepatic_recs=hep,
                    patho_assessment=patho if n % 8 else None, show_commercial_names=(n % 5 == 0),
                    lang=lang, return_html=True, carbapenemase_type=carb, uti_syndrome=uti) or "")
            row["txt"] = _sha(RS.generate_report(**common, patho_assessment=patho if n % 8 else None,
                                                 show_commercial_names=(n % 5 == 0), age_months=p.age_months))
            out[key] = row
    finally:
        RS.datetime = saved
    return out


def patho_hashes(n_cases: int = 3000) -> list:
    import cdss.organisms.pathogenicity as PG
    rng = random.Random(2026)
    orgs = ["Escherichia coli", "Klebsiella pneumoniae", "Staphylococcus aureus", "Staphylococcus epidermidis",
            "Staphylococcus spp.", "Streptococcus agalactiae", "Streptococcus pneumoniae", "Streptococcus spp.",
            "Streptococcus viridans group", "Enterococcus faecalis", "Pseudomonas aeruginosa",
            "Acinetobacter baumannii", "Candida albicans", "Proteus mirabilis", "Salmonella spp.",
            "Corynebacterium spp.", "Gram-negative bacilli", "Haemophilus influenzae", "Bacillus spp.",
            "Listeria monocytogenes", "Neisseria meningitidis", "MRSA", "VRE", "Cutibacterium acnes",
            "Clostridioides difficile"]
    specs = ["Urine", "Blood", "Sputum", "CSF", "Wound Swab", "Pus", "Stool", "Throat swab", "Tracheal aspirate",
             "BAL", "Tissue"]
    counts = ["", "10^2", "10^3", "10^4", "5x10^4", "10^5", ">10^5", "100,000", "Heavy growth", "Scanty",
              "No growth", "<10^3", "≥10^5"]
    pus = ["", "<5", "5-10", "20-25", "Numerous", ">50", "0-2", "Many", "100+"]
    ua = ["مش معروف / مش مذكور", "Urinalysis طبيعي", "Pyuria (WBCs > 5/HPF)", "Nitrites Positive", ""]
    gi = ["Fever (> 38°C)", "Bloody diarrhea", "Watery diarrhea", "Vomiting", "Abdominal cramps"]
    sirs = ["Temp > 38°C or < 36°C", "Heart rate > 90 / min", "Resp rate > 20 / min (or PaCO₂ < 32)",
            "WBC > 12k or < 4k (or > 10% bands)"]
    bsrc = ["", "مش محدد", "Single bottle positive", "Multiple bottles positive"]
    sp = ["", "<10", "25", ">25", "10-25", "5"]
    pool = PG.URINE_SYMPTOMS + PG.RESPIRATORY_SIGNS + PG.WOUND_SIGNS + gi
    hosts = PG.HOST_FACTORS_URINE + PG.HOST_FACTORS_OTHER

    def pick(lst, k):
        return rng.sample(lst, min(len(lst), k))

    digests, block = [], hashlib.sha256()
    for n in range(n_cases):
        kw = dict(specimen=rng.choice(specs), organism=rng.choice(orgs), colony_count_text=rng.choice(counts),
                  culture_purity=rng.choice(["Pure growth", "Mixed growth", ""]),
                  symptoms=pick(pool, rng.randint(0, 4)), pus_cells_text=rng.choice(pus),
                  urinalysis_result=rng.choice(ua), gram_stain=rng.choice(PG.GRAM_STAIN_OPTIONS + [""]),
                  age=rng.choice([0, 1, 3, 10, 17, 25, 45, 70, 90]), sex=rng.choice(["Male", "Female"]),
                  host_factors=pick(hosts, rng.randint(0, 3)), sputum_pus_cells=rng.choice(sp),
                  sputum_epithelial=rng.choice(sp), sirs_criteria=pick(sirs, rng.randint(0, 4)),
                  blood_source=rng.choice(bsrc), wound_type=rng.choice(PG.WOUND_TYPES + [""]),
                  collection_method=rng.choice(PG.URINE_COLLECTION_METHODS + [""]))
        block.update(json.dumps(PG.assess_pathogenicity(**kw), sort_keys=True, ensure_ascii=False,
                                default=str).encode("utf-8"))
        if n % 100 == 99:
            digests.append(block.hexdigest()[:20])
            block = hashlib.sha256()
    return digests


def _current() -> dict:
    return {"reports": report_hashes(), "pathogenicity": patho_hashes()}


def test_renderers_match_the_golden_output():
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))["reports"]
    got = report_hashes()
    assert got.keys() == want.keys()
    diff = [(k, f) for k in want for f in want[k] if got[k].get(f) != want[k][f]]
    assert not diff, (f"{len(diff)} rendered outputs changed, e.g. {diff[:5]}. If intended: "
                      "python tests/test_report_split.py --update, and review the diff.")


def test_pathogenicity_matches_the_golden_output():
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))["pathogenicity"]
    got = patho_hashes()
    diff = [i for i, (a, b) in enumerate(zip(want, got)) if a != b]
    assert len(got) == len(want) and not diff, (
        f"pathogenicity output changed in case blocks {diff[:10]} (100 cases each). If intended: "
        "python tests/test_report_split.py --update, and review the diff.")


if __name__ == "__main__":
    if "--update" in sys.argv:
        GOLDEN.write_text(json.dumps(_current(), indent=0, sort_keys=True), encoding="utf-8")
        print("golden outputs re-recorded:", GOLDEN)
    else:
        print("usage: python tests/test_report_split.py --update")
