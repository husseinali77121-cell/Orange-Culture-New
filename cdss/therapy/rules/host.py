# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Host-state rules that run LAST: hepatic impairment, renal dose adjustment, Intermediate.

They are cautions (apart from a hepatic "Avoid", which bans), so they sit below
every absolute contraindication.  A drug that already carries a caution -- or a
pregnancy caution -- does not lose these facts: they are written onto that item
instead of being skipped (the old loop needed a separate post-loop patch to do
this for five named reasons; here it holds for every reason).

Every rule has the same shape:  rule(cx, dg, out) -> None
"""
from cdss.therapy.clsi_categories import intermediate_fields
from cdss.therapy.intrinsic import build_banned_item
from cdss.therapy.tables import HEPATIC_DOSING

# Levels that need no hepatic action. Anything else is a caution; "avoid" bans.
_HEPATIC_NO_ACTION = ("normal", "renal-based", "auc/mic monitoring", "normal (renal)")


def child_pugh_grade(child_pugh) -> str:
    """A | B | C. Unknown or malformed grades fail CLOSED to the worst grade."""
    grade = (child_pugh or "C").strip().upper()[:1] or "C"
    return grade if grade in ("A", "B", "C") else "C"


def rule_hepatic(cx, dg, out):
    """Hepatic impairment (Child-Pugh): enforce HEPATIC_DOSING -- BNF 2025 / LiverTox / labels."""
    if not cx.is_hepatic:
        return
    row = HEPATIC_DOSING.get(dg.name)
    if not row:
        return
    grade = child_pugh_grade(cx.child_pugh)
    level, rec = row.get(grade, ("Normal", "No adjustment"))
    if "avoid" in str(level).lower():
        out.ban(build_banned_item(
            dg.name, "hepatic",
            f"ممنوع في القصور الكبدي (Child-Pugh {grade}).",
            f"{dg.name}: {rec}. {row.get('note', '')} "
            f"المرجع: BNF 2025 (hepatic impairment) / LiverTox NIH.",
        ))
        return
    if str(level).lower() in _HEPATIC_NO_ACTION:
        return
    line = f"🫀 Hepatic (Child-Pugh {grade}): {level} — {rec}"
    if out.preg_item is not None:
        # Stays in the pregnancy bucket; the hepatic fact travels with it.
        out.preg_item.update(hepatic_level=level, hepatic_rec=rec)
        out.preg_extra.append(line)
    elif out.primary is not None:
        out.primary.update(hepatic_level=level, hepatic_rec=rec)
        out.extra.append(line)
    else:
        out.caution({"name": dg.name, **dg.info,
                     "warning_reason": "hepatic_adjustment",
                     "hepatic_level": level, "hepatic_rec": rec})


def rule_renal_adjustment(cx, dg, out):
    """Renal dose adjustment at or below the agent's renal_limit (a caution, never a ban)."""
    renal_limit = dg.info.get("renal_limit", 0) or 0
    if not (cx.is_renal and renal_limit > 0 and cx.crcl is not None and cx.crcl <= renal_limit):
        return
    renal_note = str(dg.info.get("renal_note_en") or dg.info.get("renal_note") or "").strip()
    line = (f"🫘 Renal: CrCl {cx.crcl:.0f} ml/min"
            + ("" if cx.crcl_measured else " (assumed — no creatinine entered)")
            + f" ≤ {renal_limit} — dose adjustment required"
            + (f": {renal_note}" if renal_note else "."))
    if out.preg_item is not None:
        out.preg_item.update(renal_adjustment=True, crcl_used=cx.crcl,
                             crcl_measured=cx.crcl_measured)
        out.preg_extra.append(line)
    elif out.primary is not None:
        out.primary.update(renal_adjustment=True, crcl_used=cx.crcl,
                           crcl_measured=cx.crcl_measured)
        out.extra.append(line)
    else:
        # crcl_used / crcl_measured are carried on the item so the PDF, the text
        # report and the screen all print the same renal detail.
        out.caution({"name": dg.name, **dg.info,
                     "warning_reason": "renal_adjustment",
                     "crcl_used": cx.crcl,
                     "crcl_measured": cx.crcl_measured})


def rule_intermediate(cx, dg, out):
    """Culture result I (CLSI M100 Intermediate) or SDD is never 'allowed' as-is.

    What the I is worth depends on the class and the site (CLSI: efficacy where
    the drug is concentrated, e.g. beta-lactams and quinolones in urine, or at a
    higher dose, e.g. beta-lactams); an SDD names its own regimen. The note says
    which (cdss.therapy.clsi_categories). When the drug already carries another
    caution the I is not lost: every warned item gets `culture_intermediate`
    (postprocess.flag_intermediate).
    """
    if dg.result != "I":
        return
    fields = intermediate_fields(dg.name, dg.info, cx.spec_cat, cx.uti_upper, cx.sdd,
                                 cx.organism)
    if out.preg_item is not None:
        out.preg_item.update(fields)
        out.preg_extra.append("🟡 Culture result " + ("SDD" if fields["culture_sdd"] else "I")
                              + " — " + fields["intermediate_note_en"])
    elif out.primary is None:
        out.caution({"name": dg.name, **dg.info, "warning_reason": "intermediate_culture",
                     **fields})
