# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Clinical Decision Validation Engine (v7.4).

External review of v7.3: "create an independent unit that tests the whole case,
from the specimen entered to the final report -- not each module alone".
Every module already has its own tests; what was not checked is that the
FINISHED case is coherent: that the screen, the text report and the PDF say the
same thing, that nothing resistant or untested is offered, that a systemic
infection is not offered a bladder-only agent, and so on.

validate_case() takes the run_analysis() result (and, when available, the
rendered text report and PDF HTML) and returns violations. It decides nothing
and changes nothing: an empty list means every cross-check passed; anything
else is a defect to fix before release (the page shows it in the final
checklist; tests/test_v7_4_review.py runs it over end-to-end cases).

  V01 error    an agent offered (ranked / allowed) is R or I on the AST
  V02 error    an agent ranked was not tested
  V03 error    a bladder-only agent offered for a systemic / upper-tract UTI
  V04 warning  a bladder-only agent ranked for a complicated UTI
  V05 error    suspected/confirmed ESBL: 3rd-gen cephalosporin or amox-clav ranked
  V06 error    a "do not treat" verdict, but options or a duration are present
  V07 error    low muscle mass: an aminoglycoside / vancomycin offered without the renal / TDM note
  V08 error    a drug in more than one bucket (allowed / caution / avoid / pregnancy)
  V09 error    a safety layer did not run (degraded result)
  V10 error    critical laboratory-report / case mismatch not resolved
  V11 error    the text report's RECOMMENDED / CAUTION sections differ from the analysis
               (entries are read per section, not anywhere in the report)
  V12 error    the PDF prints "ESBL+", a mechanism without its evidence level (checked
               against the mechanism result: suspected vs confirmed), or no ranking basis
  V13 error    the summary image offers an R agent (preferred, caution or reserve column), or
               lists one agent as both offered and avoided
  V14 error    an SDD the laboratory wrote on a pair CLSI defines no SDD for is still
               unresolved (v7.7: the entry form offers S / I / R only)

RELEASE (v7.5, external review of v7.4): any ERROR blocks every export -- the
text report, the PDF and the summary image. `release_decision()` is the one
place that says so; the page calls it before each export, and again after the
text and the PDF are rendered (V11 / V12 need the rendered output). A
validation that did not run counts as a failure (fail closed).

ONE DECISION (v7.6, external review of v7.5): v7.5 checked the text inside the
text section, the PDF only when its button was pressed and the image on its
own, so a PDF that failed V12 did not stop the text report. The page now builds
all three once (cdss_ui.release.prepare_release), validates them together, and
every export reads that single decision; the PDF file is made from the very
HTML that was checked, and refused if its options changed after the check.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from cdss.common.specimen import classify_specimen

_BLADDER_ONLY = ("Nitrofurantoin", "Fosfomycin", "Norfloxacin", "Pivmecillinam", "Gepotidacin")
_ESBL_UNRELIABLE = ("Ceftriaxone", "Cefotaxime", "Ceftazidime", "Cefixime", "Cefuroxime",
                    "Cefuroxime sodium", "Cephalexin", "Cefazolin", "Amoxicillin + Clavulanic acid",
                    "Ampicillin/Sulbactam", "Ampicillin", "Amoxicillin")
_TDM = ("Gentamicin", "Amikacin", "Tobramycin", "Vancomycin")


def _names(items: Optional[Iterable[Any]]) -> List[str]:
    return [str(i.get("name", "")) for i in (items or []) if isinstance(i, dict)]


def _v(vid: str, severity: str, message: str) -> Dict[str, str]:
    return {"id": vid, "severity": severity, "message": message}


def validate_case(result: Dict[str, Any], *, specimen: str, sir_map: Dict[str, str],
                  uti_syndrome: Optional[str] = None, report_text: Optional[str] = None,
                  pdf_html: Optional[str] = None,
                  image_lists: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, str]]:
    """Cross-checks on one finished case. [] = coherent."""
    out: List[Dict[str, str]] = []
    sir = {str(k): str(v or "").strip().upper() for k, v in (sir_map or {}).items()}
    ranked = _names(result.get("ranked"))
    allowed = _names(result.get("allowed"))
    warned = _names(result.get("warned"))
    banned = _names(result.get("banned"))
    preg = _names(result.get("preg_warn"))
    urine = classify_specimen(specimen) == "urine"
    uti = str(uti_syndrome or "").lower()

    for n in dict.fromkeys(ranked + allowed):
        if sir.get(n) in ("R", "I", "SDD"):
            out.append(_v("V01", "error", f"{n} is offered but tested {sir[n]}."))
    for n in ranked:
        if n not in sir:
            out.append(_v("V02", "error", f"{n} is ranked but was not tested."))
    if urine and uti == "upper":
        for n in ranked + allowed + warned:
            if n in _BLADDER_ONLY:
                out.append(_v("V03", "error", f"{n} reaches bladder urine only - offered for a "
                                              "systemic / upper-tract UTI."))
    if urine and uti == "cuti":
        for n in ranked:
            if n in _BLADDER_ONLY:
                out.append(_v("V04", "warning", f"{n} ranked for a complicated UTI (IDSA cUTI 2025: "
                                                "generally not appropriate)."))
    prob = str((result.get("mechanism") or {}).get("probability") or "").lower()
    if prob in ("high", "moderate"):
        for n in ranked:
            if n in _ESBL_UNRELIABLE:
                out.append(_v("V05", "error", f"{n} ranked although an ESBL is suspected."))
    gate = result.get("treatment_gate")
    if gate and not gate.get("override") and (ranked or result.get("duration")):
        out.append(_v("V06", "error", "A 'do not treat' verdict, but treatment options or a "
                                      "duration were produced."))
    case = result.get("case")
    if case is not None and getattr(case, "low_muscle_mass", False):
        for it in (result.get("allowed") or []) + (result.get("warned") or []):
            if it.get("name") in _TDM and not it.get("tdm_note_en") and not it.get("renal_note"):
                out.append(_v("V07", "error", f"{it.get('name')}: low muscle mass but no renal / "
                                              "TDM note."))
    seen: Dict[str, str] = {}
    for bucket, names in (("allowed", allowed), ("caution", warned), ("avoid", banned),
                          ("pregnancy", preg)):
        for n in names:
            if n in seen and seen[n] != bucket:
                out.append(_v("V08", "error", f"{n} is in both '{seen[n]}' and '{bucket}'."))
            seen.setdefault(n, bucket)
    if result.get("degraded"):
        out.append(_v("V09", "error", "A safety layer did not run: " + "; ".join(result["degraded"])))
    elif result.get("gate_applied") is False:
        # v7.5: a skipped gate is a failure even if nothing declared it
        out.append(_v("V09", "error", "The terminal safety gate was not applied."))
    if result.get("data_blocked"):
        out.append(_v("V10", "error", "Critical mismatch between the laboratory report and the "
                                      "entered case - reports must not be released."))
    if report_text is not None and not (gate and not gate.get("override")):
        # v7.6 (external review of v7.5): each name is looked for IN ITS SECTION,
        # as an entry line ("Name [Culture: S]") -- a mention in a note elsewhere
        # in the report no longer counts as "recommended".
        rec_entries = _entries(_section(report_text, "RECOMMENDED ANTIBIOTICS",
                                        ("DOSE ADJUSTMENT", "CONTRAINDICATED")))
        caution_entries = _entries(_section(report_text, "DOSE ADJUSTMENT / USE WITH CAUTION",
                                            ("CONTRAINDICATED",)))
        for n in banned:
            if n in rec_entries and n not in warned + allowed:
                out.append(_v("V11", "error", f"The text report recommends {n}, which the "
                                              "analysis avoids."))
        for n in ranked:
            if n not in rec_entries:
                out.append(_v("V11", "error", f"{n} is ranked on screen but absent from the "
                                              "text report's recommended section."))
        for n in rec_entries:
            if n not in allowed:
                out.append(_v("V11", "error", f"The text report recommends {n}, which the "
                                              "analysis does not offer."))
        for n in warned:
            if n not in caution_entries:
                out.append(_v("V11", "error", f"{n} is under caution on screen but absent from "
                                              "the text report's caution section."))
    if pdf_html is not None:
        if "ESBL+" in pdf_html:
            out.append(_v("V12", "error", "The PDF prints 'ESBL+' (a prediction worded as a result)."))
        if ranked and "Ranked for:" not in pdf_html and not (gate and not gate.get("override")):
            out.append(_v("V12", "error", "The PDF ranks options without saying what for."))
        if ranked and ranked[0] not in pdf_html:
            out.append(_v("V12", "error", f"The PDF does not show the first-ranked agent {ranked[0]}."))
        out.extend(_mechanism_labels(result, pdf_html))
    # V14 (v7.7): the laboratory wrote SDD where CLSI M100 Ed36 defines none.
    # It is read as I meanwhile; nothing is released until the result is chosen.
    if result.get("sdd_reported"):
        from cdss.therapy.clsi_categories import sdd_defined
        for n in result.get("sdd_reported") or []:
            if not sdd_defined(n, result.get("organism") or ""):
                out.append(_v("V14", "error", f"The laboratory wrote SDD for {n}, a pair CLSI "
                                              "M100 Ed36 defines no SDD for - choose S, I or R "
                                              "from the MIC."))
    if image_lists is not None:
        def _base(x: str) -> str:
            return str(x).split(" [")[0].split(" (")[0].strip()
        pref = {_base(x) for x in image_lists.get("preferred") or []}
        # v7.6 (external review of v7.5): the Reserve column is offered too
        caut = {_base(x) for k in ("caution", "reserve") for x in image_lists.get(k) or []}
        offered = pref | caut
        avoided = {_base(x) for x in image_lists.get("avoid") or []}
        # I / SDD may sit under caution with its dose note (CLSI); never as a first choice
        for n in sorted(offered):
            if sir.get(n) == "R" or (n in pref and sir.get(n) in ("I", "SDD")):
                out.append(_v("V13", "error", f"The summary image offers {n}, tested {sir[n]}."))
        for n in sorted(offered & avoided):
            out.append(_v("V13", "error", f"The summary image lists {n} as both offered and avoided."))
    return out


def _is_heading(line: str) -> bool:
    """Report headings are upper-case phrases ("PATHOGENICITY ASSESSMENT");
    no agent name is (checked against the drug tables in v7.6)."""
    t = line.strip()
    return bool(t) and t.isupper() and " " in t


def _section(text: str, header: str, next_headers=()) -> str:
    """The body of one text-report section: from its header to the next
    heading of any kind (a section may be the last one before another block)."""
    if header not in text:
        return ""
    lines = text.split(header, 1)[1].splitlines()
    body = []
    for ln in lines[1:]:
        if _is_heading(ln) or any(ln.strip().startswith(h) for h in next_headers):
            break
        body.append(ln)
    return "\n".join(body)


def _entries(section: str) -> List[str]:
    """The agent of every entry in a section: an entry is the line just above a
    "-----" rule ("Nitrofurantoin [Culture: S]" / "Name [Culture: S] <tag>")."""
    lines = section.splitlines()
    out = []
    for i, ln in enumerate(lines[:-1]):
        if ln.strip() and lines[i + 1].startswith("-----") and not _is_heading(ln):
            out.append(ln.strip().split(" [")[0].strip())
    return out


def _mechanism_labels(result: Dict[str, Any], pdf_html: str) -> List[Dict[str, str]]:
    """V12 tied to the mechanism result and its evidence level (v7.6).

    A predicted mechanism must be printed AS predicted, a confirmed one AS
    confirmed -- checked against the analysis, not by searching for one word.
    """
    from cdss.resistance.esbl_status import esbl_status
    out: List[Dict[str, str]] = []
    mech = result.get("mechanism") or {}
    prob = str(mech.get("probability") or "").lower()
    carb_type = result.get("carbapenemase_type")
    state = esbl_status(mech, result.get("aux_tests"))
    if carb_type:
        if f"{carb_type} CONFIRMED" not in pdf_html:
            out.append(_v("V12", "error", f"The laboratory-confirmed {carb_type} is not printed as "
                                          "confirmed."))
    elif state:
        if state["label_en"] not in pdf_html:
            out.append(_v("V12", "error", f"The PDF does not state the ESBL evidence level "
                                          f"('{state['label_en']}')."))
        if state["state"] != "confirmed" and "ESBL CONFIRMED" in pdf_html:
            out.append(_v("V12", "error", "The PDF prints 'ESBL CONFIRMED' without a positive "
                                          "confirmatory test."))
    elif prob in ("ampc", "ampc_plasmid", "carbapenemase", "possible_carbapenemase"):
        for bare in (">AmpC<", ">CARBAPENEMASE<"):
            if bare in pdf_html:
                out.append(_v("V12", "error", f"The PDF prints a predicted mechanism without "
                                              f"'suspected' ({bare.strip('<>')})."))
    if "ESBL CONFIRMED" in pdf_html and not (state and state["state"] == "confirmed"):
        if not any("ESBL CONFIRMED" in v["message"] for v in out):
            out.append(_v("V12", "error", "The PDF prints 'ESBL CONFIRMED' without a positive "
                                          "confirmatory test."))
    return out


def release_decision(violations: Optional[List[Dict[str, str]]]) -> Dict[str, Any]:
    """{blocked, errors} -- None (validation did not run) blocks: fail closed."""
    if violations is None:
        return {"blocked": True, "errors": [_v("V00", "error", "Whole-case validation did not "
                                                               "run - nothing is released.")]}
    errors = [v for v in violations if v.get("severity") == "error"]
    return {"blocked": bool(errors), "errors": errors}


def summarize(violations: List[Dict[str, str]]) -> str:
    """'pass' | 'warn' | 'fail'."""
    if any(v["severity"] == "error" for v in violations):
        return "fail"
    return "warn" if violations else "pass"


def checklist_item(violations: Optional[List[Dict[str, str]]]) -> Dict[str, str]:
    """The final-checklist row for the page (status pass / warn / fail).

    None means the validation did not run -- a failure, not a pass (the same
    rule as release_decision). An empty list means every check passed.
    """
    if violations is None:
        violations = [_v("V00", "error", "Whole-case validation did not run.")]
    return {"status": summarize(violations),
            "title": "Clinical decision validation (whole case)",
            "detail": ("; ".join(f"{v['id']}: {v['message']}" for v in violations)
                       or "كل الفحوصات المتقاطعة سليمة")}


__all__ = ["validate_case", "summarize", "checklist_item", "release_decision"]
