# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""The mechanics of the rule walk: a ban is terminal, a caution is not."""
import pytest

from cdss.therapy import engine
from cdss.therapy.outcome import Outcome
from support.cases import analyse, bucket_of, context, drug, item_of


# ── Outcome ─────────────────────────────────────────────────────────────────
def test_first_ban_wins():
    out = Outcome({})
    out.ban({"name": "X", "category": "first"})
    out.ban({"name": "X", "category": "second"})
    assert out.banned["category"] == "first"


def test_first_caution_is_primary_and_later_ones_are_kept():
    out = Outcome({})
    out.caution({"name": "X", "warning_reason": "a"})
    out.caution({"name": "X", "warning_reason": "b"})
    assert out.primary["warning_reason"] == "a"
    assert [c["warning_reason"] for c in out.secondary] == ["b"]


def test_notes_merge_and_warn_beats_allow():
    notes = {}
    out = Outcome(notes)
    out.note("X", "allow", "first", "organism_note")
    out.note("X", "warn", "second", "allergy")
    out.note("X", "allow", "third", "novel_agent")
    level, text, reason, every = notes["X"]
    assert level == "warn" and reason == "allergy"
    assert all(t in text for t in ("first", "second", "third"))
    # v6.9: every reason is kept, so the English report prints each note.
    assert every == ("organism_note", "allergy", "novel_agent")


def test_a_repeated_note_is_not_duplicated():
    notes = {}
    out = Outcome(notes)
    out.note("X", "warn", "same", "r")
    out.note("X", "warn", "same", "r")
    assert notes["X"][1] == "same"


# ── the walk, with synthetic rules ──────────────────────────────────────────
def _walk(monkeypatch, *rules):
    monkeypatch.setattr(engine, "RULES", tuple(rules))
    return engine.judge_drug(context(), drug("Ciprofloxacin"), {})


def test_walk_stops_at_a_ban(monkeypatch):
    seen = []
    out = _walk(monkeypatch,
                lambda cx, dg, out: seen.append(1),
                lambda cx, dg, out: (seen.append(2), out.ban({"name": dg.name, "category": "x"})),
                lambda cx, dg, out: seen.append(3))
    assert seen == [1, 2] and out.banned["category"] == "x"


def test_walk_continues_after_a_caution_and_a_later_ban_still_applies(monkeypatch):
    out = _walk(monkeypatch,
                lambda cx, dg, out: out.caution({"name": dg.name, "warning_reason": "early"}),
                lambda cx, dg, out: out.ban({"name": dg.name, "category": "late"}))
    assert out.banned["category"] == "late", "a caution must never hide a later contraindication"


def test_every_rule_sees_a_cautioned_drug(monkeypatch):
    seen = []
    _walk(monkeypatch,
          lambda cx, dg, out: out.caution({"name": dg.name, "warning_reason": "early"}),
          lambda cx, dg, out: seen.append("b"),
          lambda cx, dg, out: seen.append("c"))
    assert seen == ["b", "c"]


# ── the same property on the real rule set ──────────────────────────────────
POSSIBLE_MRSA = {"Cephalexin": "R", "Vancomycin": "S"}          # staph, beta-lactam R, no screen


def test_possible_mrsa_caution_does_not_hide_a_no_role_ban():
    """Was: 'warned -- possible MRSA'. The agent has no activity against staphylococci at all."""
    res = analyse("Staphylococcus aureus", "Blood", {**POSSIBLE_MRSA, "Cefiderocol": "S"})
    assert bucket_of(res, "Cefiderocol") == "banned"


def test_possible_mrsa_caution_does_not_hide_the_penicillinase_ban():
    res = analyse("Staphylococcus aureus", "Pus", {**POSSIBLE_MRSA, "Penicillin": "I"})
    assert item_of(res, "Penicillin")["category"] == "penicillinase_producer"


def test_possible_mrsa_caution_does_not_hide_a_paediatric_ban():
    res = analyse("Staphylococcus aureus", "Blood", {**POSSIBLE_MRSA, "Imipenem + Relebactam": "S"},
                  age_years=6)
    assert bucket_of(res, "Imipenem + Relebactam") == "banned"


def test_a_mechanism_caution_does_not_swallow_the_pregnancy_caution():
    """Possible carbapenemase + pregnancy: the drug is shown as a pregnancy caution
    and the carbapenemase note travels with it (it used to lose the pregnancy note)."""
    sir = {"Ertapenem": "R", "Meropenem": "S", "Aztreonam": "S", "Ceftriaxone": "S"}
    plain = analyse("Citrobacter freundii", "Urine", sir, sex="Female")
    preg = analyse("Citrobacter freundii", "Urine", sir, sex="Female", is_pregnant=True)
    assert bucket_of(plain, "Aztreonam") == "warned"
    assert bucket_of(preg, "Aztreonam") == "preg_warn"
    note = item_of(preg, "Aztreonam")["preg_note"]
    assert "كاربابينيميز" in note, "the carbapenemase suspicion must still be stated"


def test_esbl_cystitis_caution_keeps_host_facts():
    sir = {"Ceftriaxone": "R", "Cefotaxime": "R", "Ceftazidime": "R", "Cefepime": "S",
           "Piperacillin + Tazobactam": "S"}
    res = analyse("E. coli", "Urine", sir, is_renal=True, cl_cr=20)
    cefepime = item_of(res, "Cefepime")
    assert cefepime["warning_reason"] == "esbl_bli_uti_only"
    assert cefepime.get("renal_adjustment") is True and "Renal" in cefepime["esbl_note"]
    # one ESBL statement, not the specific one plus the generic one
    assert cefepime["esbl_note"].count("كائن ESBL") == 1


def test_banned_list_follows_the_panel_order():
    sir = {"Vancomycin": "R", "Ciprofloxacin": "R", "Amikacin": "R"}
    res = analyse("E. coli", "Blood", sir)
    assert [b["name"] for b in res["banned"]] == list(sir)


@pytest.mark.parametrize("organism,specimen,sir", [
    ("E. coli", "Urine", {"Ciprofloxacin": "S", "Nitrofurantoin": "S", "Ceftriaxone": "R"}),
    ("Staphylococcus aureus", "Blood", {"Oxacillin": "R", "Vancomycin": "S", "Cefazolin": "S"}),
    ("Pseudomonas aeruginosa", "Sputum", {"Meropenem": "R", "Ceftazidime": "S", "Amikacin": "S"}),
])
def test_every_panel_drug_lands_in_exactly_one_bucket(organism, specimen, sir):
    res = analyse(organism, specimen, sir)
    names = [it["name"] for b in ("allowed", "warned", "preg_warn", "banned") for it in res[b]]
    assert sorted(names) == sorted(sir)
