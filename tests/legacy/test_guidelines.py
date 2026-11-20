"""Orange Lab CDSS — guideline traceability check.

Answers the question a behaviour test cannot: "does every clinical rule in this
engine come from a named, dated document, and has anyone actually checked it?"

FAILS when:
  * a rule in the engine has no row in guideline_registry.RULES
  * a registry row exists for a rule the engine no longer has (dead citation)
  * a row points at a source key that is not defined
  * a source is missing a version, date or URL
  * a verified row has gone stale (> STALE_AFTER_MONTHS)
  * a verified row does not name who checked it and when
  * a deprecated / ambiguous citation string is still used in the codebase

REPORTS (does not fail) the "pending" queue — rules inherited from earlier code
that nobody has verified against the source PDF yet. Keeping that number visible
is the whole point; a pending rule is not a bug, an invisible one is.

    python test_guidelines.py            # check
    python test_guidelines.py --queue    # print the pending review queue
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from legacy_support import all_source, module_path   # noqa: E402

from cdss.guidelines.guideline_registry import (                              # noqa: E402
    DEPRECATED_CITATIONS, RULES, SOURCES, STALE_AFTER_MONTHS, citation_line,
)

SHOW_QUEUE = "--queue" in sys.argv
# v7.5 (external review of v7.4): the machine's local date failed on a UTC CI
# runner ("verified in the future") for a review dated in Cairo the same day.
from cdss.common.util import lab_today  # noqa: E402
TODAY = lab_today()

failures: list[str] = []
warnings_: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


# ── 1. Collect every rule id the engine actually uses ────────────────────────
def engine_rule_ids() -> set:
    ids: set = set()
    import cdss.astqc.ast_reportability as RP
    import cdss.astqc.ast_consistency as CN
    import cdss.astqc.ast_panel_completeness as PC

    for group in ("INTRINSIC_RULES", "NO_BREAKPOINT_RULES", "INEFFECTIVE_INVIVO_RULES"):
        for r in getattr(RP, group, []):
            if isinstance(r, dict) and r.get("id"):
                ids.add(r["id"])
    # EXCEPTIONAL_PHENOTYPES added 2026-07: plausibility rules for results that
    # are internally consistent but contradict the published record (VRSA,
    # vancomycin-resistant pneumococcus, penicillin-resistant GAS). They carry
    # citations like every other rule and must be discovered here, or the
    # registry reports them as dead rows.
    for group in ("EQUIVALENCE_RULES", "HIERARCHY_RULES", "PREDICTIVE_RULES",
                  "EXCEPTIONAL_PHENOTYPES", "UNUSUAL_COMBINATIONS",
                  "CORRECTION_RULES"):
        for r in getattr(CN, group, []):
            if isinstance(r, dict) and r.get("id"):
                ids.add(r["id"])

    # ast_panel_completeness.py: one rule id per organism-group expected panel.
    for r in getattr(PC, "GROUPS", []):
        if isinstance(r, dict) and r.get("id"):
            ids.add(r["id"])

    app = all_source()
    ids |= set(re.findall(r'"id":\s*"(QC\d+[a-z]?)"', app))
    ids |= set(re.findall(r'f"(SPEC-URN|REP-GPO-GN):', app))
    return ids


ENGINE_IDS = engine_rule_ids()

print("Orange Lab CDSS — guideline traceability\n")

# ── 2. Every engine rule is registered, and vice versa ───────────────────────
unregistered = sorted(ENGINE_IDS - set(RULES))
for rid in unregistered:
    fail(f"rule '{rid}' is active in the engine but has no citation row")

# SYSTEM_CITATIONS are rows describing a classification system applied across
# the whole formulary (WHO AWaRe, Magiorakos MDR/XDR/PDR, the CRPA definition)
# rather than a rule with an ID. They are exempt from the dead-citation check
# and ONLY they are: the exemption is a named literal in the registry, so
# adding to it is a deliberate act rather than a pattern that quietly widens.
try:
    from cdss.guidelines.guideline_registry import SYSTEM_CITATIONS
except ImportError:
    SYSTEM_CITATIONS = frozenset()

dead = sorted(set(RULES) - ENGINE_IDS - set(SYSTEM_CITATIONS))
for rid in dead:
    fail(f"citation row '{rid}' has no matching rule in the engine (dead citation)")

# The exemption must not become a dumping ground: every member has to exist.
for rid in sorted(SYSTEM_CITATIONS):
    if rid not in RULES:
        fail(f"SYSTEM_CITATIONS names '{rid}' but the registry has no such row")

# ── 3. Sources are complete ──────────────────────────────────────────────────
for key, src in SOURCES.items():
    for field in ("title", "version", "dated", "url"):
        if not src.get(field):
            fail(f"source '{key}' is missing '{field}'")
    if src.get("url") and not src["url"].startswith("http"):
        fail(f"source '{key}' has a URL that is not a URL: {src['url']!r}")

# ── 4. Rows are well formed, and 'primary' rows are attributed and fresh ─────
pending: list[str] = []
primary: list[str] = []
unsigned: list[str] = []
owner_approved: list[str] = []      # released by the lab owner, not clinician-signed
primary_verified: list[str] = []    # checked against the source document itself
secondary_verified: list[str] = []  # checked through secondary sources
pending_heuristic: list[str] = []   # not a published rule (QC003) / not yet checked
clinician_signed: list[str] = []
owner_approved_unsigned: list[str] = []
awaiting_countersignature: list[str] = []

for rid, row in sorted(RULES.items()):
    if row.get("source") not in SOURCES:
        fail(f"rule '{rid}' points at undefined source {row.get('source')!r}")
    if not row.get("assertion"):
        fail(f"rule '{rid}' has no assertion text")

    level = row.get("verified")
    # v7.8 (external review of v7.7): the counts were merged ("checked vs
    # source = 71" added primary and secondary; "awaiting human = 0" left out
    # the owner-approved rows). Each status is counted on its own now.
    (primary_verified if level == "source" else secondary_verified
     if level == "secondary" else pending_heuristic).append(rid)
    if row.get("countersigned_by"):
        clinician_signed.append(rid)
        if "NOT a clinician countersignature" in str(row["countersigned_by"]):
            fail(f"rule '{rid}': an owner approval was written as a clinician signature")
    else:
        awaiting_countersignature.append(rid)
        if row.get("owner_approved"):
            owner_approved_unsigned.append(rid)
    if level in ("source", "secondary"):
        primary.append(rid)
        if not row.get("checked_by"):
            fail(f"rule '{rid}' is marked {level} but names no checker")
        if row.get("owner_approved") and not row.get("countersigned_by"):
            owner_approved.append(rid)
        elif not row.get("countersigned_by"):
            unsigned.append(rid)
        stamp = row.get("checked_on")
        if not stamp:
            fail(f"rule '{rid}' is marked {level} but carries no date")
            continue
        try:
            when = _dt.date.fromisoformat(stamp)
        except ValueError:
            fail(f"rule '{rid}' has an unparseable verified_on: {stamp!r}")
            continue
        if when > TODAY:
            fail(f"rule '{rid}' was verified in the future ({stamp})")
        months = (TODAY.year - when.year) * 12 + (TODAY.month - when.month)
        if months > STALE_AFTER_MONTHS:
            fail(f"rule '{rid}' verification is stale — checked {months} months ago "
                 f"({stamp}); limit is {STALE_AFTER_MONTHS}")
    elif level == "pending":
        pending.append(rid)
    else:
        fail(f"rule '{rid}' has an unknown verification level {level!r} "
             f"(expected 'source', 'secondary' or 'pending')")

# ── 5. Deprecated citation strings must be gone from the codebase ────────────
SKIP = {"guideline_registry.py", "test_guidelines.py"}
hits: dict = {}
for path in sorted(ROOT.rglob("*.py")):
    if path.name in SKIP:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        continue
    for bad in DEPRECATED_CITATIONS:
        n = text.count(bad)
        if n:
            hits.setdefault(bad, []).append((path.name, n))

# ── Report ───────────────────────────────────────────────────────────────────
print(f"  rules in engine           : {len(ENGINE_IDS)}")
print(f"  citation rows             : {len(RULES)}")
print(f"  primary_verified          : {len(primary_verified)}  (the source document itself)")
print(f"  secondary_verified        : {len(secondary_verified)}  (through secondary sources)")
print(f"  pending_heuristic         : {len(pending_heuristic)}  (not a published rule / not checked)")
print(f"  clinician_signed          : {len(clinician_signed)}")
print(f"  owner_approved_unsigned   : {len(owner_approved_unsigned)}  (lab owner's approval; "
      f"NOT a clinician signature)")
print(f"  awaiting_countersignature : {len(awaiting_countersignature)}  (every row without "
      f"a clinician's signature)")

if hits:
    total = sum(n for v in hits.values() for _, n in v)
    print(f"\n  DEPRECATED CITATION STRINGS — {total} occurrence(s):")
    for bad, where in sorted(hits.items()):
        loc = ", ".join(f"{f} x{n}" for f, n in where)
        print(f"    \"{bad}\"  ({loc})")
        print(f"        -> {DEPRECATED_CITATIONS[bad]}")
        failures.append(f'deprecated citation "{bad}" still used ({loc})')

if SHOW_QUEUE and pending:
    print(f"\n  PENDING REVIEW QUEUE ({len(pending)}) — open the PDF, confirm the "
          f"assertion, then set verified/verified_by/verified_on:")
    for rid in pending:
        print(f"\n    {rid}")
        print(f"      {RULES[rid]['assertion'][:150]}")
        print(f"      -> {citation_line(rid)}")
        print(f"         {SOURCES[RULES[rid]['source']]['url']}")

if failures:
    print(f"\n  FAILURES ({len(failures)}):")
    for f in failures:
        print(f"    ✗ {f}")

print("\n" + "=" * 68)
if failures:
    print("RESULT: traceability incomplete")
else:
    print(f"RESULT: every rule traced. {len(primary_verified)} checked against the source "
          f"itself, {len(secondary_verified)} through secondary sources, "
          f"{len(pending_heuristic)} not yet checked; {len(clinician_signed)} signed by a "
          f"clinician, {len(awaiting_countersignature)} awaiting a clinician's countersignature "
          f"({len(owner_approved_unsigned)} of them approved by the lab owner only). "
          f"Run --queue for the review list.")
# the counts must add up -- a row cannot fall between two statuses
assert len(primary_verified) + len(secondary_verified) + len(pending_heuristic) == len(RULES)
assert len(clinician_signed) + len(awaiting_countersignature) == len(RULES)
if __name__ == "__main__":
    sys.exit(1 if failures else 0)
