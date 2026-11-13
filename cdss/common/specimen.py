# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""The single specimen classifier (urine / blood / sputum / ...)."""



# ─────────────────────────────────────────────────────────────────────────
# Canonical specimen classifier — SINGLE SOURCE OF TRUTH for all routing.
# Prevents the same specimen being bucketed differently by different engines
# (pathogenicity / severity / syndrome / treatment-duration).
# Keyword order encodes clinical priority — e.g. a "Rectal Swab" is GI (rectal)
# before it is a wound (swab); a "Tracheal aspirate" is respiratory (tracheal)
# before anything else.
# ─────────────────────────────────────────────────────────────────────────
_SPECIMEN_CATEGORY_RULES = [
    # (category, [keywords])  — checked top-to-bottom; FIRST HIT WINS, so the
    # order below is load-bearing: the generic "swab" keyword sits in the LAST
    # rule precisely so that "throat swab" and "nasopharyngeal swab" are claimed
    # by the respiratory rule above it. Before this fix "throat swab" fell into
    # 'wound', which routed an upper-respiratory isolate through soft-tissue
    # logic. Anything genuinely unrecognised still returns '' and every caller
    # must treat '' as fail-closed, never as "no restriction".
    ("blood",   ["blood culture", "blood", "bacteraem", "bacterem", "septicaem"]),
    ("csf",     ["csf", "cerebrospinal", "lumbar puncture", "نخاعي"]),
    ("urine",   ["urine", "mid-stream", "midstream", "msu", "catheter specimen", "بول"]),
    ("sputum",  ["sputum", "respiratory", "tracheal", "endotracheal", "bronch", "bal",
                 "throat", "pharyn", "nasopharyn", "tonsil", "بلغم", "حلق"]),
    ("stool",   ["stool", "fecal", "faecal", "feces", "faeces", "rectal", "براز"]),
    ("abdomen", ["abdomen", "abdominal", "periton", "ascit", "bile", "biliary"]),
    ("pus",     ["pus", "abscess", "empyema", "صديد", "خراج"]),
    ("wound",   ["wound", "tissue", "swab", "ulcer", "burn", "skin", "جرح", "مسحة"]),
]

def classify_specimen(specimen: str) -> str:
    """Return the canonical specimen category for any specimen string.

    One of: 'urine','sputum','blood','csf','stool','abdomen','pus','wound', or ''.
    Every routing engine dispatches on this so a given specimen is always
    bucketed identically.
    """
    s = (specimen or "").lower()
    for category, keywords in _SPECIMEN_CATEGORY_RULES:
        if any(k in s for k in keywords):
            return category
    return ""

_SPEC_CAT_TO_TYPE = {"urine": "Urine", "blood": "Blood", "sputum": "Sputum",
                     "wound": "Wound Swab", "pus": "Pus", "stool": "Stool", "csf": "CSF",
                     "abdomen": "Pus"}
