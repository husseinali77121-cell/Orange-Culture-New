#!/usr/bin/env python3
"""Differential harness: the ORIGINAL single-file app vs this package.

Both are loaded in one process (the old modules are top-level, the new ones
live under `cdss.`), fed identical inputs, and every output is compared deeply:
run_analysis(), the QC run, the final checklist, the text report and the PDF
HTML in both languages.

    python3 tools/differential/diff_engine.py <old_tree> <new_tree> [N_random] [seed] \\
            [--allow allow_release] [--show K] [--no-matrix]

<old_tree> is an unpacked copy of the single-file release (the folder that holds
streamlit_app.py, scenario_matrix.py, ...).  With `--allow allow_release` every
difference must be classified as "stricter or equal" or as one of the documented
fixes; anything else is UNEXPLAINED and the exit code is 1.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import random
import sys
import traceback
from collections import Counter

logging.disable(logging.CRITICAL)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_pos = [a for a in sys.argv[1:] if not a.startswith("--")]
_flag_values = {sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a in ("--allow", "--show")}
_pos = [a for a in _pos if a not in _flag_values]
if len(_pos) < 2:
    raise SystemExit(__doc__)
OLD_TREE, NEW = os.path.abspath(_pos[0]), os.path.abspath(_pos[1])
N_RANDOM = int(_pos[2]) if len(_pos) > 2 else 4000
SEED = int(_pos[3]) if len(_pos) > 3 else 20261112
SHOW = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 6
sys.path.insert(0, NEW)                      # so the classifier can import cdss.*
ALLOW = None
if "--allow" in sys.argv:
    ALLOW = importlib.import_module(sys.argv[sys.argv.index("--allow") + 1])

import load_old as _load_old                 # noqa: E402
_load_old.OLD = OLD_TREE
from load_old import load_old                # noqa: E402


OLD_APP = load_old()
import clinical_utils as OLD_CU      # noqa: E402  (original module)
import final_checklist as OLD_FC     # noqa: E402
import scenario_matrix as OLD_SM     # noqa: E402

sys.path.insert(0, NEW)


class NewNS:
    """Attribute access to the new package using the old monolith's global names."""
    def __init__(self):
        self._map = json.load(open(os.path.join(NEW, "tests", "legacy", "legacy_names.json")))
        self._cache = {}

    def __getattr__(self, name):
        if name.startswith("_") and name in ("_map", "_cache"):
            raise AttributeError(name)
        if name in self._cache:
            return self._cache[name]
        target = self._map.get(name)
        if not target:
            raise AttributeError(f"no legacy name {name!r}")
        mod, _, attr = target.partition(":")
        if mod.startswith("cdss_ui"):
            raise AttributeError(f"{name} is UI-only")
        m = importlib.import_module(mod)
        val = getattr(m, attr) if attr else m
        self._cache[name] = val
        return val


NEW_APP = NewNS()
NEW_CU = importlib.import_module("cdss.common.clinical_utils")
NEW_FC = importlib.import_module("cdss.astqc.final_checklist")


# ───────────────────────── canonicalisation ─────────────────────────────────
def canon(x):
    if isinstance(x, dict):
        return {str(k): canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(canon(v) for v in x)
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if callable(x):
        return f"<fn {getattr(x, '__name__', '?')}>"
    if hasattr(x, "__dict__"):
        return {"__cls__": type(x).__name__, **canon(vars(x))}
    return repr(x)


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__} :: {str(a)[:120]!r} | {str(b)[:120]!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: return f"{path}.{k}: only in NEW :: {str(b[k])[:160]!r}"
            if k not in b: return f"{path}.{k}: only in OLD :: {str(a[k])[:160]!r}"
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d: return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            na = [i.get("name") if isinstance(i, dict) else i for i in a]
            nb = [i.get("name") if isinstance(i, dict) else i for i in b]
            return f"{path}: len {len(a)} != {len(b)} :: OLD {str(na)[:200]} | NEW {str(nb)[:200]}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d: return d
        return None
    if a != b:
        return f"{path}: {str(a)[:200]!r} != {str(b)[:200]!r}"
    return None


# ───────────────────────── case generation ──────────────────────────────────
G = OLD_APP.ABX_GUIDELINES
DRUGS = list(G)
ORGS = list(OLD_APP.ORGANISM_PROFILE)
ODD_ORGS = ["", "Unknown", "klebsiella pneumoniae", "MRSA", "mrsa", "VRE",
            "Staphylococcus aureus (MRSA screen positive)", "Enterococcus faecium",
            "Streptococcus pneumoniae", "streptococcus pyogenes", "E.coli", "e. coli ESBL",
            "Gram-negative bacilli", "Proteus mirabilis", "xyz", "Enterobacter cloacae complex",
            "Staph", "Pseudomonas", "Acinetobacter", "Candida albicans", "Listeria monocytogenes"]
SPECS = list(OLD_APP.SPECIMEN_TYPES)
ODD_SPECS = ["MSU", "Catheter urine", "Blood Culture", "sputum", "csf", "Wound", "Unknown", "",
             "Urine Culture", "High vaginal swab", "Ear swab", "Throat swab", "BAL", "Pus"]
SIR_ODD = ["r", "Resistant", "SDD", "NS", "", "?", None, " S ", "sensitive", "Intermediate", "X"]
MEDS = list(OLD_APP.COMMON_MEDS) if not isinstance(OLD_APP.COMMON_MEDS, dict) else list(OLD_APP.COMMON_MEDS)
ALLERGIES = ["Penicillin", "Penicillin (severe anaphylaxis)", "Cephalosporin", "Sulfa",
             "Fluoroquinolone", "Macrolide", "Ceftazidime", "بنسلين", "none"]


def rand_patient(rng):
    r = rng.random()
    if r < 0.12:
        age = 0
    elif r < 0.22:
        age = rng.randint(1, 7)
    elif r < 0.32:
        age = rng.randint(8, 17)
    else:
        age = rng.randint(18, 92)
    months = None
    if age == 0:
        months = rng.choice([None, 0, 0, 1, 2, 3, 5, 11, 99, -1])
    elif rng.random() < 0.03:
        months = rng.choice([0, 5, 14])
    sex = rng.choice(["Male", "Female"])
    preg = sex == "Female" and 14 <= age <= 50 and rng.random() < 0.35
    if rng.random() < 0.02:
        preg = True                       # contradictory input on purpose
    renal = rng.random() < 0.35
    cl = rng.choice([None, 5, 12, 15, 25, 29.9, 30, 35, 45, 50, 60, 75, 100, 0]) if renal \
        else rng.choice([None, 100, 80, 20])
    hep = rng.random() < 0.3
    cp = rng.choice(["A", "B", "C", "C", "", "x", "b"]) if hep else rng.choice(["A", "C"])
    meds = rng.sample(MEDS, k=rng.choice([0, 0, 1, 2, 4]))
    allergies = rng.sample(ALLERGIES, k=rng.choice([0, 0, 0, 1, 2]))
    kw = dict(age_years=age, age_months=months, sex=sex, is_pregnant=preg, is_renal=renal,
              cl_cr=cl, is_hepatic=hep, child_pugh=cp, current_meds=meds, allergies=allergies)
    if rng.random() < 0.02:
        kw["age_years"] = None
    return kw


def rand_panel(rng, organism=None):
    k = rng.choice([0, 1, 3, 6, 10, 14, 20, 30, len(DRUGS)])
    drugs = rng.sample(DRUGS, k=min(k, len(DRUGS)))
    w = rng.choice([(6, 1, 3), (3, 1, 6), (1, 0, 9), (9, 1, 0), (1, 3, 1)])
    sir = {}
    for d in drugs:
        sir[d] = rng.choices(["S", "I", "R"], weights=w)[0]
        if rng.random() < 0.02:
            sir[d] = rng.choice(SIR_ODD)
        if rng.random() < 0.01:
            sir[" " + d + " "] = sir.pop(d)
    if rng.random() < 0.15:
        sir["D-test"] = rng.choice(["Positive", "Negative", "", "pos"])
    if rng.random() < 0.05:
        sir["Penicillinase"] = rng.choice(["Negative", "Positive"])
    return sir


def cases():
    rng = random.Random(SEED)
    # A. the project's own scenario matrix, each with one random host context
    for c in ([] if "--no-matrix" in sys.argv else OLD_SM.build_matrix()):
        org, spec, sir = c["organism"], c["specimen"], dict(c["sir_map"])
        yield ("matrix:" + c.get("id", f"{org}|{spec}|{c.get('archetype')}"),
               rand_patient(rng) if rng.random() < 0.7 else dict(age_years=40, sex="Male"),
               org, spec, sir, None, None)
    # B. random panels over every organism, host and option
    for i in range(N_RANDOM):
        org = rng.choice(ORGS) if rng.random() < 0.85 else rng.choice(ODD_ORGS)
        spec = rng.choice(SPECS) if rng.random() < 0.85 else rng.choice(ODD_SPECS)
        ct = rng.choice([None, None, None, "KPC", "OXA-48", "MBL", "NDM", "unknown", "kpc"])
        uti = rng.choice([None, None, "cystitis", "upper", "pyelonephritis", "lower", "x"])
        yield (f"rand:{i}", rand_patient(rng), org, spec, rand_panel(rng, org), ct, uti)


# ───────────────────────── per-case evaluation ──────────────────────────────
def evaluate(app, cu, fc, pk, org, spec, sir, ct, uti):
    out = {}
    patient = cu.Patient(**pk)
    try:
        res = app.run_analysis(patient, org, spec, dict(sir), carbapenemase_type=ct, uti_syndrome=uti)
    except Exception as e:                                      # compare exception type too
        return {"EXC:run_analysis": f"{type(e).__name__}: {e}"}
    out["run_analysis"] = res
    k = patient.as_kwargs()
    al, wa, ba, pw = res["allowed"], res["warned"], res["banned"], res["preg_warn"]

    def safe(name, fn):
        try:
            out[name] = fn()
        except Exception as e:
            out[name] = f"EXC {type(e).__name__}: {e}"

    safe("qc", lambda: app.run_ast_qc(org, dict(sir), spec))
    safe("qc_conf", lambda: app.compute_qa_confidence(out["qc"] if isinstance(out.get("qc"), list) else [], dict(sir), org))
    safe("drop_intrinsic", lambda: app._drop_intrinsic(list(sir), org))
    safe("hide_urine_only", lambda: app._hide_urine_only(list(DRUGS), spec))
    safe("hepatic_recs", lambda: app.get_hepatic_recommendations(al, k["child_pugh"]))
    safe("deesc", lambda: app.evaluate_deescalation(al, res["phenotypes"], 72, True, (res["mdr"] or {}).get("level")))
    safe("patient_ctx", lambda: app.validate_patient_context(k["age"], k["sex"], k["is_preg"], k["cl_cr"], k["age_months"]))
    safe("checklist", lambda: fc.build_final_checklist(org, spec, dict(sir), al, wa, ba,
                                                       out["qc"] if isinstance(out.get("qc"), list) else [],
                                                       preg_warn=pw))
    for lang in ("ar", "en"):
        safe(f"notes_{lang}", lambda: [app.warned_note_for(w, lang) for w in wa])
    common = dict(colony_count="10^5", date_in="2026-11-12", pus_cells="10-15", rbcs="0-2",
                  lab_name="Lab", lab_city="City")
    safe("text_report", lambda: app.generate_report(
        "P", k["age"], k["sex"], 70.0, k["cl_cr"], k["is_renal"], k["is_preg"], k["is_hepatic"],
        al, wa, ba, pw, org, spec, res["interactions"], dict(sir), **common))
    for lang in ("ar", "en"):
        safe(f"pdf_html_{lang}", lambda: app.generate_pdf_html_report(
            "P", k["age"], k["sex"], 70.0, k["cl_cr"], k["is_renal"], k["is_preg"], k["is_hepatic"],
            al, wa, ba, pw, org, spec, dict(sir), res["interactions"], res["mdr"], res["mechanism"],
            res["phenotypes"], duration_data=res["duration"], combo_suggestions=res["combinations"],
            child_pugh=k["child_pugh"], lang=lang, return_html=True, **common))
    return out


def scrub(x):
    """Remove volatile text (timestamps) from rendered documents."""
    import re
    if isinstance(x, str):
        x = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?", "<TS>", x)
        x = re.sub(r"\d{2}/\d{2}/\d{4}( \d{2}:\d{2})?", "<TS>", x)
        return x
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items()}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


def main():
    total = same = 0
    kinds = Counter()
    shown = Counter()
    for cid, pk, org, spec, sir, ct, uti in cases():
        total += 1
        try:
            o = scrub(canon(evaluate(OLD_APP, OLD_CU, OLD_FC, pk, org, spec, sir, ct, uti)))
            n = scrub(canon(evaluate(NEW_APP, NEW_CU, NEW_FC, pk, org, spec, sir, ct, uti)))
        except Exception:
            traceback.print_exc()
            kinds["HARNESS-ERROR"] += 1
            continue
        if o == n:
            same += 1
            continue
        d = first_diff(o, n) or "?"
        label = "UNEXPLAINED"
        if ALLOW is not None:
            label = ALLOW.classify(o, n, dict(patient=pk, organism=org, specimen=spec, sir=sir,
                                              carbapenemase_type=ct, uti_syndrome=uti)) or "UNEXPLAINED"
        kinds[label] += 1
        if label == "UNEXPLAINED" and ALLOW is not None and getattr(ALLOW, "WHY", None):
            print(f"   WHY[{cid}]: {ALLOW.WHY}")
        if shown[label] < SHOW:
            shown[label] += 1
            print(f"\n[{label}] {cid}  org={org!r} spec={spec!r} ct={ct} uti={uti}\n   patient={pk}\n   sir={dict(list(sir.items())[:12])}\n   {d}")
    print("\n" + "=" * 72)
    print(f"cases: {total}   identical: {same}   different: {total - same}")
    for k, v in kinds.most_common():
        print(f"   {v:6d}  {k}")
    bad = kinds.get("UNEXPLAINED", 0) + kinds.get("HARNESS-ERROR", 0)
    print("RESULT:", "IDENTICAL / ALL DIFFERENCES EXPLAINED" if not bad else f"{bad} UNEXPLAINED")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
