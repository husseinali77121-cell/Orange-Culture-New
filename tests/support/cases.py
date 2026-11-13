# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""Small builders shared by the unit tests."""
from typing import Any, Dict, Optional

from cdss.common.clinical_utils import Patient
from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.pipeline import run_analysis
from cdss.therapy.context import DrugUnderTest, TherapyContext, build_context
from cdss.therapy.outcome import Outcome

BUCKETS = ("allowed", "warned", "preg_warn", "banned")


def context(organism: str = "E. coli", specimen: str = "Urine",
            sir: Optional[Dict[str, str]] = None, *, age: int = 40, sex: str = "Male",
            is_renal: bool = False, cl_cr: Optional[float] = None, is_preg: bool = False,
            is_hepatic: bool = False, child_pugh: str = "C", age_months: Optional[int] = None,
            meds=(), **kw) -> TherapyContext:
    """A TherapyContext for one case, built exactly as the engine builds it."""
    sir = dict(sir or {})
    cx, _drugs = build_context(list(sir), organism, specimen, age, sex, is_renal, cl_cr,
                               is_preg, is_hepatic, list(meds), sir, child_pugh, age_months, **kw)
    return cx


def drug(name: str, result: Optional[str] = "S") -> DrugUnderTest:
    info = ABX_GUIDELINES[name]
    return DrugUnderTest(name=name, info=info, low=name.lower(),
                         cls=info.get("class", "").lower(), result=result)


def apply(rule, cx: TherapyContext, dg: DrugUnderTest, out: Optional[Outcome] = None) -> Outcome:
    """Run ONE rule on one drug and return what it decided."""
    out = out if out is not None else Outcome({})
    rule(cx, dg, out)
    return out


def analyse(organism: str, specimen: str, sir: Dict[str, Any], **patient_and_options) -> Dict[str, Any]:
    opts = {k: patient_and_options.pop(k) for k in ("carbapenemase_type", "uti_syndrome")
            if k in patient_and_options}
    patient = Patient(**{"age_years": 40, "sex": "Male", **patient_and_options})
    return run_analysis(patient, organism, specimen, dict(sir), **opts)


def bucket_of(result: Dict[str, Any], name: str) -> Optional[str]:
    for b in BUCKETS:
        if any(it.get("name") == name for it in result[b]):
            return b
    return None


def item_of(result: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for b in BUCKETS:
        for it in result[b]:
            if it.get("name") == name:
                return it
    return None
