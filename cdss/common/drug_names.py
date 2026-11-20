# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""One answer to "is this the same antibiotic?" for counting and panel checks (v7.4).

DEFECT THIS CLOSES (external case review, 2026-11-20)
The AST-QA sheet listed "Cefuroxime sodium (R)" among the tested agents and,
on the same page, "Cefuroxime" among the MISSING ones. Panel completeness
matched names character by character, so a salt form (the parenteral sodium
salt) or a formulation (the oral axetil ester) of an agent that WAS tested
counted as a different, untested drug -- a false "missing" alert, and a
"Tested 10" that disagreed with the "14 antibiotics tested" printed above it.

What this module does NOT do: it never merges two agents that CLSI interprets
differently for therapy. "Cefuroxime sodium" (parenteral) and "Cefuroxime"
stay separate formulary entries with their own notes; they only fill the SAME
SLOT of the expected panel, and two entries for one slot are checked against
each other (different results = a reading error to resolve).
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Tuple

# Salt forms / formulations -> the panel slot they fill. Keys are compared after
# normalisation (lower case, alphanumerics only).
_PANEL_SLOT = {
    "cefuroximesodium": "Cefuroxime",
    "cefuroximeaxetil": "Cefuroxime",
    "cefuroximeiv": "Cefuroxime",
    "cefuroximeoral": "Cefuroxime",
}

_NORM = re.compile(r"[^a-z0-9]")


def norm_key(name: str) -> str:
    """Lower case, alphanumerics only -- the comparison key used everywhere."""
    return _NORM.sub("", str(name or "").lower())


def panel_slot(name: str) -> str:
    """The expected-panel slot this agent fills ("Cefuroxime sodium" -> "Cefuroxime")."""
    return _PANEL_SLOT.get(norm_key(name), str(name or "").strip())


def panel_slot_key(name: str) -> str:
    return norm_key(panel_slot(name))


def group_by_slot(names: Iterable[str]) -> Dict[str, List[str]]:
    """{slot key: [names as entered]} -- more than one name means the same agent twice."""
    out: Dict[str, List[str]] = {}
    for n in names:
        out.setdefault(panel_slot_key(n), []).append(str(n))
    return out


def duplicate_slots(sir_map: Mapping[str, str]) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """[(slot, [(name, result), ...])] for every slot entered more than once."""
    dup: List[Tuple[str, List[Tuple[str, str]]]] = []
    for _key, names in group_by_slot((sir_map or {}).keys()).items():
        if len(names) > 1:
            dup.append((panel_slot(names[0]),
                        [(n, str((sir_map or {}).get(n, "")).strip().upper()) for n in names]))
    return dup


def tag_with_ast(names: List[str], sir_map: Dict[str, str]) -> List[str]:
    """v7.4: each agent with this isolate's result, or "not tested"; one entry per agent.

    "Cefuroxime" and "Cefuroxime sodium" were listed as two drugs (the second
    tagged R) -- one panel slot (cdss.common.drug_names) is listed once, with
    the name it was tested under.
    """
    by_slot: Dict[str, tuple] = {}
    for d, r in (sir_map or {}).items():
        by_slot.setdefault(panel_slot_key(d), (d, str(r or "").strip().upper()))
    out: List[str] = []
    seen: set = set()
    for d in names:
        k = panel_slot_key(d)
        if k in seen:
            continue
        seen.add(k)
        hit = by_slot.get(k)
        if hit is None:
            out.append(f"{d} [not tested]")
        elif hit[0] != d:
            out.append(f"{d} [{hit[1]} as {hit[0]}]")
        else:
            out.append(f"{d} [{hit[1]}]")
    return out


__all__ = ["tag_with_ast", "norm_key", "panel_slot", "panel_slot_key", "group_by_slot", "duplicate_slots"]
