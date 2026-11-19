# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Intrinsic-resistance lookups (single source of truth: clinical_data.INTRINSIC_RESISTANCE)."""
from typing import Any
from typing import Dict

from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.health import (
    INTRINSIC_RESISTANCE,
)
from cdss.therapy.tables import (
    ORGANISM_AVOID_CLASS_MAP,
)


# =========================================================
# التحليل السريري
# =========================================================
def is_intrinsically_avoided(organism_type: str, drug_name: str, drug_info: Dict[str, Any],
                             return_source: bool = False):
    """True if the drug is on the organism's avoid list.

    With return_source=True: 'intrinsic' | 'profile' | None -- WHY it is avoided.

    2026-11-10: split out so the UI can say "intrinsic resistance" only when it
    is true. The ORGANISM_PROFILE avoid lists also hold "not recommended"
    entries (poor clinical efficacy despite in-vitro activity), and every one
    of them used to be shown to the physician as intrinsic resistance.
    """
    # ── FIX: the reconciled intrinsic-resistance table first ──────────────────
    # (v7.3 wording: INTRINSIC_RESISTANCE is the program's reconciled table --
    # CLSI M100 Ed36 first, EUCAST Expected Resistant Phenotypes v3.3 where CLSI
    # is silent, each row with its own source in guideline_registry / the
    # EUCAST audit. It is checked before the per-organism profile.)
    # The per-organism ORGANISM_PROFILE["avoid"] list was incomplete for
    # P. aeruginosa (missing Doxycycline and the intrinsically-inactive
    # cephalosporins), so drugs like Doxycycline (reported I) leaked into
    # "Use with caution" and Cephalexin was mis-tagged via the beta-lactamase path
    # instead of being flagged as intrinsic. Checking INTRINSIC_RESISTANCE here
    # guarantees a name-level intrinsic hit routes straight to Avoid, and keeps
    # a single source of truth shared with MDR-stripping and mechanism inference.
    _org_l = (organism_type or "").lower().strip()
    for _org_key, _drug_list in INTRINSIC_RESISTANCE.items():
        # Same length guard as _remove_intrinsic_resistance -- without it an
        # unreadable organism name banned every drug that is intrinsic to ANY
        # organism in the table.
        if not _org_key:
            continue
        if (_org_key in _org_l or (len(_org_l) >= 4 and _org_l in _org_key)) \
                and drug_name in _drug_list:
            return "intrinsic" if return_source else True

    _prof = ORGANISM_PROFILE.get(organism_type) or {}
    # 2026-11-10: a class-wide avoid ("Cephalosporins" for MRSA) must not
    # catch the deliberate exception (Ceftaroline binds PBP2a).
    if drug_name in (_prof.get("avoid_exempt") or []):
        return None if return_source else False
    organism_avoid = _prof.get("avoid", [])
    d_low   = drug_name.lower()
    d_class = (drug_info or {}).get("class", "").lower()
    for avoid_item in organism_avoid:
        av_low = avoid_item.lower().strip()
        if av_low in d_low or d_low in av_low:
            return "profile" if return_source else True
        mapped = ORGANISM_AVOID_CLASS_MAP.get(av_low)
        if mapped and any(cls in d_class for cls in mapped):
            return "profile" if return_source else True
    return None if return_source else False

def build_banned_item(name: str, category: str, reason_short: str, reason_detail: str) -> Dict[str, str]:
    return {"name": name, "category": category,
            "reason_short": reason_short, "reason_detail": reason_detail}

# mecA (MRSA) and vanA/vanB (VRE) are ACQUIRED mechanisms, not intrinsic ones.
# They live in INTRINSIC_RESISTANCE under the pseudo-species keys "mrsa"/"vre"
# because that table also drives the therapeutic Avoid list, where banning every
# beta-lactam on an MRSA is exactly right. But Magiorakos strips only INTRINSIC
# categories before counting, and counts acquired resistance. Leaving these rows
# in place for the MDR pass deleted the very categories that define the
# phenotype: an isolate reported as "VRE" lost its Glycopeptides category and
# came back level=None, while the SAME isolate reported as "Enterococcus
# faecium" came back MDR. One isolate must not get two answers because of how
# the lab typed its name.
_ACQUIRED_NOT_INTRINSIC = {
    "mrsa": {"Oxacillin", "Penicillin", "Cefoxitin", "Ampicillin", "Amoxicillin",
             "Amoxicillin + Clavulanic acid", "Ampicillin/Sulbactam",
             "Piperacillin + Tazobactam", "Cephalexin", "Cefadroxil", "Cephradine",
             "Cefazolin", "Cefaclor", "Cefuroxime", "Cefuroxime sodium",
             "Ceftriaxone", "Cefotaxime", "Cefixime", "Ceftazidime", "Cefepime",
             "Cefoperazone", "Cefoperazone + Sulbactam",
             "Imipenem/Cilastatin", "Meropenem", "Ertapenem"},
    "vre":  {"Vancomycin", "Teicoplanin"},
}

def _remove_intrinsic_resistance(organism: str, sir_map: Dict[str, str],
                                 keep_acquired: bool = False) -> Dict[str, str]:
    """Drop drugs the organism is intrinsically resistant to (not acquired).

    keep_acquired=True (used by classify_mdr) additionally keeps the agents whose
    resistance on that row is an ACQUIRED mechanism, so the MDR/XDR count sees
    them. Everything else -- the Avoid list, mechanism inference -- keeps the
    default and still strips the whole row.
    """
    org_l = (organism or "").lower().strip()
    drugs_to_drop = set()
    for org_key, drug_list in INTRINSIC_RESISTANCE.items():
        if not org_key:
            continue
        # Reverse containment (`org_l in org_key`) exists so that "proteus"
        # picks up "proteus mirabilis". Ungated, it also makes EVERY key match a
        # blank or 1-2 character name: `"" in "escherichia coli"` is True, so an
        # organism the OCR failed to read stripped the ENTIRE panel and
        # classify_mdr came back level=None with total_tested=0 -- a silent
        # false-negative on the MDR alert. A genus fragment is never shorter
        # than four characters.
        if org_key in org_l or (len(org_l) >= 4 and org_l in org_key):
            _row = set(drug_list)
            if keep_acquired:
                _row -= _ACQUIRED_NOT_INTRINSIC.get(org_key, set())
            drugs_to_drop.update(_row)
    if not drugs_to_drop:
        return dict(sir_map)
    return {d: v for d, v in sir_map.items() if d not in drugs_to_drop}
