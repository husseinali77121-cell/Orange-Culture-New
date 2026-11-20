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
                           confirmed: Any = False) -> List[Dict[str, Any]]:
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
    # v7.8: `confirmed` may be the set of codes the physician confirmed (each
    # issue its own confirmation); a bool still means "all of them"
    confirmed = _confirmed(confirmed, code) and confirmable
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


# ═════════════════════════════════════════════════════════════════════════
# v7.8 -- contradictions INSIDE the case inputs (owner's request after the
# external review of v7.7: "protect the program against conflicts in the
# inputs themselves"). Same issue format and the same release rule as above:
#   * IMPOSSIBLE (not confirmable): fix the entry -- nothing releases meanwhile;
#   * IMPLAUSIBLE (confirmable): released only after the physician confirms
#     THAT issue (each its own confirmation, printed in the reports).
# ═════════════════════════════════════════════════════════════════════════
# Weight plausible for age -- wide on purpose: it catches a typo or a unit slip
# (a dose is computed from it), not an unusual patient. (age upper bound, min, max)
_WEIGHT_FOR_AGE = ((1, 1.0, 15.0), (3, 6.0, 25.0), (6, 9.0, 40.0), (12, 13.0, 100.0),
                   (18, 22.0, 180.0), (200, 30.0, 250.0))


def _confirmed(confirmed: Any, code: str) -> bool:
    """True / False for every issue, or the set of codes the physician confirmed."""
    if isinstance(confirmed, (set, frozenset, list, tuple)):
        return code in confirmed
    return bool(confirmed)


def _input_issue(code, entered, report, confirmed, *, en, ar, hint_ar,
                 confirmable=True, confirmed_en=""):
    i = _issue(code, report, entered, _confirmed(confirmed, code), en=en, ar=ar,
               confirmable=confirmable,
               confirmed_en=confirmed_en or f"{en} -- confirmed by the physician.")
    i["hint_ar"] = hint_ar
    i["hint_en"] = "Correct the entry" + (", or confirm it." if confirmable else ".")
    i["kind"] = "input"
    return i


def _org_tokens(name: Any) -> List[str]:
    t = re.sub(r"[^a-z ]+", " ", str(name or "").lower().replace("spp", " "))
    return [w for w in t.split() if w]


def same_organism(a: Any, b: Any) -> bool:
    """'E. coli' = 'Escherichia coli'; 'Klebsiella' (genus) = 'Klebsiella pneumoniae'."""
    x, y = _org_tokens(a), _org_tokens(b)
    if not x or not y:
        return True                                   # nothing to compare
    if x == y or " ".join(x) in " ".join(y) or " ".join(y) in " ".join(x):
        return True
    if len(x) >= 2 and len(y) >= 2 and x[1] == y[1]:
        return x[0][0] == y[0][0]                      # genus initial + species
    return False


def check_case_inputs(patient: Any, *, specimen: str = "", organism: str = "",
                      panel: Optional[Dict[str, Any]] = None,
                      symptoms: Optional[Iterable[str]] = None,
                      report: Optional[Dict[str, Any]] = None,
                      confirmed: Any = False) -> List[Dict[str, Any]]:
    """Contradictions between the inputs, and between the inputs and the
    laboratory report the OCR read. [] when the case is coherent."""
    from cdss.common.specimen import classify_specimen
    out: List[Dict[str, Any]] = []
    rep = report or {}
    sex = str(getattr(patient, "sex", "") or "")
    age = getattr(patient, "effective_age_years", None)
    preg = bool(getattr(patient, "is_pregnant", False))
    hosts = [str(h) for h in (getattr(patient, "host_factors", None) or [])]

    # ── pregnancy ─────────────────────────────────────────────────────────
    if preg and sex.lower().startswith("m"):
        out.append(_input_issue(
            "INPUT_PREGNANCY_MALE", "pregnant, male", "", False, confirmable=False,
            en="Pregnancy is recorded for a male patient.",
            ar="حمل مُسجَّل لمريض ذكر.", hint_ar="صحّح النوع أو شيل علامة الحمل."))
    if preg and age is not None and age < 10:
        out.append(_input_issue(
            "INPUT_PREGNANCY_AGE", f"pregnant, {age:g} y", "", False, confirmable=False,
            en=f"Pregnancy is recorded at {age:g} years of age.",
            ar=f"حمل مُسجَّل لعمر {age:g} سنة.", hint_ar="صحّح العمر أو شيل علامة الحمل."))
    elif preg and age is not None and (age < 12 or age > 55):
        out.append(_input_issue(
            "INPUT_PREGNANCY_AGE_UNUSUAL", f"pregnant, {age:g} y", "", confirmed,
            en=f"Pregnancy at {age:g} years -- outside the usual range.",
            ar=f"حمل في عمر {age:g} سنة — خارج المعتاد.",
            hint_ar="راجع العمر وعلامة الحمل، أو أكّدهم."))
    if "Pregnant" in hosts and not preg:
        # the pathogenicity panel's host factor with the pregnancy flag unset:
        # the score assumes pregnancy, the drug safety gates do not
        out.append(_input_issue(
            "INPUT_PREGNANT_HOST_ONLY", "host factor 'Pregnant'", "", False, confirmable=False,
            en=("'Pregnant' is ticked as a host factor but the patient is not marked "
                "pregnant -- the pregnancy drug-safety rules are not applied."),
            ar=("«Pregnant» متعلّمة في عوامل المضيف، والمريضة مش متعلّم عليها حمل — قواعد أمان "
                "الأدوية في الحمل مش شغالة."),
            hint_ar="علّم «Patient is Pregnant» في بيانات المريض، أو شيل «Pregnant» من عوامل المضيف."))

    # ── weight, renal function ───────────────────────────────────────────
    w = getattr(patient, "weight_kg", None)
    if w is not None and age is not None:
        for upper, lo, hi in _WEIGHT_FOR_AGE:
            if age < upper:
                if not (lo <= float(w) <= hi):
                    out.append(_input_issue(
                        "INPUT_WEIGHT_AGE", f"{float(w):g} kg at {age:g} y", "", confirmed,
                        en=f"Weight {float(w):g} kg is implausible at {age:g} years (doses use it).",
                        ar=f"الوزن {float(w):g} كجم غير منطقي لعمر {age:g} سنة (الجرعات بتتحسب منه).",
                        hint_ar="صحّح الوزن أو العمر، أو أكّدهم."))
                break
    crcl = getattr(patient, "cl_cr", None)
    if crcl is not None and float(crcl) < 0:
        out.append(_input_issue(
            "INPUT_CRCL_NEGATIVE", f"CrCl {float(crcl):g}", "", False, confirmable=False,
            en=f"Creatinine clearance {float(crcl):g} ml/min is impossible.",
            ar=f"CrCl {float(crcl):g} مستحيل.", hint_ar="صحّح الكرياتينين أو الوزن."))
    elif crcl is not None and float(crcl) > 250:
        out.append(_input_issue(
            "INPUT_CRCL_HIGH", f"CrCl {float(crcl):g}", "", confirmed,
            en=f"Creatinine clearance {float(crcl):g} ml/min is implausibly high (a creatinine typo?).",
            ar=f"CrCl {float(crcl):g} عالي بشكل غير منطقي (غلطة في الكرياتينين؟).",
            hint_ar="راجع الكرياتينين والوزن والعمر، أو أكّد."))

    # ── symptoms ─────────────────────────────────────────────────────────
    sym = [str(x) for x in (symptoms or [])]
    if "Asymptomatic" in sym and len(sym) > 1:
        out.append(_input_issue(
            "INPUT_SYMPTOMS_CONTRADICT", ", ".join(sym), "", False, confirmable=False,
            en="'Asymptomatic' is selected together with symptoms.",
            ar="«Asymptomatic» متختارة مع أعراض في نفس الوقت.",
            hint_ar="شيل «Asymptomatic» أو شيل الأعراض — الاتنين مع بعض بيقلبوا الحكم."))

    # ── the entry against the laboratory report (what the OCR read) ─────
    r_org = rep.get("Organism")
    if r_org and organism and not same_organism(r_org, organism):
        out.append(_input_issue(
            "INPUT_REPORT_ORGANISM", organism, r_org, confirmed,
            en=f"The report names {r_org}; the case is analysed as {organism}.",
            ar=f"التقرير مكتوب فيه {r_org}، والتحليل شغال على {organism}.",
            hint_ar="اختار الكائن اللي في التقرير، أو أكّد إن قراءة الـ OCR غلط."))
    r_spec = rep.get("Specimen")
    if r_spec and specimen:
        a, b = classify_specimen(r_spec), classify_specimen(specimen)
        if a and b and a != b:
            out.append(_input_issue(
                "INPUT_REPORT_SPECIMEN", specimen, r_spec, confirmed,
                en=f"The report says {r_spec}; the case is analysed as {specimen}.",
                ar=f"التقرير مكتوب فيه عينة {r_spec}، والتحليل شغال على {specimen}.",
                hint_ar="اختار العينة اللي في التقرير، أو أكّد إن القراءة غلط."))
    r_sex = str(rep.get("Sex") or "")
    if r_sex and sex and r_sex[:1].lower() != sex[:1].lower():
        out.append(_input_issue(
            "INPUT_REPORT_SEX", sex, r_sex, confirmed,
            en=f"The report says {r_sex}; the patient is entered as {sex}.",
            ar=f"التقرير مكتوب فيه {r_sex}، والمريض متسجّل {sex}.",
            hint_ar="صحّح النوع، أو أكّد إن القراءة غلط."))
    r_age = rep.get("Age")
    if (r_age is not None and age is not None and not rep.get("AgeAmbiguous")
            and rep.get("AgeMonths") is None):
        try:
            if abs(float(r_age) - float(age)) > 1:
                out.append(_input_issue(
                    "INPUT_REPORT_AGE", f"{age:g} y", f"{float(r_age):g} y", confirmed,
                    en=f"The report says {float(r_age):g} years; the patient is entered as {age:g}.",
                    ar=f"التقرير مكتوب فيه {float(r_age):g} سنة، والمريض متسجّل {age:g}.",
                    hint_ar="صحّح العمر، أو أكّد إن القراءة غلط."))
        except (TypeError, ValueError):
            pass
    if rep.get("NoGrowth") and panel:
        out.append(_input_issue(
            "INPUT_REPORT_NO_GROWTH", f"{len(panel)} AST results", "no growth", confirmed,
            en="The report says no growth, yet an organism and AST results are entered.",
            ar="التقرير مكتوب فيه «No growth»، ومع ذلك فيه كائن ونتائج حساسية متسجلة.",
            hint_ar="راجع التقرير: لو مفيش نمو مفيش علاج بالنتايج دي — أو أكّد إن القراءة غلط."))
    return out


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
           "check_case_inputs", "same_organism", "blocking", "report_lines_en", "GROUP_LABEL",
           "CATHETER_GROUPS"]
