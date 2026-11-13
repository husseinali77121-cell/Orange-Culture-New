# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Creatinine clearance, paediatric eGFR and renal-severity helpers."""
from typing import Optional
from typing import Tuple




def calc_creatinine_clearance(age: int, weight: float, scr: float, sex: str) -> float:
    if scr <= 0:
        return 0.0
    crcl = ((140 - age) * weight) / (72 * scr)
    if sex == "Female":
        crcl *= 0.85
    # Cockcroft-Gault goes negative past age 140. The widget caps age at 120 so
    # this cannot fire today, but a negative clearance would satisfy every
    # `cl_cr <= renal_limit` test at once and print "CrCl -14 ml/min" in the
    # report, so clamp at the source rather than trusting the caller.
    return max(0.0, crcl)

def calc_paediatric_egfr(height_cm: Optional[float], scr: Optional[float],
                         age_years: Optional[float],
                         age_months: Optional[int] = None) -> Optional[float]:
    """Paediatric eGFR (ml/min/1.73 m²) -- bedside Schwartz, or None.

    Added 2026-11-11 (round 4). Cockcroft-Gault is an ADULT equation; in a
    child it is driven by body weight and badly underestimates clearance (a
    healthy 3.5 kg neonate with SCr 0.5 came out at ~14 ml/min).
      * 1-17 years: bedside Schwartz (CKiD, Schwartz et al. JASN 2009),
        eGFR = 0.413 x height(cm) / SCr(mg/dL)
      * under 1 year: the original Schwartz constant for TERM infants, 0.45
        (0.33 applies to pre-term infants, which this form cannot tell apart).
    Returns None without a height -- the equation cannot be applied.
    """
    try:
        h = float(height_cm or 0)
        s = float(scr or 0)
    except (TypeError, ValueError):
        return None
    if h <= 0 or s <= 0:
        return None
    infant = (age_months is not None) or (age_years is not None and age_years < 1)
    k = 0.45 if infant else 0.413
    return round(k * h / s, 1)

# ── UNKNOWN vs NORMAL CLEARANCE ──────────────────────────────────────────────
# The defect this replaces: the sidebar set `cl_cr = 100.0` whenever serum
# creatinine was left at 0, and 100 ml/min is not "unknown", it is a normal
# clearance. So a clinician who TICKED "Renal Impairment" but did not have the
# creatinine to hand got:
#   * no renal dose-adjustment note on any agent (no renal_limit reaches 100),
#   * Nitrofurantoin RECOMMENDED rather than refused,
#   * and a report line reading "Renal: IMPAIRED  CrCl: 100" — an asserted
#     normal number, which is worse than printing nothing.
# Measured against a real CrCl of 25 the same panel went from 19 recommended
# agents to 6. The flag did nothing at all except add a reassuring caption.
#
# `None` now means "not measured". When the impairment flag is set we substitute
# ASSUMED_CRCL_UNKNOWN, which is the same 30 ml/min convention clinical_matrix
# already used, so the two layers agree instead of one assuming 30 and the other
# 100. Every string that quotes a substituted number says it was ASSUMED.
ASSUMED_CRCL_UNKNOWN: float = 30.0

def resolve_crcl(cl_cr: Optional[float], is_renal: bool) -> Tuple[Optional[float], bool]:
    """(effective CrCl, was_measured). None means no renal branch applies."""
    if cl_cr is not None:
        return float(cl_cr), True
    return (ASSUMED_CRCL_UNKNOWN, False) if is_renal else (None, False)

def crcl_label(cl_cr: Optional[float], is_renal: bool = False,
               lang: str = "en") -> str:
    """CrCl for display. Never presents an assumed value as a measured one."""
    eff, measured = resolve_crcl(cl_cr, is_renal)
    if eff is None:
        return "غير مطلوب" if lang == "ar" else "not applicable"
    if measured:
        return f"{eff:.1f} ml/min"
    if lang == "ar":
        return (f"غير مقيسة (لم يُدخل الكرياتينين) — الجرعات محسوبة على "
                f"افتراض CrCl ≈ {eff:.0f} مل/د")
    return (f"not measured (no creatinine entered) — dosing assumes "
            f"CrCl ≈ {eff:.0f} ml/min")

def get_renal_severity(crcl: Optional[float]) -> str:
    # KDIGO G-stages rather than three home-made bands. The old table called
    # CrCl 200 "Mild" and lumped G4 (15-29) together with dialysis-dependent G5,
    # which are not the same dosing problem.
    if crcl is None:
        return "Unknown"
    if crcl >= 90:
        return "Normal (G1)"
    if crcl >= 60:
        return "Mild (G2)"
    if crcl >= 30:
        return "Moderate (G3)"
    if crcl >= 15:
        return "Severe (G4)"
    return "Kidney failure (G5)"
