# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""QA confidence score from QC findings."""
from typing import Any
from typing import Dict
from typing import List




def compute_qa_confidence(
    qc_issues: List[Dict[str, Any]],
    sir_map: Dict[str, str],
    organism: str,
) -> Dict[str, Any]:
    """
    Confidence Score للتوصية العلاجية — بناءً على:
      1. عدد وشدة الـ QA issues (errors تخفض أكتر من warnings)
      2. اكتمال الـ AST panel (عدد المضادات المختبرة)
    يرجع: {level, score, icon, color, reasons}
    """
    score   = 100
    reasons = []

    n_errors   = sum(1 for i in qc_issues if i.get("severity") == "error")
    n_warnings = sum(1 for i in qc_issues if i.get("severity") == "warning")

    if n_errors:
        score -= n_errors * 30
        reasons.append(f"{n_errors} تناقض حرج (error) في نتائج الـ AST")
    if n_warnings:
        score -= n_warnings * 12
        reasons.append(f"{n_warnings} ملاحظة (warning) تستدعي المراجعة")

    n_tested = len(sir_map) if sir_map else 0
    if n_tested == 0:
        score -= 50
        reasons.append("لا توجد نتائج AST مدخلة")
    elif n_tested <= 2:
        score -= 35
        reasons.append(f"عدد المضادات المختبرة قليل جداً ({n_tested}) -- لا يكفي لتوصية موثوقة")
    elif n_tested < 5:
        score -= 20
        reasons.append(f"عدد المضادات المختبرة قليل ({n_tested}) -- قد لا يغطي كل الخيارات العلاجية")
    elif n_tested < 8:
        score -= 8
        reasons.append(f"عدد المضادات المختبرة محدود ({n_tested})")

    score = max(0, min(100, score))

    if score >= 80:
        level, icon, color = "High Confidence",     "🟢", "#1e8449"
    elif score >= 50:
        level, icon, color = "Moderate Confidence", "🟡", "#b7770d"
    else:
        level, icon, color = "Low Confidence",      "🔴", "#922b21"

    if not reasons:
        reasons.append("لا توجد مشاكل مكتشفة -- تقرير AST مكتمل ومتسق")

    return {
        "level":      level,  "icon":  icon,  "color": color,
        "score":      score,  "reasons": reasons,
        "n_errors":   n_errors, "n_warnings": n_warnings, "n_tested": n_tested,
    }
