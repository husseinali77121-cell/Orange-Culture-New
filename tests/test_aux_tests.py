# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""D-test and penicillinase: Positive / Negative results that ride in the panel.

Regression for a defect of the single-file app: the panel was normalised to
S/I/R before the rules ran, so these two results were discarded -- a negative
D-test could never release clindamycin.
"""
import pytest

from cdss.common.aux_tests import is_aux_key, normalize_aux_result, read_aux_tests
from cdss.ocr.ocr_parsing import normalize_sir_map
from support.cases import analyse, bucket_of, item_of

STAPH = "Staphylococcus aureus"
INDUCIBLE = {"Erythromycin": "R", "Clindamycin": "S", "Vancomycin": "S", "Oxacillin": "S"}


@pytest.mark.parametrize("value,expected", [
    ("Negative", "NEGATIVE"), ("neg", "NEGATIVE"), (" -ve ", "NEGATIVE"), ("سالب", "NEGATIVE"),
    ("Positive", "POSITIVE"), ("POS", "POSITIVE"), ("+", "POSITIVE"), ("موجب", "POSITIVE"),
    ("", ""), (None, ""), ("S", ""), ("R", ""), ("done", ""), ("?", ""),
])
def test_normalize_aux_result_never_guesses(value, expected):
    assert normalize_aux_result(value) == expected


def test_aux_keys_are_read_before_normalisation_drops_them():
    panel = {"Clindamycin": "S", "D-test": "Negative", "Penicillinase": "Positive"}
    assert "D-test" not in normalize_sir_map(panel)              # why the old code never saw it
    assert read_aux_tests(panel) == {"d_test": "NEGATIVE", "penicillinase": "POSITIVE",
                                     "esbl_confirm": ""}      # v7.4: ESBL confirmatory test
    assert is_aux_key(" d-TEST ") and not is_aux_key("Clindamycin")


def test_negative_d_test_releases_clindamycin():
    res = analyse(STAPH, "Wound Swab", {**INDUCIBLE, "D-test": "Negative"})
    assert bucket_of(res, "Clindamycin") == "allowed"


def test_positive_d_test_bans_and_says_positive():
    res = analyse(STAPH, "Wound Swab", {**INDUCIBLE, "D-test": "Positive"})
    item = item_of(res, "Clindamycin")
    assert item["category"] == "d_test_inducible" and "Positive" in item["reason_short"]


@pytest.mark.parametrize("panel_extra", [{}, {"D-test": ""}, {"D-test": "S"}, {"D-test": "pending"}])
def test_missing_or_unreadable_d_test_stays_closed(panel_extra):
    res = analyse(STAPH, "Wound Swab", {**INDUCIBLE, **panel_extra})
    item = item_of(res, "Clindamycin")
    assert item["category"] == "d_test_inducible" and "Not Confirmed" in item["reason_short"]


def test_penicillinase_result_decides_penicillin():
    base = {"Penicillin": "S", "Oxacillin": "S", "Vancomycin": "S"}
    assert bucket_of(analyse(STAPH, "Wound Swab", base), "Penicillin") == "warned"
    assert bucket_of(analyse(STAPH, "Wound Swab", {**base, "Penicillinase": "Negative"}), "Penicillin") == "allowed"
    pos = item_of(analyse(STAPH, "Wound Swab", {**base, "Penicillinase": "Positive"}), "Penicillin")
    assert pos["category"] == "penicillinase_producer"


def test_aux_rows_are_never_treated_as_drugs():
    res = analyse(STAPH, "Wound Swab", {**INDUCIBLE, "D-test": "Negative", "Penicillinase": "Negative"})
    names = {it["name"] for b in ("allowed", "warned", "preg_warn", "banned") for it in res[b]}
    assert names == set(INDUCIBLE)
    assert not any("D-test" in str(w) for w in res.get("patient_warnings", []))


# ── oxacillin / cefoxitin "I": no such category for staphylococci ───────────
@pytest.mark.parametrize("screen", ["Oxacillin", "Cefoxitin"])
def test_intermediate_methicillin_screen_is_not_a_pass(screen):
    res = analyse(STAPH, "Blood", {screen: "I", "Cefazolin": "S", "Vancomycin": "S"})
    cefazolin = item_of(res, "Cefazolin")
    assert bucket_of(res, "Cefazolin") != "allowed"
    assert cefazolin.get("warning_reason") == "possible_mrsa"
    assert "Intermediate" in cefazolin["possible_mrsa_note"]
    assert any(p["phenotype"] == "Possible MRSA" for p in res["phenotypes"])


def test_possible_mrsa_note_describes_the_panel_that_is_there():
    untested = item_of(analyse(STAPH, "Blood", {"Cephalexin": "R", "Vancomycin": "S", "Cefazolin": "S"}), "Cefazolin")
    assert "لا تحتوي Oxacillin" in untested["possible_mrsa_note"]
    discordant = item_of(analyse(STAPH, "Blood", {"Cephalexin": "R", "Vancomycin": "S", "Cefazolin": "S",
                                                  "Cefoxitin": "S"}), "Cefazolin")
    assert "لا تحتوي Oxacillin" not in discordant["possible_mrsa_note"]
    assert "Cefoxitin = S" in discordant["possible_mrsa_note"]
