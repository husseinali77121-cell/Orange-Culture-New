# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Does the case entered in the app match the laboratory report? (v7.4)

DEFECT THIS CLOSES (external case review, 2026-11-20)
The laboratory report printed "Sample: Mid stream urine". The pathogenicity
panel had "Indwelling catheter (Foley)" selected, so every catheter rule ran:
the CA-UTI count threshold (>= 10^3 with symptoms), "replace the catheter if
>= 2 weeks and re-culture", the CA-UTI protocol and duration, and a cUTI
classification that moved nitrofurantoin to "caution". Nothing compared the
two: the OCR read only the specimen TYPE ("Urine") and threw the collection
method away.

Now:
  * `collection_group()` reduces any wording (lab report or app) to one group;
  * `detect_collection_method()` reads the method from the report text (OCR);
  * `check_case_consistency()` returns a CRITICAL issue when the two disagree,
    when the report states a method and none was entered (v7.5), or when the
    report says "voided / midstream" while a urinary catheter is recorded as a
    host factor. A critical issue blocks the physician-facing
    reports until the inputs are corrected or the physician confirms the
    entered method (the confirmation is printed).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

# group -> the label used by the pathogenicity panel (URINE_COLLECTION_METHODS)
GROUP_LABEL = {
    "voided": "Midstream clean-catch",
    "indwelling": "Indwelling catheter (Foley)",
    "intermittent": "Intermittent catheterisation (in-out / CIC)",
    "suprapubic_catheter": "Suprapubic catheter",
    "spa": "Suprapubic aspirate (SPA)",
    "condom": "Condom catheter",
    "bag": "Bag specimen (infant)",
    "nephrostomy": "Nephrostomy / Ileal conduit",
}
# Groups in which a urinary catheter is in place (CA-UTI rules apply).
CATHETER_GROUPS = frozenset({"indwelling", "intermittent", "suprapubic_catheter"})

# Order matters: the more specific phrase first ("suprapubic catheter" before
# "suprapubic", "catheter" last of all).
_PATTERNS = (
    ("nephrostomy", r"nephrostom|ileal\s*conduit|urostom|\bconduit\b"),
    ("condom", r"condom"),
    ("bag", r"\bbag\b|u[\s\-]?bag|كيس"),
    ("suprapubic_catheter", r"supra[\s\-]?pubic\s+cath|\bspc\b"),
    ("spa", r"supra[\s\-]?pubic(\s+(needle\s+)?aspirat)?|\bspa\b"),
    ("intermittent", r"intermittent|in[\s\-]?(and[\s\-])?out|\bcic\b|\bisc\b|straight\s+cath"),
    ("indwelling", r"indwelling|foley|\bcsu\b|catheter\s+(urine|specimen|sample)|"
                   r"(urine|specimen|sample)\s+(from|via)\s+(the\s+)?catheter|قسطرة"),
    ("voided", r"mid[\s\-]?stream|\bmsu\b|clean[\s\-]?catch|\bvoided\b|منتصف\s*(ال)?(تبول|بول)"),
)
_NOT_STATED = ("", "مش محدد", "not stated", "unknown", "none", "n/a")


def collection_group(text: Any) -> Optional[str]:
    """One group for any wording of a urine collection method, or None."""
    t = str(text or "").strip().lower()
    if t in _NOT_STATED:
        return None
    for group, rx in _PATTERNS:
        if re.search(rx, t):
            return group
    if re.search(r"cathet", t):
        return "indwelling"
    return None


def detect_collection_method(text: str) -> Optional[str]:
    """The urine collection method printed on a laboratory report, as a panel label.

    The labelled field first ("Sample : Mid stream urine"); otherwise an
    unambiguous phrase anywhere in the text. None when the report does not say.
    """
    t = str(text or "").lower()
    for m in re.finditer(r"(?:specimen|sample|collection|type of specimen|نوع العينة|العينة)"
                         r"\s*(?:type|method)?\s*[:\-]\s*([^\n|]{2,60})", t):
        g = collection_group(m.group(1))
        if g:
            return GROUP_LABEL[g]
    # Outside a labelled field only unambiguous English phrases count -- a stray
    # word elsewhere on the page (a footer, an advert) must not raise an alert.
    for group, rx in _UNLABELLED:
        if re.search(rx, t):
            return GROUP_LABEL[group]
    return None


_UNLABELLED = (
    ("voided", r"mid[\s\-]?stream\s+urine|\bmsu\b|clean[\s\-]?catch"),
    ("indwelling", r"\bfoley\b|indwelling\s+cath|\bcsu\b|catheter\s+(urine|specimen)"),
    ("suprapubic_catheter", r"supra[\s\-]?pubic\s+cath"),
    ("intermittent", r"intermittent\s+cath|in[\s\-]?(and[\s\-])?out\s+cath"),
    ("nephrostomy", r"nephrostom|ileal\s*conduit"),
)


def check_case_consistency(*, specimen: str, report_collection: Optional[str],
                           entered_collection: Optional[str],
                           host_factors: Optional[Iterable[str]] = None,
                           confirmed: bool = False) -> List[Dict[str, Any]]:
    """Critical disagreements between the laboratory report and the entered case.

    Each issue: {code, severity, blocking, message_en, message_ar, report_value,
    entered_value}. `blocking` is False once the physician has `confirmed` the
    entered method (the issue is still returned, so the confirmation is printed).
    """
    from cdss.common.specimen import classify_specimen
    if classify_specimen(specimen) != "urine":
        return []
    # NB: the checks that do not need the laboratory report (entry vs host
    # factors) run even when the OCR read no method (v7.6).
    rg = collection_group(report_collection)
    eg = collection_group(entered_collection)
    hf_cath = any("urinary catheter" in str(h).lower() for h in (host_factors or []))
    issues: List[Dict[str, Any]] = []
    if rg and not eg:
        # v7.5 (external review of v7.4): "not entered" was read as "no conflict".
        # v7.6 (external review of v7.5): and a physician "confirmation" released
        # it -- confirming a method that was never entered. Not confirmable: the
        # only way out is to select the method (`confirmable` False, always blocking).
        issues.append(_issue(
            "SPECIMEN_COLLECTION_NOT_ENTERED", report_collection, entered_collection or "not entered",
            False, confirmable=False,
            en=(f"The laboratory report says '{report_collection}', but no collection method was "
                "entered for the case - the threshold and the catheter (CA-UTI) rules were applied "
                "without it."),
            ar=(f"تقرير المعمل بيقول «{report_collection}» لكن طريقة الجمع مش متحددة في البرنامج — "
                "العتبة وقواعد القسطرة اتطبقت من غيرها.")))
    if rg and eg and rg != eg:
        issues.append(_issue(
            "SPECIMEN_COLLECTION_MISMATCH", report_collection, entered_collection, confirmed,
            en=(f"Collection method mismatch: the laboratory report says "
                f"'{report_collection}', the case was entered as '{entered_collection}'. "
                "The threshold, the catheter (CA-UTI) rules, the UTI classification and the "
                "duration all depend on it."),
            ar=(f"تعارض في طريقة جمع العينة: تقرير المعمل «{report_collection}» والبرنامج "
                f"«{entered_collection}». العتبة وقواعد القسطرة (CA-UTI) وتصنيف الـ UTI والمدة "
                "كلها بتعتمد عليها.")))
    if rg == "voided" and hf_cath and eg not in CATHETER_GROUPS:
        issues.append(_issue(
            "SPECIMEN_VOIDED_WITH_CATHETER", report_collection, "Urinary catheter (host factor)",
            confirmed,
            en=("The laboratory report says a voided / midstream specimen, but a urinary "
                "catheter is recorded as a host factor - the catheter rules are being applied "
                "to a voided specimen."),
            ar=("تقرير المعمل بيقول عينة midstream / تبول، لكن «Urinary catheter» متسجلة في "
                "عوامل المضيف — قواعد القسطرة بتتطبق على عينة تبول.")))
    elif eg == "voided" and hf_cath:
        # v7.6 (external review of v7.5): the same contradiction inside the entry
        # itself, when the OCR could not read the report. It may be real (the
        # catheter was removed and a midstream specimen taken -- IDSA CA-UTI
        # 2009), so it can be confirmed; it cannot pass unseen.
        issues.append(_issue(
            "SPECIMEN_ENTRY_VOIDED_WITH_CATHETER", "", entered_collection,
            confirmed,
            confirmed_en=(f"'{entered_collection}' analysed with a urinary catheter recorded as a "
                          "host factor (e.g. catheter removed before a midstream specimen)."),
            en=("A midstream / voided specimen was entered, but a urinary catheter is recorded "
                "as a host factor - is the catheter still in place?"),
            ar=("اتدخلت عينة midstream / تبول، لكن «Urinary catheter» متسجلة في عوامل المضيف — "
                "القسطرة لسه موجودة؟")))
    return issues


def _issue(code, report_value, entered_value, confirmed, *, en, ar,
           confirmable: bool = True, confirmed_en: str = "") -> Dict[str, Any]:
    confirmed = bool(confirmed) and confirmable
    return {
        "code": code, "severity": "critical", "blocking": not confirmed,
        "confirmed": confirmed, "confirmable": confirmable,
        # what the reports print once the physician confirmed it
        "confirmed_en": confirmed_en or (f"analysed as '{entered_value}' although the laboratory "
                                         f"report says '{report_value}'."),
        "report_value": str(report_value or ""), "entered_value": str(entered_value or ""),
        "message_en": en, "message_ar": ar,
        # IDSA CA-UTI 2009 also accepts a midstream specimen within 48 h of
        # catheter removal -- the one legitimate reason for the two to differ.
        "hint_en": ("Correct the entry, or confirm it: e.g. the catheter was removed within the "
                    "previous 48 h and a midstream specimen was taken (IDSA CA-UTI 2009)."),
        "hint_ar": ("صحّح الإدخال أو أكّده: مثلاً القسطرة اتشالت خلال آخر 48 ساعة واتاخدت عينة "
                    "midstream (IDSA CA-UTI 2009)."),
    }


def blocking(issues: Optional[List[Dict[str, Any]]]) -> bool:
    return any(i.get("blocking") for i in (issues or []))


def report_lines_en(issues: Optional[List[Dict[str, Any]]]) -> List[str]:
    """One line per issue for the reports: the alert, or the physician's confirmation."""
    out: List[str] = []
    for i in issues or []:
        if i.get("confirmed"):
            out.append("DATA CHECK - physician confirmed: " + i["confirmed_en"])
        else:
            out.append("CRITICAL DATA MISMATCH - " + i["message_en"])
    return out


__all__ = ["collection_group", "detect_collection_method", "check_case_consistency",
           "blocking", "report_lines_en", "GROUP_LABEL", "CATHETER_GROUPS"]
