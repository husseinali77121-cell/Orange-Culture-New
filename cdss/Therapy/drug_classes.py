# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Drug-class predicates used by the therapy rules (pure functions of a formulary row)."""
from typing import Dict


def _cls_and_name(info_dict: Dict, drug_name: str = "") -> str:
    """Class text PLUS drug name, lower-cased, for robust matching.

    Matching on the class string alone silently mis-sorted any drug whose
    class was phrased differently from the token being searched for.
    """
    c = (info_dict.get("class") or "").lower()
    n = (drug_name or info_dict.get("name") or "")
    return f"{c} | {str(n).lower()}"

_BLI_TOKENS = ("bli", "tazobactam", "sulbactam", "clavulan", "avibactam",
               "relebactam", "vaborbactam", "inhibitor")

def _is_penicillin_or_ceph(info_dict: Dict, drug_name: str = "") -> bool:
    """True for the beta-lactams an ESBL / AmpC hydrolyses.

    FIX 2026-08-01: the token list was penicillin / cephalosporin / cillin /
    cef / ceph. Aztreonam's class string is "Monobactam (IV)" and its name
    contains none of those substrings, so it matched NOTHING -- while the
    docstring of this very function's caller states that an ESBL is
    "resistant to ALL penicillins + cephalosporins (+ aztreonam)". A
    confirmed-ESBL Klebsiella bacteraemia therefore came back with
    Aztreonam in the RECOMMENDED bucket, and the terminal safety gate did
    not catch it either. Aztreonam is an oxyimino beta-lactam -- it is the
    classic ESBL substrate and CLSI uses it as an ESBL screening agent.
    """
    t = _cls_and_name(info_dict, drug_name)
    if "carbapenem" in t or "penem" in t:
        return False
    if any(k in t for k in _BLI_TOKENS):
        return False   # BLI combos handled separately (UTI-only caution)
    return any(k in t for k in ("penicillin", "cephalosporin", "cephalosporins",
                                "cillin", "cef", "ceph",
                                "monobactam", "aztreonam"))

def _is_bli_combo(info_dict: Dict, drug_name: str = "") -> bool:
    t = _cls_and_name(info_dict, drug_name)
    if "carbapenem" in t or "relebactam" in t or "vaborbactam" in t:
        return False          # carbapenem/BLI pairs handled by _is_carbapenem
    return any(k in t for k in _BLI_TOKENS)

def _is_carbapenem(info_dict: Dict) -> bool:
    return "carbapenem" in info_dict.get("class", "").lower()
