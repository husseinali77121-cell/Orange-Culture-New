"""v7.5 (2026-11-20): the external review of v7.4.

Each point was reproduced on v7.4 before it was changed; each test below fails there.

  1. A whole-case validation ERROR did not block the exports -- only the
     laboratory-report mismatch did -- and the page never gave the validator the
     safety-layer status, the rendered text or the rendered PDF (V09 / V11 / V12
     were dead on the page). Now every error blocks the text report, the PDF and
     the image; a validation that did not run blocks (fail closed); the text and
     the PDF are re-checked after rendering, and the PDF file is made from the
     very HTML that was checked.
  2. A collection method stated on the laboratory report but NOT entered in the
     case raised nothing. Now a CRITICAL, release-blocking issue.
  3. run_analysis(apply_gate=False) returned degraded=[] -- a result without the
     terminal safety gate looked complete. Now declared, and V09 fires.
  4. tests/legacy/test_guidelines.py used the machine's date: on a UTC runner a
     review dated in Cairo "today" was "in the future". Now the lab's date.
  5. The registry header said "countersigned_by is empty on every row"; QC003 was
     "pending" and signed at once.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.common.clinical_utils import Patient  # noqa: E402
from cdss.common.util import lab_today  # noqa: E402
from cdss.common.data_consistency import check_case_consistency  # noqa: E402
from cdss.guidelines.guideline_registry import RULES  # noqa: E402
from cdss.pipeline import run_analysis  # noqa: E402
from cdss.validation.case_validator import release_decision, validate_case  # noqa: E402

FOLEY, MSU = "Indwelling catheter (Foley)", "Midstream clean-catch"
S, R = "S", "R"
PANEL = {"Nitrofurantoin": S, "Amikacin": S, "Imipenem/Cilastatin": S, "Ceftriaxone": R,
         "Ciprofloxacin": R, "Trimethoprim/Sulfamethoxazole": R}


# ── 1. Validation errors block every export ─────────────────────────────────
def test_a_validation_that_did_not_run_blocks_release():
    assert release_decision(None)["blocked"]
    assert not release_decision([])["blocked"]
    assert not release_decision([{"id": "V04", "severity": "warning", "message": "x"}])["blocked"]
    assert release_decision([{"id": "V01", "severity": "error", "message": "x"}])["blocked"]


def test_the_release_gate_reads_the_validation_not_only_the_data_check():
    from support import fake_streamlit
    fake_streamlit.install()
    from cdss_ui.release_gate import reports_blocked
    assert reports_blocked(SimpleNamespace(data_blocked=False), "x")            # never ran
    # v7.6: the gate reads the ONE release decision made before any button
    assert reports_blocked(SimpleNamespace(data_blocked=False, release={
        "blocked": True, "errors": [{"id": "V01", "severity": "error",
                                     "message": "Ciprofloxacin is offered but tested R."}]}), "x")
    assert not reports_blocked(SimpleNamespace(data_blocked=False,
                                               release={"blocked": False, "errors": []}), "x")


def _ui(monkeypatch=None, **patches):
    from support.ui_harness import payload, run_page
    pl = payload("E. coli", "Urine", PANEL, age=40, sex="Female")
    return run_page(pl, runs=2, script=patches.pop("script", None))


CLINICAL_EXPORTS = ("TXT", "Download PDF", "تنزيل الصورة")


def _clinical_downloads(trace):
    from support.ui_harness import calls
    return [c[1][0] for c in calls(trace, "download_button")
            if any(k in c[1][0] for k in CLINICAL_EXPORTS)]


def test_a_missing_safety_layer_blocks_all_three_exports_on_the_page(monkeypatch):
    # v7.6 (external review of v7.5): "no download button at all" proved nothing
    # for the PDF (its button was never pressed) and would fail on the AST-QA
    # archive PDF, which is not a clinical report. Each export is checked by
    # name, with the PDF actually requested.
    import cdss.pipeline as P
    from support.ui_harness import rendered_text        # installs the fake streamlit first
    import cdss_ui.report_panels as RP
    made = []
    monkeypatch.setattr(RP, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(RP, "pdf_html_to_bytes", lambda h: made.append(h) or b"%PDF-1.4")
    traces, state, errors = _ui(script={"gen_pdf_btn": True})
    assert not errors, errors
    assert _clinical_downloads(traces[-1]) and made          # the control: all three are offered
    monkeypatch.setattr(P, "SAFETY_GATE_AVAILABLE", False)
    made.clear()
    traces, state, errors = _ui(script={"gen_pdf_btn": True})
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "V09" in txt
    for what in ("التقرير النصي موقوف", "تقرير الـ PDF موقوف", "صورة الملخص موقوف"):
        assert what in txt, what
    assert _clinical_downloads(traces[-1]) == [] and not made


def test_a_healthy_case_is_still_released():
    from support.ui_harness import calls, rendered_text
    traces, state, errors = _ui()
    assert not errors, errors
    assert state.get("_rpt_text") and "موقوف" not in rendered_text(traces[-1])
    assert any("TXT" in c[1][0] for c in calls(traces[-1], "download_button"))


def test_the_rendered_text_report_is_checked_before_it_is_offered(monkeypatch):
    import cdss_ui.release as REL
    from support.ui_harness import calls, rendered_text
    monkeypatch.setattr(REL, "generate_report", lambda **k: "RECOMMENDED ANTIBIOTICS\n(nothing)\n")
    traces, state, errors = _ui()
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "V11" in txt and "التقرير النصي موقوف" in txt
    assert not any("TXT" in c[1][0] for c in calls(traces[-1], "download_button"))


def test_the_pdf_file_is_made_from_the_checked_html_and_a_bad_one_is_never_made(monkeypatch):
    import cdss_ui.report_panels as RP
    from support.ui_harness import calls, rendered_text
    made = []
    monkeypatch.setattr(RP, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(RP, "pdf_html_to_bytes", lambda h: made.append(h) or b"%PDF-1.4")
    traces, state, errors = _ui(script={"gen_pdf_btn": True})
    assert not errors, errors
    assert made and "Ranked for:" in made[-1]                      # the checked HTML
    assert any("Download PDF" in c[1][0] for c in calls(traces[-1], "download_button"))

    made.clear()
    import cdss_ui.release as REL
    _real = REL.generate_pdf_html_report
    monkeypatch.setattr(REL, "generate_pdf_html_report",
                        lambda **k: _real(**k).replace("Ranked for:", "ESBL+ "))
    traces, state, errors = _ui(script={"gen_pdf_btn": True})
    assert not errors, errors
    assert not made and "V12" in rendered_text(traces[-1])
    assert not any("Download PDF" in c[1][0] for c in calls(traces[-1], "download_button"))


def test_the_image_lists_are_validated():
    v = validate_case({}, specimen="Urine", sir_map={"Ciprofloxacin": R, "Amikacin": S, "Cefepime": "I"},
                      image_lists={"preferred": ["Ciprofloxacin [W · PO]", "Cefepime [W · IV]"],
                                   "caution": ["Amikacin (Renal dose)"], "avoid": ["Amikacin (R)"]})
    msgs = " ".join(x["message"] for x in v if x["id"] == "V13")
    assert "offers Ciprofloxacin, tested R" in msgs and "offers Cefepime, tested I" in msgs
    assert "Amikacin as both offered and avoided" in msgs
    ok = validate_case({}, specimen="Urine", sir_map={"Cefepime": "I"},
                       image_lists={"preferred": [], "caution": ["Cefepime (I)"], "avoid": []})
    assert not ok                                                    # I under caution is allowed


# ── 2. Collection method stated on the report but not entered ───────────────
@pytest.mark.parametrize("report,entered,hf,codes", [
    (FOLEY, "مش محدد", [], {"SPECIMEN_COLLECTION_NOT_ENTERED"}),
    (FOLEY, "", [], {"SPECIMEN_COLLECTION_NOT_ENTERED"}),
    (MSU, "مش محدد", ["Urinary catheter"], {"SPECIMEN_COLLECTION_NOT_ENTERED",
                                            "SPECIMEN_VOIDED_WITH_CATHETER"}),
    (FOLEY, FOLEY, [], set()),
    (None, "مش محدد", [], set()),
])
def test_the_reviewers_table(report, entered, hf, codes):
    got = check_case_consistency(specimen="Urine", report_collection=report,
                                 entered_collection=entered, host_factors=hf)
    assert {i["code"] for i in got} == codes
    assert all(i["blocking"] and i["severity"] == "critical" for i in got)


def test_an_unentered_method_blocks_the_pipeline_result_and_the_page():
    r = run_analysis(Patient(age_years=40, sex="Female"), "E. coli", "Urine", dict(PANEL),
                     report_collection_method=FOLEY)
    assert r["data_blocked"] and r["data_issues"][0]["code"] == "SPECIMEN_COLLECTION_NOT_ENTERED"
    from support.ui_harness import payload, rendered_text, run_page
    pl = payload("E. coli", "Urine", PANEL, age=40, sex="Female")
    pl["patient"]["CollectionMethod"] = FOLEY
    traces, state, errors = run_page(pl, runs=2, script={"patho_coll_sel": "مش محدد"})
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "CRITICAL" in txt and "مش متحددة" in txt and not state.get("_rpt_text")


# ── 3. A skipped safety gate is declared ────────────────────────────────────
def test_skipping_the_gate_is_degraded_and_fails_validation():
    r = run_analysis(Patient(age_years=45, sex="Male"), "Klebsiella spp.", "Blood",
                     {"Meropenem": "S"}, apply_gate=False)
    assert r["gate_applied"] is False and r["degraded"]
    assert "apply_gate=False" in r["degraded"][0]
    assert any(v["id"] == "V09" for v in validate_case(r, specimen="Blood", sir_map={"Meropenem": "S"}))
    # even an undeclared skip is caught
    assert any(v["id"] == "V09" for v in validate_case({"gate_applied": False}, specimen="Blood",
                                                       sir_map={}))
    healthy = run_analysis(Patient(age_years=45, sex="Male"), "Klebsiella spp.", "Blood",
                           {"Meropenem": "S"})
    assert healthy["gate_applied"] is True and not healthy["degraded"]


# ── 4. The guideline dates are compared in the laboratory's calendar ───────
def test_the_lab_date_is_cairos_whatever_the_machine_clock():
    late_utc = dt.datetime(2026, 11, 19, 23, 30, tzinfo=dt.timezone.utc)
    assert lab_today(late_utc) == dt.date(2026, 11, 20)
    assert lab_today(dt.datetime(2026, 11, 20, 1, 0, tzinfo=dt.timezone.utc)) == dt.date(2026, 11, 20)


def test_the_lab_date_can_be_pinned(monkeypatch):
    monkeypatch.setenv("ORANGE_LAB_TODAY", "2027-01-05")
    assert lab_today() == dt.date(2027, 1, 5)


@pytest.mark.parametrize("tz", ["UTC", "Pacific/Pago_Pago", "Africa/Cairo"])
def test_the_traceability_check_passes_on_any_machine_timezone(tz):
    env = {**os.environ, "TZ": tz}
    env.pop("ORANGE_LAB_TODAY", None)
    out = subprocess.run([sys.executable, str(ROOT / "tests" / "legacy" / "test_guidelines.py")],
                         cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout[-1500:]
    assert "in the future" not in out.stdout


# ── 5. The registry says what it is ─────────────────────────────────────────
def test_no_row_is_both_unverified_and_signed():
    assert not [k for k, v in RULES.items() if v.get("verified") == "pending" and v.get("countersigned_by")]


def test_qc003_keeps_its_old_signature_as_history_and_is_queued():
    row = RULES["QC003"]
    assert "countersigned_by" not in row and "2026-08-03" in row["signature_withdrawn"]
    assert "HEURISTIC" in row["awaiting_countersignature"]


def test_the_registry_header_no_longer_claims_every_row_is_unsigned():
    src = (ROOT / "cdss" / "guidelines" / "guideline_registry.py").read_text(encoding="utf-8")
    assert "empty on every row right now" not in src
    for state in ("countersigned_by", "owner_approved", "awaiting_countersignature",
                  "signature_withdrawn"):
        assert state in src.split("WHY THE SOURCE STRINGS")[0], state
