# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Which explanation belongs to which warning."""
from typing import Any
from typing import Dict




def warned_note_for(item: Dict[str, Any], lang: str = "ar") -> str:
    """The explanation that belongs to THIS warning, in the caller's language.

    DEFECT THIS FIXES (2026-08-01, fourth pass)
    The warned-item renderer was two branches:

        if warning_reason in ("esbl_bli_uti_only", "possible_carbapenemase"):
            show item["esbl_note"]
        else:
            show item["renal_note"]          # <- everything else landed here

    Every warned item carries `**info` spread from ABX_GUIDELINES, and every
    ABX_GUIDELINES row has a `renal_note`. So the else branch never printed an
    empty string -- it printed a CONFIDENT, WELL-FORMATTED, WRONG note:

      * Child-Pugh C warning on Ciprofloxacin rendered
        "CrCl <30: خفض الجرعة 50%…" -- renal dosing for a patient whose
        kidneys are fine and whose liver is failing.
      * A safety-gate demotion of Oxacillin in MENINGITIS rendered
        "🟢 لا تعديل كلوي مطلوب" -- actively reassuring, at the moment the gate
        had just refused the drug for not crossing the blood-brain barrier.
      * Neonatal warnings rendered adult renal dosing.

    Wrong text is worse than no text: a blank line invites the reader to look
    further, a fluent irrelevant sentence does not.

    The real explanation was present the whole time under a per-reason key --
    gate_note, hepatic_level/hepatic_rec, reason_short/reason_detail -- and
    nothing read it. This resolver is the single place that knows which key
    belongs to which reason.

    Returns "" only when the item genuinely carries no explanation, which the
    render layer surfaces explicitly rather than printing a blank bullet.
    """
    # 2026-11-10: an item can carry a second, independent fact (a novel-agent
    # note, an organism caution, a CLSI breakpoint restriction) under
    # `clinical_note` while its primary warning_reason is something else --
    # renal dosing, say. It is appended so neither fact hides the other.
    def _primary() -> str:
        if not isinstance(item, dict):
            return ""
        ar = (lang or "ar").lower().startswith("ar")

        def pick(*keys) -> str:
            for k in keys:
                v = item.get(k)
                if v and str(v).strip():
                    return str(v).strip()
            return ""

        reason = item.get("warning_reason") or ""
        category = item.get("category") or ""

        if reason in ("esbl_bli_uti_only", "possible_carbapenemase"):
            return pick("esbl_note", "esbl_note_en") if ar else pick("esbl_note_en", "esbl_note")

        if reason == "hepatic_adjustment":
            lvl, rec = item.get("hepatic_level"), item.get("hepatic_rec")
            if lvl or rec:
                head = f"🫀 Child-Pugh: {lvl}" if lvl else "🫀 قصور كبدي"
                body = f" — {rec}" if rec else ""
                extra = pick("hepatic_note", "hepatic_note_en")
                return f"{head}{body}" + (f"  \n{extra}" if extra else "")
            return pick("hepatic_note", "hepatic_note_en")

        if reason == "renal_adjustment":
            return pick("renal_note", "renal_note_en") if ar else pick("renal_note_en", "renal_note")

        if reason == "possible_mrsa":
            return pick("possible_mrsa_note")

        if reason == "safety_gate":
            return pick("gate_note", "gate_note_en") if ar else pick("gate_note_en", "gate_note")

        if reason == "neonate" or category == "neonate":
            short, detail = pick("reason_short"), pick("reason_detail")
            return f"{short}  \n{detail}" if short and detail else (short or detail)

        if reason == "intermediate_culture":
            if not ar:
                return ("Result is Intermediate (I) - EUCAST: susceptible, increased exposure. "
                        "Use only at the higher dose / extended infusion and after excluding a "
                        "susceptible (S) alternative.")
            return ("النتيجة Intermediate (I) — حسب EUCAST تعني حساسية عند تعرّض أعلى: "
                    "لا تُستخدم إلا بجرعة أعلى/تسريب ممتد وبعد استبعاد بديل حسّاس (S).")

        if reason == "interaction" or category == "interaction":
            return pick("interaction_note", "reason_detail", "reason_short")

        if reason == "pregnancy" or category == "pregnancy":
            return pick("preg_note", "preg_note_en", "reason_detail", "reason_short")

        # Warnings added by the 2026-11-10 review fixes carry their explanation
        # under ONE key, `clinical_note` (literal set: this function is lifted
        # by name into bare test namespaces, so it must not depend on a global).
        if reason in ("novel_agent", "organism_caution", "allergy", "uti_upper",
                      "aminoglycoside_pseudomonas", "colistin", "penicillinase_unconfirmed",
                      "no_breakpoint", "ampc_sdd", "ampc_cefepime"):
            if not ar:
                return (pick("clinical_note_en")
                        or "Clinical caution applies to this agent for this organism / site - review before use.")
            return pick("clinical_note", "reason_detail", "reason_short")

        # Unknown reason: try every explanation slot that exists before giving up,
        # and NEVER fall back to renal_note -- that silent substitution is the whole
        # defect this function replaces.
        return pick("reason_short", "reason_detail", "gate_note", "esbl_note",
                    "hepatic_rec", "note")

    base = _primary()
    _en_mode = not (lang or "ar").lower().startswith("ar")
    extra = str(item.get("clinical_note_en" if _en_mode else "clinical_note") or "").strip() \
        if isinstance(item, dict) else ""
    if extra and extra not in base:
        return f"{base}  \n{extra}" if base else extra
    return base
