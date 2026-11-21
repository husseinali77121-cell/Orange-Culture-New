"""v7.6 (2026-11-20): the external review of v7.5, and a systematic sweep.

Each point was reproduced on v7.5 before it was changed; each test below fails there.

  1. A collection method stated on the laboratory report but NOT entered could
     be "confirmed" by the physician -- confirming a method nobody entered. Now
     not confirmable: the only way out is to select the method.
  2. Release validation was split: the text was checked inside the text
     section, the PDF only when its button was pressed, the image on its own --
     a PDF failing V12 did not stop the text report. Now ONE decision
     (cdss_ui.release.prepare_release) before any export button.
  3. V11 searched the whole text report: a ranked agent named in a note
     anywhere counted as "in the report". Now read per section, as entries, both
     ways, and the caution section too.
  4. V13 left out the Reserve column of the summary image.
  5. V12 looked for the string "ESBL+" only. Now checked against the mechanism
     result and its evidence level (suspected / confirmed / test negative,
     laboratory-confirmed carbapenemase).
  6. An entered midstream specimen with "Urinary catheter" as a host factor was
     checked only when the OCR had read a method from the report.
  7. Without a tz database the date fell back to a fixed UTC+3 -- one hour wrong
     all winter; tzdata was neither a requirement nor bundled into the EXE.
  8. An invalid ORANGE_LAB_TODAY raised in every caller.
  9. "All three exports blocked" asserted that no download button existed at
     all (rewritten in tests/test_v7_5_review.py).

The sweep (end of file): every V-rule fires on a positive case and stays quiet
on its negative; seeded random cases across organisms, specimens and patients
validate clean end to end; seeded random page runs never offer a clinical export
the release decision blocked.
"""
from __future__ import annotations

import datetime as dt
import logging
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
from cdss.common.data_consistency import check_case_consistency  # noqa: E402
from cdss.common.util import egypt_utc_offset, lab_today  # noqa: E402
from cdss.pipeline import run_analysis  # noqa: E402
from cdss.reports.report_service import generate_pdf_html_report, generate_report  # noqa: E402
from cdss.validation.case_validator import release_decision, validate_case  # noqa: E402

FOLEY, MSU = "Indwelling catheter (Foley)", "Midstream clean-catch"
CATH = "Urinary catheter"
S, R = "S", "R"
PANEL = {"Nitrofurantoin": S, "Amikacin": S, "Imipenem/Cilastatin": S, "Ceftriaxone": R,
         "Ciprofloxacin": R, "Trimethoprim/Sulfamethoxazole": R}
ESBL = {"Ampicillin": R, "Cefuroxime": R, "Ceftriaxone": R, "Cefotaxime": R, "Ceftazidime": R,
        "Cefepime": R, "Ciprofloxacin": R, "Meropenem": S, "Imipenem/Cilastatin": S,
        "Ertapenem": S, "Amikacin": S, "Nitrofurantoin": S, "Fosfomycin": S,
        "Piperacillin + Tazobactam": S}
CRE = dict(ESBL, Meropenem=R, Ertapenem=R, **{"Imipenem/Cilastatin": R})
CONFIRM_REPORT = ("أؤكد إكلينيكياً أن طريقة الجمع المُدخلة هي الصحيحة رغم تقرير المعمل "
                  "(يُطبع في التقرير) — بدون التأكيد أو التصحيح التقارير موقوفة")
CONFIRM_ENTRY = ("أؤكد إكلينيكياً إن العينة فعلاً midstream / تبول رغم تسجيل القسطرة (مثلاً "
                 "القسطرة اتشالت قبل أخذ العينة) — يُطبع في التقرير؛ بدون التأكيد أو التصحيح "
                 "التقارير موقوفة")
CLINICAL_EXPORTS = ("TXT", "Download PDF", "تنزيل الصورة")


def _clinical_downloads(trace):
    from support.ui_harness import calls
    return [c[1][0] for c in calls(trace, "download_button")
            if any(k in c[1][0] for k in CLINICAL_EXPORTS)]


def _page(panel=PANEL, org="E. coli", spec="Urine", runs=2, script=None, report_method=None,
          age=40, sex="Female"):
    from support.ui_harness import payload, run_page
    pl = payload(org, spec, panel, age=age, sex=sex)
    if report_method:
        pl["patient"]["CollectionMethod"] = report_method
    return run_page(pl, runs=runs, script=script)


# ── 1. A method never entered cannot be "confirmed" ─────────────────────────
def test_an_unentered_method_cannot_be_confirmed():
    i = check_case_consistency(specimen="Urine", report_collection=FOLEY,
                               entered_collection="مش محدد", confirmed=True)
    assert [x["code"] for x in i] == ["SPECIMEN_COLLECTION_NOT_ENTERED"]
    assert i[0]["blocking"] and not i[0]["confirmed"] and not i[0]["confirmable"]
    r = run_analysis(Patient(age_years=40, sex="Female"), "E. coli", "Urine", dict(PANEL),
                     report_collection_method=FOLEY, consistency_confirmed=True)
    assert r["data_blocked"]
    # a real mismatch stays confirmable
    j = check_case_consistency(specimen="Urine", report_collection=FOLEY,
                               entered_collection=MSU, confirmed=True)
    assert j and not j[0]["blocking"] and j[0]["confirmable"]


def test_the_page_offers_no_confirmation_for_an_unentered_method():
    from support.ui_harness import rendered_text
    traces, state, errors = _page(report_method=FOLEY,
                                  script={"patho_coll_sel": "مش محدد", CONFIRM_REPORT: True})
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "CRITICAL" in txt and "مفيش تأكيد يحل محلها" in txt
    assert "أؤكد إكلينيكياً" not in txt, "no checkbox for an issue that cannot be confirmed"
    assert _clinical_downloads(traces[-1]) == [] and not state.get("_rpt_text")


# ── 6. Entry vs host factors, with no method read from the report ───────────
def test_an_entered_midstream_with_a_catheter_is_flagged_without_the_ocr():
    pt = Patient(age_years=40, sex="Female", collection_method=MSU, host_factors=[CATH])
    r = run_analysis(pt, "E. coli", "Urine", dict(PANEL))
    assert r["data_blocked"]
    assert [x["code"] for x in r["data_issues"]] == ["SPECIMEN_ENTRY_VOIDED_WITH_CATHETER"]
    r2 = run_analysis(pt, "E. coli", "Urine", dict(PANEL), consistency_confirmed=True)
    assert not r2["data_blocked"]
    # a catheter specimen with a catheter is coherent
    pt3 = Patient(age_years=40, sex="Female", collection_method=FOLEY, host_factors=[CATH])
    assert not run_analysis(pt3, "E. coli", "Urine", dict(PANEL))["data_issues"]


def test_the_page_checks_the_entry_even_when_the_ocr_read_no_method():
    from support.ui_harness import rendered_text
    script = {"patho_coll_sel": MSU, "patho_host_sel": [CATH]}
    traces, state, errors = _page(script=script)
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "CRITICAL" in txt and "القسطرة لسه موجودة" in txt
    assert _clinical_downloads(traces[-1]) == []
    traces, state, errors = _page(script={**script, CONFIRM_ENTRY: True})
    assert not errors, errors
    rpt = state.get("_rpt_text") or ""
    assert "physician confirmed" in rpt and "catheter removed" in rpt
    assert any("TXT" in d for d in _clinical_downloads(traces[-1]))


# ── 2. One release decision before any export button ────────────────────────
def test_a_pdf_that_fails_validation_stops_the_text_report_and_the_image_too(monkeypatch):
    from support.ui_harness import rendered_text
    import cdss_ui.release as REL
    _real = REL.generate_pdf_html_report
    monkeypatch.setattr(REL, "generate_pdf_html_report",
                        lambda **k: _real(**k).replace("Ranked for:", "ESBL+ "))
    traces, state, errors = _page()                      # the PDF button is never pressed
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "V12" in txt and "التقرير النصي موقوف" in txt and "صورة الملخص موقوف" in txt
    assert _clinical_downloads(traces[-1]) == []


def test_a_release_step_that_crashes_blocks_everything(monkeypatch):
    from support.ui_harness import rendered_text
    import cdss_ui.release as REL

    def boom(*a, **k):
        raise RuntimeError("simulated")
    monkeypatch.setattr(REL, "generate_report", boom)
    traces, state, errors = _page()
    assert not errors, errors
    assert "V00" in rendered_text(traces[-1]) and _clinical_downloads(traces[-1]) == []


def test_the_pdf_signature_covers_every_pdf_option():
    from support import fake_streamlit
    fake_streamlit.install()
    from cdss_ui.release import pdf_signature
    page = SimpleNamespace(_rpt_input_hash="h")
    base = {"lang": "ar", "combo": True, "dur": True, "patho": True, "cp": "A", "sev": "x"}
    sigs = {pdf_signature(page, base)}
    for k, v in (("lang", "en"), ("combo", False), ("dur", False), ("patho", False),
                 ("cp", "C"), ("sev", "y")):
        sigs.add(pdf_signature(page, {**base, k: v}))
    assert len(sigs) == 7
    assert pdf_signature(SimpleNamespace(_rpt_input_hash="other"), base) not in sigs


def test_a_clean_validation_is_shown_as_clean_and_a_missing_one_as_a_failure():
    # found by the random page sweep below: the checklist read a clean [] as
    # "validation did not run" (an `x or [V00]` fallback)
    from cdss.validation.case_validator import checklist_item
    assert checklist_item([])["status"] == "pass"
    assert checklist_item(None)["status"] == "fail" and "V00" in checklist_item(None)["detail"]
    from support.ui_harness import rendered_text
    traces, state, errors = _page()
    assert not errors, errors
    txt = rendered_text(traces[-1])
    # v7.9: as a word -- the rendered text also carries the base64 of the tree
    # image, where "V00" can occur by chance (it did when the image changed)
    import re
    assert not re.search(r"\bV00\b", txt) and "كل الفحوصات المتقاطعة سليمة" in txt
    assert any("TXT" in d for d in _clinical_downloads(traces[-1]))


# ── 3. V11 reads each section's entries ─────────────────────────────────────
def _items(*names):
    return [{"name": n} for n in names]


def _text(rec=(), caution=(), tail=""):
    sep2 = "-" * 60
    L = ["SENSITIVITY RESULTS", "=" * 60, "", "RECOMMENDED ANTIBIOTICS", "=" * 60]
    for n in rec:
        L += [f"{n} [Culture: S]", sep2, "Note      : x", ""]
    if caution:
        L += ["", "DOSE ADJUSTMENT / USE WITH CAUTION", "=" * 60]
        for n in caution:
            L += [f"{n} [Culture: S]", sep2, "Reason    : renal", ""]
    return "\n".join(L) + "\n" + tail


def test_v11_a_ranked_agent_mentioned_only_in_a_note_is_missing():
    res = {"ranked": _items("Nitrofurantoin"), "allowed": _items("Nitrofurantoin", "Amikacin")}
    good = _text(rec=("Nitrofurantoin", "Amikacin"))
    assert not [v for v in validate_case(res, specimen="Urine", sir_map=PANEL,
                                         report_text=good) if v["id"] == "V11"]
    bad = _text(rec=("Amikacin",), tail="\nNote : Nitrofurantoin would also be an option.\n")
    v = [x["message"] for x in validate_case(res, specimen="Urine", sir_map=PANEL,
                                             report_text=bad) if x["id"] == "V11"]
    assert any("Nitrofurantoin is ranked" in m for m in v), v


def test_v11_an_entry_the_analysis_does_not_offer_and_a_missing_caution():
    res = {"ranked": [], "allowed": _items("Amikacin"), "warned": _items("Cefepime"),
           "banned": _items("Ciprofloxacin")}
    t = _text(rec=("Amikacin", "Ciprofloxacin"))
    msgs = [x["message"] for x in validate_case(res, specimen="Urine", sir_map=PANEL,
                                                report_text=t) if x["id"] == "V11"]
    assert any("recommends Ciprofloxacin" in m for m in msgs)
    assert any("Cefepime is under caution" in m for m in msgs)
    # the next heading ends the section, whatever it is (no CONTRAINDICATED block)
    t2 = _text(rec=("Amikacin",), caution=("Cefepime",),
               tail="\nPATHOGENICITY ASSESSMENT\n" + "-" * 60 + "\nEvidence : 70/100\n")
    assert not [x for x in validate_case(res, specimen="Urine", sir_map=PANEL,
                                         report_text=t2) if x["id"] == "V11"]


def test_v11_is_quiet_on_real_text_reports():
    for pt, panel in ((Patient(age_years=40, sex="Female"), PANEL),
                      (Patient(age_years=80, sex="Male", weight_kg=50, is_renal=True, cl_cr=25),
                       ESBL)):
        r = run_analysis(pt, "Escherichia coli", "Urine", dict(panel))
        t = generate_report(patient_name="X", age=pt.age_years, sex=pt.sex, weight=70,
                            cl_cr=pt.cl_cr, is_renal=pt.is_renal, is_preg=False, is_hepatic=False,
                            allowed=r["allowed"], warned=r["warned"], banned=r["banned"],
                            preg_warn_items=r["preg_warn"], organism="Escherichia coli",
                            specimen="Urine", interactions=[], sir_map=dict(panel))
        assert not [v for v in validate_case(r, specimen="Urine", sir_map=panel, report_text=t)
                    if v["id"] == "V11"]


# ── 5. V12 against the mechanism result ─────────────────────────────────────
def _pdf(panel, aux=None, carb=None, org="Escherichia coli"):
    pt = Patient(age_years=50, sex="Female")
    r = run_analysis(pt, org, "Urine", dict(panel, **(aux or {})), carbapenemase_type=carb)
    h = generate_pdf_html_report(
        patient_name="X", age=50, sex="Female", weight=70, cl_cr=None, is_renal=False,
        is_preg=False, is_hepatic=False, allowed=r["allowed"], warned=r["warned"],
        banned=r["banned"], preg_warn_items=r["preg_warn"], organism=org, specimen="Urine",
        interactions=[], sir_map=dict(panel), mdr_result=r["mdr"], esbl_result=r["mechanism"],
        phenotypes=r.get("phenotypes"), return_html=True, lang="en", aux_tests=aux or {},
        carbapenemase_type=carb, duration_data={"label": "x", "standard_days": 5})
    return dict(r, aux_tests=aux or {}, carbapenemase_type=carb), h


def _v12(res, html, panel):
    return [v["message"] for v in validate_case(res, specimen="Urine", sir_map=panel,
                                                pdf_html=html) if v["id"] == "V12"]


STATES = [(ESBL, None, None, "Escherichia coli"),
          (ESBL, {"ESBL confirmation": "Positive"}, None, "Escherichia coli"),
          (ESBL, {"ESBL confirmation": "Negative"}, None, "Escherichia coli"),
          (CRE, None, "KPC", "Escherichia coli"),
          (CRE, None, None, "Escherichia coli"),
          (CRE, None, "NDM", "Klebsiella pneumoniae")]


@pytest.mark.parametrize("panel,aux,carb,org", STATES)
def test_v12_is_quiet_on_every_real_mechanism_state(panel, aux, carb, org):
    res, h = _pdf(panel, aux, carb, org)
    assert _v12(res, h, panel) == []


def test_v12_a_suspected_esbl_printed_as_confirmed_is_caught():
    res, h = _pdf(ESBL)
    assert "Suspected ESBL" in h
    bad = h.replace("Suspected ESBL (pattern only, not confirmed)", "ESBL CONFIRMED")
    m = _v12(res, bad, ESBL)
    assert any("evidence level" in x for x in m) and any("without a positive" in x for x in m)


def test_v12_a_negative_confirmatory_test_must_be_printed():
    res, h = _pdf(ESBL, {"ESBL confirmation": "Negative"})
    bad = h.replace("confirmatory test was NEGATIVE", "pattern")
    assert any("evidence level" in x for x in _v12(res, bad, ESBL))


def test_v12_a_confirmed_carbapenemase_must_be_printed_as_confirmed():
    res, h = _pdf(CRE, carb="KPC")
    assert "KPC CONFIRMED" in h
    assert any("KPC" in x for x in _v12(res, h.replace("KPC CONFIRMED", "KPC"), CRE))


# ── 4. V13 covers the Reserve column ────────────────────────────────────────
def test_v13_an_r_agent_in_the_reserve_column_is_an_error():
    sir = {"Meropenem": R, "Amikacin": S}
    v = validate_case({}, specimen="Urine", sir_map=sir,
                      image_lists={"preferred": ["Amikacin [A · IV]"], "caution": [],
                                   "avoid": [], "reserve": ["Meropenem [W · IV]"]})
    assert any(x["id"] == "V13" and "Meropenem" in x["message"] for x in v)
    ok = validate_case({}, specimen="Urine", sir_map=dict(sir, Meropenem=S),
                       image_lists={"preferred": ["Amikacin [A · IV]"], "caution": [],
                                    "avoid": [], "reserve": ["Meropenem [W · IV]"]})
    assert not [x for x in ok if x["id"] == "V13"]


# ── 7-8. The laboratory date ────────────────────────────────────────────────
def test_the_egypt_rule_matches_the_tz_database_hour_by_hour_2023_2035():
    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo("Africa/Cairo")
    except Exception:
        pytest.skip("no tz database on this machine to compare against")
    t = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    bad = []
    while t.year < 2036:
        if egypt_utc_offset(t) != t.astimezone(z).utcoffset():
            bad.append(t)
        t += dt.timedelta(hours=1)
    assert not bad, bad[:5]


def test_without_a_tz_database_a_winter_evening_is_still_the_cairo_date(monkeypatch):
    import zoneinfo

    def missing(key):
        raise zoneinfo.ZoneInfoNotFoundError(key)
    monkeypatch.setattr(zoneinfo, "ZoneInfo", missing)
    monkeypatch.delenv("ORANGE_LAB_TODAY", raising=False)
    # 21:30 UTC on 15 January is 23:30 in Cairo (UTC+2); a fixed +3 said 16 January
    assert lab_today(dt.datetime(2026, 1, 15, 21, 30, tzinfo=dt.timezone.utc)) == dt.date(2026, 1, 15)
    # 21:30 UTC on 15 July is 00:30 on the 16th in Cairo (UTC+3)
    assert lab_today(dt.datetime(2026, 7, 15, 21, 30, tzinfo=dt.timezone.utc)) == dt.date(2026, 7, 16)


def test_an_invalid_date_pin_is_reported_and_ignored(monkeypatch, caplog):
    monkeypatch.setenv("ORANGE_LAB_TODAY", "20-11-2026")
    with caplog.at_level(logging.WARNING):
        d = lab_today()
    assert isinstance(d, dt.date) and "ORANGE_LAB_TODAY" in caplog.text
    monkeypatch.setenv("ORANGE_LAB_TODAY", "2026-11-20")
    assert lab_today() == dt.date(2026, 11, 20)


def test_tzdata_is_required_and_bundled_into_the_exe():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert any(ln.split("#")[0].strip() == "tzdata" for ln in req.splitlines())
    assert '"tzdata"' in (ROOT / "orange_cdss.spec").read_text(encoding="utf-8")


# ── Sweep 1: every V-rule fires on a positive case and stays quiet otherwise ─
def _ids(res, **k):
    k.setdefault("specimen", "Urine")
    k.setdefault("sir_map", {})
    return {v["id"] for v in validate_case(res, **k) if v["severity"] == "error"} | \
        {v["id"] + "w" for v in validate_case(res, **k) if v["severity"] == "warning"}


POSITIVE = {
    "V01": ({"allowed": _items("Ciprofloxacin")}, {"sir_map": {"Ciprofloxacin": R}}),
    "V02": ({"ranked": _items("Amikacin")}, {"sir_map": {}}),
    "V03": ({"allowed": _items("Nitrofurantoin")},
            {"sir_map": {"Nitrofurantoin": S}, "uti_syndrome": "upper"}),
    "V04w": ({"ranked": _items("Nitrofurantoin")},
             {"sir_map": {"Nitrofurantoin": S}, "uti_syndrome": "cuti"}),
    "V05": ({"ranked": _items("Ceftriaxone"), "mechanism": {"probability": "high"}},
            {"sir_map": {"Ceftriaxone": S}}),
    "V06": ({"ranked": _items("Amikacin"), "treatment_gate": {"override": False}},
            {"sir_map": {"Amikacin": S}}),
    "V07": ({"allowed": _items("Amikacin"), "case": SimpleNamespace(low_muscle_mass=True)},
            {"sir_map": {"Amikacin": S}}),
    "V08": ({"allowed": _items("Amikacin"), "banned": _items("Amikacin")},
            {"sir_map": {"Amikacin": S}}),
    "V09": ({"degraded": ["safety_gate unavailable"]}, {}),
    "V10": ({"data_blocked": True}, {}),
    "V11": ({"ranked": _items("Amikacin"), "allowed": _items("Amikacin")},
            {"sir_map": {"Amikacin": S}, "report_text": _text(rec=())}),
    "V12": ({}, {"pdf_html": "<b>ESBL+</b>"}),
    "V13": ({}, {"sir_map": {"Ciprofloxacin": R},
                 "image_lists": {"preferred": ["Ciprofloxacin"]}}),
    "V14": ({"sdd_reported": ["Nitrofurantoin"], "organism": "Escherichia coli"}, {}),   # v7.7
    "V15": ({"ocr_reviewed": False}, {}),                                                  # v7.8
    "V17": ({"allowed": _items("Nitrofurantoin"), "organism": "E. coli",
             "host": {"age_years": 40}}, {"specimen": "Blood", "sir_map": {"Nitrofurantoin": S}}),
}
NEGATIVE = {
    "V01": ({"allowed": _items("Ciprofloxacin")}, {"sir_map": {"Ciprofloxacin": S}}),
    "V02": ({"ranked": _items("Amikacin")}, {"sir_map": {"Amikacin": S}}),
    "V03": ({"allowed": _items("Nitrofurantoin")},
            {"sir_map": {"Nitrofurantoin": S}, "uti_syndrome": "lower"}),
    "V04w": ({"ranked": _items("Nitrofurantoin")},
             {"sir_map": {"Nitrofurantoin": S}, "uti_syndrome": "lower"}),
    "V05": ({"ranked": _items("Ceftriaxone"), "mechanism": {"probability": "low"}},
            {"sir_map": {"Ceftriaxone": S}}),
    "V06": ({"ranked": _items("Amikacin"), "treatment_gate": {"override": True}},
            {"sir_map": {"Amikacin": S}}),
    "V07": ({"allowed": [{"name": "Amikacin", "tdm_note_en": "TDM"}],
             "case": SimpleNamespace(low_muscle_mass=True)}, {"sir_map": {"Amikacin": S}}),
    "V08": ({"allowed": _items("Amikacin"), "banned": _items("Ciprofloxacin")},
            {"sir_map": {"Amikacin": S}}),
    "V09": ({"degraded": [], "gate_applied": True}, {}),
    "V10": ({"data_blocked": False}, {}),
    "V11": ({"ranked": _items("Amikacin"), "allowed": _items("Amikacin")},
            {"sir_map": {"Amikacin": S}, "report_text": _text(rec=("Amikacin",))}),
    "V12": ({}, {"pdf_html": "<b>no mechanism</b>"}),
    "V13": ({}, {"sir_map": {"Ciprofloxacin": S},
                 "image_lists": {"preferred": ["Ciprofloxacin"]}}),
    "V14": ({"sdd_reported": ["Cefepime"], "organism": "Escherichia coli"}, {}),
    "V15": ({"ocr_reviewed": None}, {}),          # nothing was read from an image
    "V17": ({"allowed": _items("Nitrofurantoin"), "organism": "E. coli",
             "host": {"age_years": 40}}, {"specimen": "Urine", "sir_map": {"Nitrofurantoin": S}}),
}


@pytest.mark.parametrize("rule", sorted(POSITIVE))
def test_every_rule_fires_on_its_case_and_stays_quiet_on_the_negative(rule):
    res, kw = POSITIVE[rule]
    assert rule in _ids(res, **kw), (rule, validate_case(res, **{"specimen": "Urine", **kw}))
    res, kw = NEGATIVE[rule]
    assert rule not in _ids(res, **kw)


def test_the_rule_table_covers_every_documented_rule():
    import cdss.validation.case_validator as CV
    import re
    documented = set(re.findall(r"^  (V\d\d) (error|warning)", CV.__doc__, re.M))
    covered = {k.rstrip("w") for k in POSITIVE}
    # V16 is global (the rule base itself): tests/test_v7_8_review.py breaks
    # the tables on purpose to show it fires
    assert {d for d, _ in documented} == covered | {"V16"}


# ── Sweep 2: random cases validate clean end to end ─────────────────────────
ORGS = ["Escherichia coli", "Klebsiella pneumoniae", "Pseudomonas aeruginosa",
        "Acinetobacter baumannii", "Proteus mirabilis", "Enterococcus faecalis",
        "Staphylococcus aureus"]
DRUGS = ["Ampicillin", "Amoxicillin/Clavulanate", "Cefuroxime", "Ceftriaxone", "Ceftazidime",
         "Cefepime", "Piperacillin + Tazobactam", "Meropenem", "Imipenem/Cilastatin", "Ertapenem",
         "Amikacin", "Gentamicin", "Ciprofloxacin", "Levofloxacin",
         "Trimethoprim/Sulfamethoxazole", "Nitrofurantoin", "Fosfomycin", "Colistin",
         "Vancomycin", "Linezolid", "Doxycycline", "Cephalexin"]
SPECIMENS = ["Urine", "Blood", "Sputum", "Wound swab"]
HOST = [[], [CATH], ["Paraplegia (spinal cord injury)"], ["Diabetes"]]


def _random_case(rng):
    org = rng.choice(ORGS)
    panel = {d: rng.choice((S, S, R, "I")) for d in rng.sample(DRUGS, rng.randint(4, 14))}
    spec = rng.choice(SPECIMENS)
    hf = rng.choice(HOST)
    coll = (FOLEY if CATH in hf else rng.choice((MSU, ""))) if spec == "Urine" else ""
    age = rng.choice((0.3, 4, 23, 45, 70, 88))
    # v7.8: a weight plausible for the age -- an implausible one is now an
    # input conflict that blocks the case (tested in tests/test_v7_8_review.py)
    weight = {0.3: 6, 4: 16}.get(age, rng.choice((50, 70, 95)))
    pt = Patient(age_years=age, sex=rng.choice(("Male", "Female")),
                 weight_kg=weight, host_factors=hf, collection_method=coll)
    return pt, org, spec, panel


@pytest.mark.parametrize("seed", range(6))
def test_random_cases_validate_clean_end_to_end(seed):
    rng = random.Random(7600 + seed)
    for _ in range(25):
        pt, org, spec, panel = _random_case(rng)
        try:
            r = run_analysis(pt, org, spec, dict(panel))
        except Exception as exc:                       # pragma: no cover - a crash is a finding
            pytest.fail(f"run_analysis crashed on {org}/{spec}/{panel}: {exc!r}")
        kw = dict(patient_name="X", age=pt.age_years, sex=pt.sex, weight=pt.weight_kg, cl_cr=None,
                  is_renal=False, is_preg=False, is_hepatic=False, allowed=r["allowed"],
                  warned=r["warned"], banned=r["banned"], preg_warn_items=r["preg_warn"],
                  organism=org, specimen=spec, interactions=[], sir_map=dict(panel),
                  treatment_gate=r.get("treatment_gate"))
        t = generate_report(**kw)
        errs = [v for v in validate_case(r, specimen=spec, sir_map=panel, report_text=t)
                if v["severity"] == "error"]
        assert not errs, (org, spec, panel, pt, errs)


# ── Sweep 3: random page runs never offer a blocked clinical export ─────────
@pytest.mark.parametrize("seed", range(4))
def test_random_page_runs_never_offer_a_blocked_export(seed):
    from support.ui_harness import rendered_text
    rng = random.Random(7700 + seed)
    org = rng.choice(["E. coli", "Klebsiella pneumoniae", "Pseudomonas aeruginosa"])
    panel = {d: rng.choice((S, S, R)) for d in rng.sample(DRUGS, rng.randint(5, 12))}
    script = {"patho_coll_sel": rng.choice((MSU, FOLEY, "مش محدد")),
              "patho_host_sel": rng.choice(HOST)}
    report = rng.choice((None, MSU, FOLEY))
    traces, state, errors = _page(panel, org=org, script=script, report_method=report)
    assert not errors, errors
    txt = rendered_text(traces[-1])
    offered = _clinical_downloads(traces[-1])
    blocked = "التقرير النصي موقوف" in txt
    assert offered or blocked, "every run either offers the report or says why not"
    assert not (offered and blocked), offered
    if offered:
        assert "❌ **Clinical decision validation" not in txt


# ── Found while sweeping (second part of the v7.6 review) ───────────────────
@pytest.mark.parametrize("spelling", ["Amoxicillin/Clavulanate", "Amoxicillin-Clavulanate",
                                      "Amoxicillin clavulanate", "Amoxicillin + clavulanate",
                                      "Amoxicillin/clav", "Amox/Clav", "Amoxycillin-clavulanate"])
def test_amoxicillin_clavulanate_is_never_read_as_plain_amoxicillin(spelling):
    # it was: the longest alias found was "amoxicillin", so amox-clav S became amoxicillin S
    from cdss.ocr.ocr_parsing import parse_result_line
    assert parse_result_line(f"{spelling}   S") == [("Amoxicillin + Clavulanic acid", "S")]


def test_plain_amoxicillin_and_short_pip_tazo_still_read_right():
    from cdss.ocr.ocr_parsing import parse_result_line
    assert parse_result_line("Amoxicillin   R") == [("Amoxicillin", "R")]
    assert parse_result_line("Piperacillin/tazo   S") == [("Piperacillin + Tazobactam", "S")]


def test_sdd_is_offered_only_where_clsi_defines_it():
    from cdss.therapy.clsi_categories import sdd_defined, sir_options_for
    yes = [("Cefepime", "Escherichia coli"), ("Piperacillin + Tazobactam", "Klebsiella pneumoniae"),
           ("Ceftaroline", "Staphylococcus aureus"), ("Daptomycin", "Enterococcus faecium")]
    no = [("Cefepime", "Pseudomonas aeruginosa"), ("Daptomycin", "Enterococcus faecalis"),
          ("Nitrofurantoin", "Escherichia coli"), ("Amikacin", "Escherichia coli"),
          ("Ceftriaxone", "Escherichia coli"), ("Ciprofloxacin", "Escherichia coli")]
    assert all(sdd_defined(d, o) for d, o in yes)
    assert not any(sdd_defined(d, o) for d, o in no)
    assert sir_options_for("Ciprofloxacin", "Escherichia coli") == ["S", "I", "R"]


def test_an_sdd_on_an_undefined_pair_is_flagged_not_silently_changed():
    from cdss.astqc.reconciliation import mandatory_checks
    ids = [i["id"] for i in mandatory_checks("Escherichia coli", "Urine",
                                             {"Nitrofurantoin": "SDD", "Cefepime": "SDD"})]
    assert ids == ["REC-SDD-UNDEFINED"]
    from support.ui_harness import calls, rendered_text
    traces, state, errors = _page({"Nitrofurantoin": "SDD", "Cefepime": "SDD", "Amikacin": S})
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "كاتب SDD لـ Nitrofurantoin" in txt and "كاتب SDD لـ Cefepime" not in txt
    boxes = {c[2].get("key", ""): c[2].get("options") for c in calls(traces[-1], "selectbox")
             if isinstance(c[2], dict)}
    nitro = [v for k, v in boxes.items() if k.startswith("sir_Nitrofurantoin")]
    amik = [v for k, v in boxes.items() if k.startswith("sir_Amikacin")]
    # v7.7: the form offers S / I / R only; the unresolved laboratory SDD shows
    # as "--" (choose) and stays the laboratory's reading until it is chosen
    assert nitro and nitro[0] == ["--", "S", "I", "R"]
    assert amik and amik[0] == ["S", "I", "R"]
    assert state["sir_map_edited"]["Nitrofurantoin"] == "SDD"      # not turned into S


def test_a_non_urine_report_says_what_the_ranking_is_for_and_is_released():
    from cdss.stewardship.ranking import ranking_basis
    assert ranking_basis("Wound swab") == "Wound swab isolate · no ESBL / carbapenemase pattern"
    traces, state, errors = _page({"Ciprofloxacin": S, "Amikacin": S, "Ceftriaxone": S,
                                   "Meropenem": S}, spec="Wound swab")
    assert not errors, errors
    assert any("TXT" in d for d in _clinical_downloads(traces[-1]))


def test_esbl_not_excluded_covers_penicillins_and_cystitis():
    pt = Patient(age_years=45, sex="Female")
    # invasive: ampicillin S was ranked while cefuroxime S was cautioned
    r = run_analysis(pt, "Escherichia coli", "Sputum",
                     {"Ceftazidime": R, "Cefuroxime": S, "Ampicillin": S, "Fosfomycin": S})
    assert r["mechanism"]["probability"] == "moderate"
    assert "Ampicillin" not in [x["name"] for x in r["ranked"]]
    assert dict((x["name"], x.get("warning_reason")) for x in r["warned"])["Ampicillin"] == \
        "esbl_not_excluded"
    # cystitis: still an option, under caution, with its English note
    r2 = run_analysis(pt, "Proteus mirabilis", "Urine",
                      {"Ceftazidime": R, "Ceftriaxone": S, "Gentamicin": S, "Ciprofloxacin": S})
    w = {x["name"]: x for x in r2["warned"]}
    assert "Ceftriaxone" in w and "Ceftriaxone" not in [x["name"] for x in r2["ranked"]]
    from cdss.therapy.notes import warned_note_for
    assert "uncomplicated cystitis only" in warned_note_for(w["Ceftriaxone"], "en")
    assert not [v for v in validate_case(r2, specimen="Urine", sir_map={"Ceftriaxone": S})
                if v["id"] == "V05"]


def test_every_row_awaiting_dr_tarek_carries_the_owners_reviewed_decision():
    from cdss.guidelines.guideline_registry import RULES, V76_REVIEW
    unsigned = {k for k, v in RULES.items() if not v.get("countersigned_by")}
    assert unsigned == set(V76_REVIEW)
    for k in unsigned:
        row = RULES[k]
        assert "2026-11-20" in row["owner_approved"]
        assert "NOT a clinician countersignature" in row["owner_approved"]
        assert row["review_v76"]
    assert sum(1 for v in RULES.values() if v.get("countersigned_by")) == 54   # none added
    assert "HEURISTIC" in RULES["QC003"]["awaiting_countersignature"]


def test_the_signed_panels_no_longer_print_pending_review():
    import cdss.astqc.ast_panel_completeness as PC
    refs = " ".join(g.get("reference", "") for g in PC.GROUPS)
    assert "pending review" not in refs and "pending full Ed36" not in refs
