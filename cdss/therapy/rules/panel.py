# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Rules about the panel itself: unreadable / resistant results and co-medication alerts.

Every rule has the same shape:  rule(cx, dg, out) -> None
    cx   TherapyContext  the case: organism, specimen, host, mechanism (read-only)
    dg   DrugUnderTest   one agent of the panel and its S/I/R result (read-only)
    out  Outcome         where the rule records a ban / caution / note
"""
from cdss.formulary.co_medications import _canon_med
from cdss.formulary.interaction_effects import HEPATIC_CAUTION_AR
from cdss.formulary.interaction_effects import interaction_alert
from cdss.therapy.intrinsic import build_banned_item


def rule_unreadable(cx, dg, out):
    """A panel value that is not S / I / R is never assumed susceptible."""
    if dg.name in cx.unreadable:
        out.ban(build_banned_item(
            dg.name, "unreadable",
            "نتيجة الحساسية غير مقروءة.",
            f"{dg.name}: القيمة المسجّلة في اللوحة ليست S أو I أو R. لا يمكن "
            "تفسيرها، ولا يجوز افتراض أنها حساسة. أعد إدخال النتيجة يدوياً.",
        ))
        return


def rule_resistant(cx, dg, out):
    """R on the culture: the agent is out."""
    if dg.result == "R":
        out.ban(build_banned_item(
            dg.name, "resistant", "مقاوم (R) في نتيجة المزرعة.",
            f"المزرعة أثبتت أن {dg.name} لا يثبط نمو الجرثومة. MIC أعلى من الحد العلاجي -> خطر فشل علاجي.",
        ))
        return


def rule_interaction_alerts(cx, dg, out):
    """Co-medication interactions and the hepatic-caution alert (side notes, never a verdict).

    v6.7: the alert names what the interaction DOES and what to do
    (cdss.formulary.interaction_effects) -- the bare pair told the prescriber
    that something was wrong, not whether to expect a high INR or a seizure.
    """
    _declared = {_canon_med(x) for x in (dg.info.get("interacts_with") or [])}
    for med in cx.current_meds:
        if _canon_med(med) in _declared:
            cx.alerts.append(interaction_alert(dg.name, med, "ar"))
    if cx.is_hepatic and dg.info.get("hepatic_caution"):
        cx.alerts.append(HEPATIC_CAUTION_AR.format(drug=dg.name))
