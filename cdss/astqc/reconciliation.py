# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Mandatory consistency checks on the panel itself, before any confidence (v7.4).

External case review (2026-11-20): the AST-QA sheet said "High Confidence —
Errors: 0" while, on the same page, the panel counts disagreed ("Tested 10"
beside "14 antibiotics tested") and one agent appeared as both tested and
missing under two spellings. The confidence score was computed from the
interpretive findings only; nothing checked that the panel had been counted
and named consistently.

These checks run first (run_ast_qc pass 0), so their findings reach the inline
QC, the final checklist, the QA report and the confidence score like any
other finding:

  REC-DUP-CONFLICT  error    the same agent entered twice (spelling) with DIFFERENT
                             results, or an oral form reported MORE susceptible than the
                             parenteral form (the oral breakpoint is the stricter one)
  REC-DUP           warning  the same agent entered twice with the same result
  REC-UNREADABLE    warning  a result that is not S / I / R / SDD (dropped from analysis)
  REC-SDD-UNDEFINED error    SDD on a drug / organism pair CLSI defines no SDD for (read as I)
  REC-COUNT         error    the panel-completeness counts do not reconcile with the
                             panel as entered (an internal error -- never expected)
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from cdss.common.drug_names import duplicate_slots

_READABLE = {"S", "I", "R", "SDD"}


def mandatory_checks(organism: str, specimen: str, raw_panel: Optional[Mapping[str, Any]],
                     panel_result: Any = None) -> List[Dict[str, Any]]:
    """Findings in run_ast_qc's {id, severity, message, fix} shape."""
    panel = {str(k).strip(): v for k, v in (raw_panel or {}).items() if str(k or "").strip()}
    issues: List[Dict[str, Any]] = []

    for slot, entries in duplicate_slots({k: str(v or "") for k, v in panel.items()}):
        results = {r for _, r in entries}
        listing = ", ".join(f"{n} = {r or '?'}" for n, r in entries)
        if _is_formulation_pair(entries):
            # Oral and parenteral forms of one agent carry DIFFERENT CLSI
            # breakpoints (cefuroxime oral S <= 4 vs parenteral S <= 8), so both
            # may be reported and may differ -- but the oral (stricter) reading can
            # never be more susceptible than the parenteral one.
            bad = _oral_more_susceptible(entries)
            if bad:
                issues.append({
                    "id": "REC-DUP-CONFLICT", "severity": "error",
                    "message": (f"{slot}: {listing}. The oral interpretation uses the stricter "
                                "breakpoint and cannot be more susceptible than the parenteral "
                                "one - one entry is a reading or transcription error."),
                    "fix": "Re-read the zone / MIC against both CLSI criteria and correct the entry.",
                })
            continue
        if len(results) > 1:
            issues.append({
                "id": "REC-DUP-CONFLICT", "severity": "error",
                "message": (f"{slot} was entered more than once with different results "
                            f"({listing}). The same agent cannot be both - one entry is a "
                            "reading or transcription error."),
                "fix": "Check the bench record and keep one entry with the correct result.",
            })
        else:
            issues.append({
                "id": "REC-DUP", "severity": "warning",
                "message": (f"{slot} was entered more than once ({listing}) - the same agent "
                            "under two names (salt form / formulation / spelling)."),
                "fix": "Keep one entry so the panel counts are not inflated.",
            })

    unreadable = [k for k, v in panel.items()
                  if str(v or "").strip().upper() not in _READABLE
                  and str(v or "").strip().lower() not in ("", "positive", "negative", "pos", "neg")]
    if unreadable:
        issues.append({
            "id": "REC-UNREADABLE", "severity": "warning",
            "message": ("Result not readable as S / I / R / SDD for: " + ", ".join(unreadable)
                        + " - these agents were left out of every analysis."),
            "fix": "Enter the result as S, I, R or SDD.",
        })

    # v7.6: SDD written for a pair CLSI defines no SDD for (an OCR or entry slip --
    # "SDD" on nitrofurantoin). The engine reads it as I; the reading must be fixed.
    from cdss.therapy.clsi_categories import is_sdd, sdd_defined
    bad_sdd = [k for k, v in panel.items() if is_sdd(v) and not sdd_defined(k, organism)]
    if bad_sdd:
        issues.append({
            "id": "REC-SDD-UNDEFINED", "severity": "error",
            "message": ("SDD entered for " + ", ".join(bad_sdd) + " - CLSI M100 Ed36 defines SDD "
                        "only for cefepime and piperacillin-tazobactam (Enterobacterales), "
                        "ceftaroline (S. aureus) and daptomycin (E. faecium). Read as I until "
                        "corrected."),
            "fix": "Check the laboratory report and enter S, I or R (or the MIC).",
        })

    if panel_result is not None and getattr(panel_result, "status", "") != "not_evaluated":
        try:
            ok = panel_result.reconciles()
        except Exception:          # pragma: no cover - older result object
            ok = True
        if not ok:
            issues.append({
                "id": "REC-COUNT", "severity": "error",
                "message": ("Panel counts do not reconcile: expected "
                            f"{panel_result.expected_total}, covered {panel_result.tested_count}, "
                            f"missing {len(panel_result.missing_primary) + len(panel_result.missing_supplemental)}, "
                            f"additional {len(panel_result.extra_tested)}, entered "
                            f"{panel_result.total_tested}."),
                "fix": "Internal counting error - do not release the QA sheet; report it.",
            })
    return issues


_RANK = {"S": 0, "SDD": 1, "I": 1, "R": 2}
# oral (stricter CLSI criterion) -> parenteral form of the same agent
_ORAL_PARENTERAL = {"cefuroxime": ("cefuroximesodium",), "cefuroximeaxetil": ("cefuroximesodium",)}


def _is_formulation_pair(entries) -> bool:
    from cdss.common.drug_names import norm_key
    keys = {norm_key(n) for n, _ in entries}
    return len(keys) == len(entries) and any(
        k in _ORAL_PARENTERAL and any(p in keys for p in _ORAL_PARENTERAL[k]) for k in keys)


def _oral_more_susceptible(entries) -> bool:
    from cdss.common.drug_names import norm_key
    res = {norm_key(n): r for n, r in entries}
    for oral, parenterals in _ORAL_PARENTERAL.items():
        if oral not in res:
            continue
        for par in parenterals:
            if par in res and res[oral] in _RANK and res[par] in _RANK \
                    and _RANK[res[oral]] < _RANK[res[par]]:
                return True
    return False


__all__ = ["mandatory_checks"]
