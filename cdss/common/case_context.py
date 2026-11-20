# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""One record of the case facts that several modules read (v7.0).

DEFECT THIS CLOSES (external review, 2026-11-19)
The pathogenicity panel recorded "Indwelling catheter (Foley)" and the host
factors "Urinary catheter" + "Quadriplegia", while
  * the report image printed "Urine / Mid-Stream" (a hard-coded string),
  * the syndrome card was built with is_cath=False (hard-coded) and called a
    febrile catheter-associated infection "Uncomplicated UTI",
  * the duration panel did not know about the catheter, and
  * the renal note said "Normal" for a quadriplegic patient, whose low muscle
    mass makes a normal creatinine overestimate the GFR.
Each module had its own idea of the case. They now read this one record,
built once from the pathogenicity inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from cdss.common.specimen import classify_specimen

_NOT_STATED = ("", "مش محدد", "not stated", "unknown", "none")

# Collection method -> the short English label the reports print.
_COLLECTION_LABEL = (
    ("midstream", "Mid-Stream (clean-catch)"),
    ("indwelling", "Indwelling catheter (Foley)"),
    ("foley", "Indwelling catheter (Foley)"),
    ("intermittent", "Intermittent catheterisation"),
    ("suprapubic catheter", "Suprapubic catheter"),
    ("aspirate", "Suprapubic aspirate"),
    ("spa", "Suprapubic aspirate"),
    ("condom", "Condom catheter"),
    ("bag", "Bag specimen"),
    ("nephrostomy", "Nephrostomy / ileal conduit"),
    ("conduit", "Nephrostomy / ileal conduit"),
)
# Methods that mean the patient HAS a urinary catheter (CA-UTI rules apply).
_CATHETER_METHODS = ("indwelling", "foley", "suprapubic catheter", "intermittent")
# Host factors that make creatinine a poor GFR marker (low muscle mass).
_LOW_MUSCLE = ("quadripleg", "tetrapleg", "parapleg", "spinal cord", "cervical cord",
               "amputat", "cachex", "muscle wasting", "sarcopen")


@dataclass(frozen=True)
class CaseContext:
    specimen: str = ""
    host_factors: List[str] = field(default_factory=list)
    collection_method: str = ""          # as entered ("" when not stated)

    @property
    def is_urine(self) -> bool:
        return classify_specimen(self.specimen) == "urine"

    @property
    def collection_label(self) -> str:
        """English label for the reports, or "" when the method was not stated."""
        c = (self.collection_method or "").strip().lower()
        if not self.is_urine or c in _NOT_STATED:
            return ""
        for key, label in _COLLECTION_LABEL:
            if key in c:
                return label
        return self.collection_method.strip()

    @property
    def is_cath(self) -> bool:
        """A urinary catheter is in place (collection method or host factor)."""
        c = (self.collection_method or "").lower()
        return (any(k in c for k in _CATHETER_METHODS)
                or any("urinary catheter" in str(h).lower() for h in self.host_factors))

    @property
    def cuti_device(self) -> bool:
        """A device or structural factor that makes a UTI complicated (IDSA cUTI
        2025): an indwelling, suprapubic or intermittent catheter, a nephrostomy /
        conduit (v7.1), v7.2: an obstruction / stone / stent -- the factor the
        severity engine already called complicated."""
        c = (self.collection_method or "").lower()
        _obstr = any(k in str(h).lower() for h in self.host_factors
                     for k in ("obstruction", "stone", "stent"))
        return self.is_urine and (self.is_cath or "nephrostomy" in c or "conduit" in c or _obstr)

    @property
    def ventilated(self) -> bool:
        return any(k in str(h).lower() for h in self.host_factors
                   for k in ("tracheostomy", "ventilat"))

    @property
    def central_line(self) -> bool:
        return any(k in str(h).lower() for h in self.host_factors
                   for k in ("central line", "picc"))

    def syndrome_device(self) -> bool:
        """The device the syndrome card asks about, for THIS specimen (v7.1):
        urine -> urinary catheter (CA-UTI), sputum -> ventilator / tracheostomy
        (HAP/VAP), blood -> central line (CRBSI). The card's is_cath was read
        for urine only, so HAP/VAP and CRBSI could never be named."""
        cat = classify_specimen(self.specimen)
        if cat == "urine":
            return self.is_cath
        if cat == "sputum":
            return self.ventilated
        if cat == "blood":
            return self.central_line
        return False

    @property
    def spinal_cord_injury(self) -> bool:
        return any(k in str(h).lower() for h in self.host_factors
                   for k in ("quadripleg", "tetrapleg", "parapleg", "spinal cord", "cervical cord"))

    @property
    def low_muscle_mass(self) -> bool:
        """Serum creatinine overestimates GFR (SCI, amputation, cachexia)."""
        return any(k in str(h).lower() for h in self.host_factors for k in _LOW_MUSCLE)


def build_case_context(specimen: str, host_factors: Optional[List[str]] = None,
                       collection_method: Optional[str] = None) -> CaseContext:
    hf = [str(h) for h in (host_factors or []) if str(h or "").strip()]
    cm = str(collection_method or "").strip()
    if cm.lower() in _NOT_STATED:
        cm = ""
    return CaseContext(specimen=specimen or "", host_factors=hf, collection_method=cm)


LOW_MUSCLE_CRCL_NOTE_AR = (
    "⚠️ كتلة عضلية منخفضة (إصابة النخاع الشوكي / شلل / بتر): الـ eGFR المحسوب من الكرياتينين قد "
    "يبالغ في تقدير وظائف الكلى — «الكلى طبيعية» قد يكون غير دقيق. فكّر في Cystatin C أو GFR مقاس "
    "(بول 24 ساعة). للأمينوجليكوزيد والفانكومايسين: قِس المستوى (TDM) لضبط الجرعة الفردية — "
    "والـ TDM لا يُغني عن تقييم وظائف الكلى لاختيار الجرعة وتعديلها.")
LOW_MUSCLE_CRCL_NOTE_EN = (
    "Low muscle mass (spinal cord injury / paralysis / amputation): creatinine-based eGFR may "
    "overestimate renal function, so 'renal function normal' may be wrong. Consider cystatin C "
    "or a measured GFR (24-h urine). Use therapeutic drug monitoring to individualise "
    "aminoglycoside / vancomycin dosing; renal function assessment remains necessary for dose "
    "selection and adjustment.")

# v7.4: the one-line form printed beside the agent in the ranked list (PDF / image).
LOW_MUSCLE_TDM_SHORT_EN = ("Low muscle mass: eGFR may overestimate GFR - cystatin C / measured GFR; "
                           "TDM to individualise dosing (renal assessment still required).")
LOW_MUSCLE_TDM_SHORT_AR = ("كتلة عضلية منخفضة: الـ eGFR قد يبالغ — Cystatin C أو GFR مقاس؛ TDM لضبط "
                           "الجرعة (مع تقييم وظائف الكلى).")

# Agents whose dosing depends on an accurate GFR and that need levels.
TDM_AGENTS = ("Gentamicin", "Amikacin", "Tobramycin", "Vancomycin", "Teicoplanin",
              "Colistin", "Polymyxin B")

__all__ = ["CaseContext", "build_case_context", "LOW_MUSCLE_CRCL_NOTE_AR",
           "LOW_MUSCLE_CRCL_NOTE_EN", "LOW_MUSCLE_TDM_SHORT_EN", "LOW_MUSCLE_TDM_SHORT_AR",
           "TDM_AGENTS"]
