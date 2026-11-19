# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Drug-list filters used when building the editable panel (intrinsic / urine-only)."""
from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.common.specimen import (
    classify_specimen,
)
from cdss.therapy.intrinsic import (
    is_intrinsically_avoided,
)


def _drop_intrinsic(names, organism):
    """Remove agents this organism is intrinsically resistant to.

    The Organism Guidance panel printed first/second/third-line straight from
    ORGANISM_PROFILE with only the urine-only filter applied. Nothing checked
    the intrinsic table, so a single stale row in the profile put a drug the
    engine BANS on the same screen as a recommendation. This closes the display
    against the same source of truth the engine uses, so the two cannot drift
    apart again even if a profile row is edited carelessly.
    """
    out = []
    for n in (names or []):
        info = ABX_GUIDELINES.get(n, {})
        if is_intrinsically_avoided(organism, n, info):
            continue
        out.append(n)
    return out

def _hide_urine_only(names, specimen):
    """Drop urine-only agents from organism first/second/third-line *guidance display*
    on non-urine sites (they reach therapeutic levels only in urine). The ranking side
    already strips these from `allowed`; this keeps the reference list honest too.
    Norfloxacin keeps an enteric (GI) role, so it is retained for Stool."""
    # Uses the canonical classifier so that this display filter cannot drift away
    # from the therapeutic filter in analyze_antibiotics -- they must agree on
    # what counts as urine, or the reference list contradicts the recommendation.
    cat = classify_specimen(specimen)
    if cat == "urine":
        return list(names or [])
    drop = {"nitrofurantoin", "fosfomycin"}
    if cat != "stool":
        drop = drop | {"norfloxacin"}
    return [n for n in (names or []) if n.lower().strip() not in drop]


def _drop_tested_ns(names, sir_map):
    """Drop agents this isolate tested non-susceptible (I / SDD / R) -- v7.0.

    The text report printed the organism's GENERIC first line (Klebsiella:
    TMP-SMX, amoxicillin-clavulanate, cefuroxime) under the AST of an isolate
    resistant to all three. After the AST, a first-line list must agree with it.
    """
    sm = {str(k).strip().lower(): str(v or "").strip().upper() for k, v in (sir_map or {}).items()}
    return [n for n in (names or []) if sm.get(str(n).strip().lower(), "") not in ("I", "R", "SDD")]
