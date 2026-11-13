# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Egyptian-market brand names for each generic agent."""
from typing import Dict

from cdss.formulary.abx_guidelines import ABX_ALIAS_INDEX
from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.formulary.abx_guidelines import normalize_abx_key


# ── Commercial Names Loader ───────────────────────────────────────────
def load_commercial_names(filepath: str = "commercial_names.txt") -> Dict[str, str]:
    """Loads commercial names -- multi-path search for Streamlit Cloud compatibility."""
    import os as _os
    result: Dict[str, str] = {}
    # __file__ may be undefined in some exec contexts -> guard it
    try:
        _base = _os.path.dirname(_os.path.abspath(__file__))
    except NameError:
        _base = _os.getcwd()
    for _p in [filepath,
                _os.path.join(_base, filepath),
                _os.path.join(_os.getcwd(), filepath)]:
        try:
            with open(_p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        g, _, b = line.partition("=")
                        g, b = g.strip(), b.strip()
                        if g and b:
                            result[g.lower()] = b
            if result:
                break
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return result

COMMERCIAL_NAMES: Dict[str, str] = load_commercial_names()

# The brand file and ABX_GUIDELINES spell combination drugs differently
# ("Amoxicillin-Clavulanate" vs "Amoxicillin + Clavulanic acid",
# "Ampicillin-Sulbactam" vs "Ampicillin/Sulbactam"). An exact lowercase lookup
# therefore returned NOTHING for 11 of 51 agents -- including Augmentin, Unasyn,
# Tazocin, Tienam and Septrin, the brands an Egyptian clinician is most likely to
# want. Resolve through the same normalisation and alias index the OCR uses, so
# either spelling finds the entry.
_COMMERCIAL_BY_KEY: Dict[str, str] = {}

for _g, _b in COMMERCIAL_NAMES.items():
    _COMMERCIAL_BY_KEY[normalize_abx_key(_g)] = _b
    _canon = ABX_ALIAS_INDEX.get(normalize_abx_key(_g))
    if _canon:
        _COMMERCIAL_BY_KEY.setdefault(normalize_abx_key(_canon), _b)

def get_commercial_name(generic: str) -> str:
    if not generic:
        return ""
    direct = COMMERCIAL_NAMES.get(generic.lower(), "")
    if direct:
        return direct
    key = normalize_abx_key(generic)
    if key in _COMMERCIAL_BY_KEY:
        return _COMMERCIAL_BY_KEY[key]
    # Last resort: the drug's own declared aliases (e.g. "augmentin").
    for _alias in (ABX_GUIDELINES.get(generic, {}) or {}).get("aliases", []):
        hit = _COMMERCIAL_BY_KEY.get(normalize_abx_key(_alias))
        if hit:
            return hit
    return ""
