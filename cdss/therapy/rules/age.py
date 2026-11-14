# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Age rules: children, neonates, the preterm window.

Every rule has the same shape:  rule(cx, dg, out) -> None
    cx   TherapyContext  the case: organism, specimen, host, mechanism (read-only)
    dg   DrugUnderTest   one agent of the panel and its S/I/R result (read-only)
    out  Outcome         where the rule records a ban / caution / note
"""
from cdss.therapy.intrinsic import build_banned_item
from cdss.therapy.tables import CHILD_BAN_REASONS
from cdss.therapy.tables import NEONATAL_RESTRICTIONS


def rule_child(cx, dg, out):
    """Paediatric contraindications (child_safe, fluoroquinolones, tetracyclines under 8)."""
    # ══════════════════════════════════════════════════════════════════
    # ABSOLUTE CONTRAINDICATIONS -- checked BEFORE pregnancy caution
    # (child age + renal threshold are hard bans; pregnancy is discretionary)
    # ══════════════════════════════════════════════════════════════════
    if cx.age < 18 and not dg.info.get("child_safe", True):
        if "fluoroquinolone" in dg.cls:
            out.ban(build_banned_item(
                dg.name, "child", "غير مناسب < 18 سنة.", CHILD_BAN_REASONS["fluoroquinolone"]
            ))
            return
        if "tetracycline" in dg.cls:
            # The age<8 guard used to sit on this branch, so a tetracycline
            # given to an 8-17 year old fell through to the generic message
            # below and the clinician was told "not preferred for children"
            # with no reason -- losing the dental-staining/bone-deposition
            # rationale that is the whole point of the restriction, and
            # losing the fact that AAP Red Book 2024 and CLSI now accept
            # short courses of doxycycline (<21 days) at any age.
            # FIX 2026-11-10: the tooth-staining restriction is an UNDER-8
            # rule. An 8-17 year old was banned from every tetracycline
            # ("needs a physician decision"), which no guideline says --
            # from 8 years they are ordinary agents. Doxycycline itself is
            # child_safe now (AAP Red Book 2024) and never reaches here.
            if cx.age < 8:
                out.ban(build_banned_item(
                    dg.name, "child", "غير مناسب < 8 سنوات.",
                    CHILD_BAN_REASONS["tetracycline"]
                    + "\n\nملاحظة (AAP Red Book 2024): Doxycycline لدورة قصيرة (≤ 21 يوم) "
                      "مقبول في أي عمر — هو البديل من نفس الصنف."))
                return
            # age 8-17: no paediatric ban -- fall through to the remaining checks
        else:
            out.ban(build_banned_item(
                dg.name, "child", "غير مفضل للأطفال.",
                f"{dg.name}: يحتاج تقييم متخصص أو لا يُنصح به روتينياً في عمر {cx.age} سنة. "
                f"{dg.info.get('child_note', '')}".strip(),
            ))
            return


def rule_neonate(cx, dg, out):
    """Neonatal / young-infant restrictions, by age in months."""
    # ── NEONATAL / YOUNG-INFANT gate ──────────────────────────────────────
    # Runs only when the patient is inside the first year, and only when we
    # actually know the age in months. If the clinician entered age=0 years
    # WITHOUT the months field, we cannot tell a 3-week-old from an
    # 11-month-old -- so we warn rather than silently allowing, which is the
    # behaviour that shipped.
    if cx.age < 1 and dg.name in NEONATAL_RESTRICTIONS:
        _neo = NEONATAL_RESTRICTIONS[dg.name]
        _alt = f" البديل: {_neo['alt']}." if _neo.get("alt") else ""
        _alt_en = (f" Alternative: {_neo.get('alt_en') or _neo['alt']}."
                   if _neo.get("alt") else "")
        # v6.7: every caution carries its English form too -- the English PDF
        # printed "A clinical note ... in the Arabic report" for each one.
        _reason_en = _neo.get("reason_en", "")
        # A months value outside 0-11 is not a patient, it is a data error.
        # Treating 99 as "older than the threshold" silently switched the
        # whole neonatal gate off; treat it as UNKNOWN instead, which warns.
        _m = cx.age_months
        if _m is not None and not (0 <= _m <= 11):
            _m = None
        if _m is None:
            out.caution({
                # FIX 2026-08-01: `**info` and `warning_reason` were both
                # missing here, so the render layer had no reason to switch
                # on and no ABX metadata to fall back to -- the item printed
                # as a bare drug name with an empty explanation.
                "name": dg.name, **dg.info,
                "category": "neonate", "warning_reason": "neonate",
                "reason_short": f"عمر غير محدد بالشهور — تحقق من حد الـ {_neo['months']} شهور.",
                "reason_detail": (f"{_neo['reason']}{_alt}\n\n"
                                  "أدخل العمر بالشهور (خانة «أقل من سنة») "
                                  "ليطبّق النظام الحد العمري بدقة."),
                "reason_short_en": (f"Age in months not entered — check the "
                                    f"{_neo['months']}-month limit."),
                "reason_detail_en": (f"{_reason_en}{_alt_en}\n\nEnter the age in months "
                                     "(the 'under 1 year' field) so the age limit is applied "
                                     "exactly."),
            })
            return
        if _m < _neo["months"]:
            if _neo["action"] == "ban":
                out.ban(build_banned_item(
                    dg.name, "neonate",
                    f"يُمنع تحت {_neo['months']} شهر (العمر {_m} شهر).",
                    f"{_neo['reason']}{_alt}",
                ))
            else:
                out.caution({
                    "name": dg.name, **dg.info,
                    "category": "neonate", "warning_reason": "neonate",
                    "reason_short": f"حذر شديد تحت {_neo['months']} شهر.",
                    "reason_detail": f"{_neo['reason']}{_alt}",
                    "reason_short_en": f"Extreme caution under {_neo['months']} months.",
                    "reason_detail_en": f"{_reason_en}{_alt_en}",
                })
            return


def rule_preterm_window(cx, dg, out):
    """Ceftriaxone preterm window: ask about gestational age rather than assume."""
    # Preterm window: the chronological ban has lifted, but for an
    # ex-premature infant the contraindication runs to 41 weeks POSTMENSTRUAL
    # age — roughly three chronological months for a 28-weeker. The engine
    # holds no gestational-age field, so it asks rather than assumes.
    if cx.age < 1 and cx.age_months is not None and dg.name in NEONATAL_RESTRICTIONS:
        _neo2 = NEONATAL_RESTRICTIONS[dg.name]
        _pcm = _neo2.get("preterm_caution_months")
        if _pcm and _neo2.get("months", 0) <= cx.age_months < _pcm:
            out.caution({
                "name": dg.name, **dg.info,
                "category": "neonate", "warning_reason": "neonate",
                "reason_short": f"خديج؟ تحقّق قبل الوصف (العمر {cx.age_months} شهر).",
                "reason_detail": _neo2.get("preterm_reason", ""),
                "reason_short_en": (f"Born preterm? Check before prescribing "
                                    f"(age {cx.age_months} months)."),
                "reason_detail_en": _neo2.get("preterm_reason_en", ""),
            })
            return
