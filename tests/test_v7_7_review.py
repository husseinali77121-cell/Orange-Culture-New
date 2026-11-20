"""v7.7 (2026-11-20): SDD leaves the entry form; the external review of v7.6.

The owner's decision: every result list is S / I / R. SDD is not a choice
anywhere; a laboratory SDD read by the OCR is kept and explained in a NOTE under
the drug, as I and dose-adjustment results are.

  1. The form offers S / I / R only (OCR rows, manual rows, quick add, the
     "detected without a result" rows).
  2. A laboratory SDD on a pair CLSI defines it for is shown as I with the SDD
     note and its regimen, and the engine keeps it SDD (the reports print SDD).
  3. A laboratory SDD where CLSI defines none shows "--" (choose) with an
     error, is read as I meanwhile, and blocks every export (V14) until chosen.
  4. PL3 said "the program reads it as SDD" -- untrue since v7.1, and it asked
     to correct the report to SDD without an MIC. An I on a CLSI no-I pair is
     never turned into SDD: "SDD or R -- obtain the MIC".
  5. Daptomycin: SDD_REGIMENS took "VRE" as E. faecium; PL3's own list did not.
     One table now; SDD needs E. faecium.
  6. A manually added drug without a result entered the analysis as S.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cdss.astqc.phenotype_plausibility import check_plausibility, no_i_pair  # noqa: E402
from cdss.therapy.clsi_categories import SDD_REGIMENS, panel_display, sdd_defined  # noqa: E402

S, R = "S", "R"
EXPORTS = ("TXT", "Download PDF", "تنزيل الصورة")


def _page(panel, org="E. coli", spec="Urine", script=None, runs=2):
    from support.ui_harness import payload, run_page
    return run_page(payload(org, spec, panel, age=40, sex="Female"), runs=runs, script=script)


def _boxes(trace):
    from support.ui_harness import calls
    return {c[2].get("key", ""): c[2].get("options") for c in calls(trace, "selectbox")
            if isinstance(c[2], dict)}


def _key(trace, prefix):
    keys = [k for k in _boxes(trace) if k.startswith(prefix)]
    assert keys, prefix
    return keys[0]


def _downloads(trace):
    from support.ui_harness import calls
    return [c[1][0] for c in calls(trace, "download_button") if any(k in c[1][0] for k in EXPORTS)]


PANEL = {"Cefepime": "SDD", "Nitrofurantoin": "SDD", "Amikacin": S, "Imipenem/Cilastatin": S,
         "Ciprofloxacin": R}


# ── 1. S / I / R only, everywhere ───────────────────────────────────────────
def test_no_result_list_on_the_page_offers_sdd():
    traces, state, errors = _page(PANEL)
    assert not errors, errors
    result_lists = {k: v for k, v in _boxes(traces[-1]).items()
                    if k.startswith(("sir_", "quick_add_sir", "assign_"))
                    or (v and set(v) & {"S", "I", "R"})}
    assert result_lists, "the panel was not drawn"
    for k, opts in result_lists.items():
        assert "SDD" not in (opts or []), (k, opts)
        assert set(opts or []) - {"--"} <= {"S", "I", "R"}, (k, opts)


def test_the_form_options_are_s_i_r_for_every_pair():
    from cdss.therapy.clsi_categories import sir_options_for
    for drug, org in (("Cefepime", "E. coli"), ("Ceftaroline", "Staphylococcus aureus"),
                      ("Daptomycin", "Enterococcus faecium"), ("Nitrofurantoin", "E. coli")):
        assert sir_options_for(drug, org) == ["S", "I", "R"]


# ── 2. A laboratory SDD where CLSI defines it ───────────────────────────────
def test_a_laboratory_sdd_shows_as_i_with_its_note_and_stays_sdd_for_the_engine():
    from support.ui_harness import rendered_text
    panel = {k: v for k, v in PANEL.items() if k != "Nitrofurantoin"}
    traces, state, errors = _page(panel)
    assert not errors, errors
    box = _boxes(traces[-1])[_key(traces[-1], "sir_Cefepime_")]
    assert box == ["S", "I", "R"]
    txt = rendered_text(traces[-1])
    assert "تقرير المعمل: **SDD**" in txt and "2 g IV q8h" in txt     # the note under the drug
    assert state["sir_map_edited"]["Cefepime"] == "SDD"
    rpt = state.get("_rpt_text") or ""
    assert "Cefepime [Culture: SDD]" in rpt and "Susceptible-dose dependent" in rpt
    assert _downloads(traces[-1]), "a valid SDD does not block anything"


def test_choosing_another_result_replaces_the_laboratory_sdd():
    panel = {k: v for k, v in PANEL.items() if k != "Nitrofurantoin"}
    traces, state, errors = _page(panel)
    key = _key(traces[-1], "sir_Cefepime_")
    traces, state, errors = _page(panel, script={key: "R"})
    assert not errors, errors
    assert state["sir_map_edited"]["Cefepime"] == "R"
    traces, state, errors = _page(panel, script={key: "I"})      # back to what the form shows
    assert state["sir_map_edited"]["Cefepime"] == "SDD"          # the laboratory's reading


# ── 3. A laboratory SDD where CLSI defines none ─────────────────────────────
def test_an_undefined_sdd_must_be_chosen_and_blocks_the_reports_until_then():
    from support.ui_harness import rendered_text
    traces, state, errors = _page(PANEL)
    assert not errors, errors
    key = _key(traces[-1], "sir_Nitrofurantoin_")
    assert _boxes(traces[-1])[key] == ["--", "S", "I", "R"]
    txt = rendered_text(traces[-1])
    assert "كاتب SDD لـ Nitrofurantoin" in txt
    assert "The laboratory wrote SDD for Nitrofurantoin" in txt          # V14
    assert _downloads(traces[-1]) == []
    assert state["sir_map_edited"]["Nitrofurantoin"] == "SDD"     # never silently S
    traces, state, errors = _page(PANEL, script={key: "I"})
    assert not errors, errors
    assert state["sir_map_edited"]["Nitrofurantoin"] == "I"
    assert "The laboratory wrote SDD for Nitrofurantoin" not in rendered_text(traces[-1])
    assert _downloads(traces[-1])


# ── 4. An I on a CLSI no-I pair is never converted ──────────────────────────
def test_an_i_on_a_no_i_pair_says_sdd_or_r_and_is_never_converted():
    from support.ui_harness import rendered_text
    traces, state, errors = _page({"Cefepime": "I", "Amikacin": S, "Imipenem/Cilastatin": S})
    assert not errors, errors
    txt = rendered_text(traces[-1])
    assert "ممكن تكون SDD أو R" in txt and "مش بيحوّلها SDD" in txt
    assert state["sir_map_edited"]["Cefepime"] == "I"
    rpt = state.get("_rpt_text") or ""
    assert "Cefepime [Culture: SDD]" not in rpt
    shown, level, note = panel_display("Cefepime", "E. coli", "I")
    assert (shown, level) == ("I", "warning")


def test_pl3_no_longer_says_the_program_reads_i_as_sdd():
    f = [x for x in check_plausibility("Escherichia coli", {"Cefepime": "I"}, sdd=[])
         if x["id"] == "PL3:Cefepime"]
    assert f, "PL3 must still fire"
    text = " ".join(str(f[0][k]) for k in ("title_en", "detail_en", "action_en"))
    assert "Do not automatically convert I to SDD" in text and "SDD or R" in text
    assert "reads it as SDD" not in text and "Correct the laboratory report to SDD" not in text
    assert "لا يجوز تحويل I تلقائياً إلى SDD" in f[0]["detail_ar"]


# ── 5. Daptomycin: SDD needs E. faecium; one table for both checks ──────────
def test_daptomycin_sdd_needs_e_faecium_not_just_vre():
    assert not sdd_defined("Daptomycin", "VRE")
    assert not sdd_defined("Daptomycin", "Enterococcus faecalis")
    assert sdd_defined("Daptomycin", "Enterococcus faecium")
    assert panel_display("Daptomycin", "VRE", "SDD")[:2] == ("--", "error")


def test_sdd_defined_and_no_i_pair_agree_for_every_organism_the_app_offers():
    from cdss.organisms.organism_profile import ORGANISM_PROFILE
    orgs = list(ORGANISM_PROFILE) + ["VRE", "MRSA", "MSSA", "E. coli", "Enterobacterales"]
    bad = [(d, o) for d in SDD_REGIMENS for o in orgs if sdd_defined(d, o) != no_i_pair(d, o)]
    assert not bad, bad[:5]


# ── 6. A drug added by hand without a result is not S ───────────────────────
def test_a_manually_added_drug_without_a_result_is_left_out_not_s():
    from support.ui_harness import rendered_text
    traces, state, errors = _page({"Ciprofloxacin": S})
    mkey = [k for k in state if str(k).startswith("manual_drugs_")]
    assert mkey
    traces, state, errors = _page({"Ciprofloxacin": S}, script={mkey[0]: ["Amikacin"]})
    assert not errors, errors
    box = _boxes(traces[-1])[_key(traces[-1], "sir_manual_Amikacin_")]
    assert box[0] == "--"
    assert "Amikacin" not in state["sir_map_edited"]
    assert "حدّد نتيجة كل واحد" in rendered_text(traces[-1])
