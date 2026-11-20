# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""Run the test suite in named groups, one JUnit XML file per group (v7.8).

External review of v7.7: the results must be re-runnable on the same package
and kept by CI, group by group, and a timeout must never count as a pass.

    python tools/run_test_groups.py                 # every group
    python tools/run_test_groups.py --group ocr     # one group
    python tools/run_test_groups.py --out results   # where the XML goes

Exit code 0 only when EVERY group ran to the end and passed. A group that
times out, crashes or collects nothing is a failure. Every test file must be
in exactly one group -- a new file left out of the map fails the run, so no
test can be skipped silently.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# group -> (what it covers, test files). Files are whole: a review file that
# tests several layers sits with the layer it mostly guards.
GROUPS = {
    "rules": ("intrinsic / no-breakpoint / hierarchy rules, therapy rules, rule-base integrity",
              ["test_rules_unit.py", "test_outcome_and_engine.py", "test_aux_tests.py",
               "test_architecture.py", "test_v6_9_clsi_idsa.py"]),
    "clinical_safety": ("pregnancy, children, renal, hepatic; properties on random cases",
                        ["test_properties.py", "test_final_review.py", "test_v7_0_review.py",
                         "test_v7_1_review.py"]),
    "resistance_pathogenicity": ("ESBL / AmpC / CRE / MDR-XDR-PDR; infection vs colonisation",
                                 ["test_v7_2_review.py", "test_v7_3_review.py",
                                  "test_v7_4_review.py"]),
    "ocr": ("reading AST tables from report images (needs Tesseract; skipped without it)",
            ["test_v7_8_ocr.py"]),
    "reports": ("text, PDF and image agree", ["test_report_split.py", "test_fonts.py"]),
    "ui": ("manual entry, QC refresh, the page under a fake Streamlit",
           ["test_ui_page.py", "test_launcher_window.py", "test_v6_7_review.py"]),
    "release_gate": ("no export while a critical error stands; input and rule conflicts",
                     ["test_v7_5_review.py", "test_v7_6_review.py", "test_v7_7_review.py",
                      "test_v7_8_review.py"]),
    "packaging": ("the release files, the upload batches, the EXE spec",
                  ["test_packaging.py", "test_verify_upload.py", "test_upload_instructions.py",
                   "test_partial_upload.py"]),
    "legacy": ("the 21 regression suites written before the package split",
               ["test_legacy_suites.py"]),
}
TIMEOUT_S = {"legacy": 1800, "ocr": 1200}
DEFAULT_TIMEOUT_S = 900


def unassigned() -> list:
    """Test files in tests/ that no group runs (or that a group names but do not exist)."""
    have = {p.name for p in (ROOT / "tests").glob("test_*.py")}
    named = [f for _d, files in GROUPS.values() for f in files]
    dup = sorted({f for f in named if named.count(f) > 1})
    return sorted(have - set(named)) + [f"(missing) {f}" for f in sorted(set(named) - have)] + \
        [f"(in two groups) {f}" for f in dup]


def run(group: str, out: Path) -> dict:
    _desc, files = GROUPS[group]
    xml = out / f"junit-{group}.xml"
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", "-p", "no:cacheprovider",
           f"--junitxml={xml}", *[str(ROOT / "tests" / f) for f in files]]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=TIMEOUT_S.get(group, DEFAULT_TIMEOUT_S))
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        # pytest exit 5 = nothing collected: not a pass
        status = "passed" if r.returncode == 0 else ("no tests" if r.returncode == 5 else "failed")
        return {"group": group, "status": status, "returncode": r.returncode,
                "seconds": round(time.time() - t0, 1), "summary": tail[0], "junit": xml.name}
    except subprocess.TimeoutExpired:
        return {"group": group, "status": "TIMEOUT (counted as a failure)", "returncode": None,
                "seconds": round(time.time() - t0, 1), "summary": "", "junit": xml.name}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--group", choices=sorted(GROUPS), action="append")
    ap.add_argument("--out", default="test-results")
    a = ap.parse_args(argv)
    missing = unassigned()
    if missing:
        print("test files not mapped to exactly one group:", ", ".join(missing))
        return 2
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = [run(g, out) for g in (a.group or GROUPS)]
    (out / "summary.json").write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    for r in results:
        print(f"{r['group']:26} {r['status']:32} {r['seconds']:>7}s  {r['summary']}")
    return 0 if all(r["status"] == "passed" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
