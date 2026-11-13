# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Contradictions in the patient inputs themselves."""
from typing import List
from typing import Optional




def validate_patient_context(age: int, sex: str, is_preg: bool,
                             cl_cr: float, age_months: Optional[int] = None
                             ) -> List[str]:
    """Contradictions in the patient inputs themselves.

    Nothing checked these. A pregnancy flag on a male patient, a negative age or
    an impossible creatinine clearance all ran to completion and silently
    reshaped the entire recommendation list -- the pregnancy flag alone bans
    thirteen agents. A clinical tool should say when its inputs cannot all be
    true at once.
    """
    problems: List[str] = []
    if is_preg and str(sex).strip().lower() in ("male", "ذكر", "m"):
        problems.append("⚠️ عُلِّم الحمل مع جنس «ذكر» — راجع بيانات المريض "
                        "(علامة الحمل وحدها تحظر 13 دواءً).")
    if is_preg and age is not None and 0 <= age < 10:
        problems.append(f"⚠️ عُلِّم الحمل مع عمر {age} سنة — راجع بيانات المريض.")
    if age is not None and age < 0:
        problems.append(f"⚠️ العمر المُدخَل سالب ({age}).")
    if age is not None and age > 120:
        problems.append(f"⚠️ العمر المُدخَل غير معقول ({age} سنة).")
    if age_months is not None and not (0 <= age_months <= 11):
        problems.append(f"⚠️ العمر بالشهور خارج النطاق 0–11 ({age_months}).")
    if cl_cr is not None and cl_cr < 0:
        problems.append(f"⚠️ تصفية الكرياتينين سالبة ({cl_cr:.0f}).")
    if cl_cr is not None and cl_cr > 250:
        problems.append(f"⚠️ تصفية الكرياتينين غير معقولة ({cl_cr:.0f} mL/min) — "
                        "راجع الوزن والكرياتينين المُدخَلين.")
    return problems
