# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Pregnancy rule.

Every rule has the same shape:  rule(cx, dg, out) -> None
    cx   TherapyContext  the case: organism, specimen, host, mechanism (read-only)
    dg   DrugUnderTest   one agent of the panel and its S/I/R result (read-only)
    out  Outcome         where the rule records a ban / caution / note
"""
from cdss.formulary.pregnancy_en import preg_note_en
from cdss.therapy.intrinsic import build_banned_item
from cdss.therapy.tables import preg_status_of


def rule_pregnancy(cx, dg, out):
    """Pregnancy: absolute contraindications ban; cautions are recorded and the drug keeps walking."""
    # ══════════════════════════════════════════════════════════════════
    # PREGNANCY SAFETY BLOCK
    # Updated per: ACOG 2023, BNF 2025, EMA 2025, ENTIS 2024,
    #              IDSA AMR Guidance 2026, WHO AWaRe 2025, BMJ Teratology 2023
    #
    # ORDERING IS LOAD-BEARING -- DO NOT MOVE THE RENAL BLOCK BACK ABOVE THIS.
    # The renal-adjustment branch below ends in `continue`. While it sat
    # BEFORE this block, any drug whose renal_limit happened to exceed the
    # patient's CrCl skipped pregnancy screening entirely: a pregnant woman
    # with CrCl 55 was shown Gentamicin, Amikacin and Tobramycin (fetal
    # ototoxicity, FDA category D) as "Use with caution -- needs renal
    # adjustment" instead of BANNED, and at CrCl <=30 Clarithromycin,
    # TMP-SMX and Gatifloxacin leaked the same way. The leak was invisible
    # in testing because it only fires when BOTH is_renal is ticked AND
    # cl_cr <= that particular drug's renal_limit. A sweep over
    # 7 specimens x 20 organisms x 7 CrCl values found 560 leaking cells.
    # Absolute teratogenic contraindications must be resolved before any
    # branch that can exit the loop early.
    # ══════════════════════════════════════════════════════════════════
    #
    # FIX 2026-11-11 (round 4): every pregnancy CAUTION used to end in
    # `continue`, straight into preg_warn_items. Nothing after this block
    # ran for those drugs -- not the hepatic contraindication, not the renal
    # adjustment, not the Intermediate flag -- and run_analysis() never
    # passed the pregnancy bucket through the terminal safety gate either.
    # So a pregnant woman in Child-Pugh C was shown TMP-SMX and
    # Nitrofurantoin (hepatic AVOID) as "use with caution", and a pregnant
    # woman with meningitis was shown Gentamicin/Amikacin (no CSF
    # penetration) as options: 322 of 6,000 random cases. A pregnancy
    # caution is now RECORDED here and the drug keeps walking through the
    # remaining hard checks; it is bucketed at the end of the loop.
    if cx.is_preg:

        # ── 1. Tetracyclines: ALWAYS BANNED (class-based override) ────────
        if "tetracycline" in dg.cls:
            out.ban(build_banned_item(
                dg.name, "pregnancy",
                "⛔ ممنوع في الحمل -- Tetracyclines.",
                "Tetracyclines (Doxycycline / Tetracycline / Minocycline / Tigecycline):\n"
                "تترسّب في عظام وأسنان الجنين -> تصبغ دائم للأسنان وتثبيط نمو العظام.\n"
                "محظورة في كل مراحل الحمل (خاصة بعد الأسبوع 15).\n"
                "ACOG 2023 / BNF 2025: contraindication مطلقة.\n"
                "البديل: Azithromycin (atypicals) | Amoxicillin-Clavulanate | Cephalosporin.",
            ))
            return

        # ── 2. Aminoglycosides: USE WITH CAUTION (2026-11-10) ─────────────
        # FIX: was an absolute ban. Gentamicin is standard obstetric therapy
        # (ampicillin + gentamicin for chorioamnionitis / intra-amniotic
        # infection, ACOG; severe pyelonephritis and sepsis in pregnancy).
        # Documented fetal eighth-nerve toxicity is with streptomycin and
        # kanamycin; gentamicin/tobramycin/amikacin carry a theoretical risk
        # managed by once-daily dosing, levels and short courses.
        if "aminoglycoside" in dg.cls:
            out.preg_item = {
                "name": dg.name, **dg.info,
                "preg_note": (
                    f"⚠️ Use with Caution — {dg.name} في الحمل:\n"
                    "يعبر المشيمة. خطر السمية السمعية الجنينية موثّق أساساً مع Streptomycin و "
                    "Kanamycin؛ مع Gentamicin نظري ونادر.\n"
                    "مقبول عند الحاجة (التهاب المشيمة: Ampicillin + Gentamicin؛ التهاب حويضة "
                    "شديد أو إنتان) بجرعة يومية واحدة ومراقبة المستوى ولأقصر مدة.\n"
                    ">>> القرار النهائي للطبيب المعالج حصراً. <<<"),
            }

        # ── 3. TMP-SMX: USE WITH CAUTION, trimester-dependent (2026-11-10) ─
        # FIX: was an absolute ban. ACOG Committee Opinion 717 (reaffirmed):
        # sulfonamides remain appropriate in the 1st trimester when no
        # suitable alternative exists; avoid near term (kernicterus). It is
        # also the alternative for Listeria in penicillin allergy.
        elif ("sulfonamide" in dg.cls or "trimethoprim" in dg.low
                or "sulfamethox" in dg.low):
            out.preg_item = {
                "name": dg.name, **dg.info,
                "preg_note": (
                    "⚠️ TMP-SMX — Use with Caution في الحمل:\n"
                    "الثلث الأول: مضاد للفولات — يُستخدم فقط عند غياب بديل مناسب (ACOG CO 717) "
                    "مع حمض الفوليك.\n"
                    "قرب الولادة (≥ 32-36 أسبوع): تجنّب — خطر kernicterus.\n"
                    "الثلث الثاني: مقبول.\n"
                    ">>> القرار النهائي للطبيب المعالج حسب الـ trimester. <<<"),
            }

        # ── 4. Clarithromycin: BANNED ─────────────────────────────────────
        elif "clarithromycin" in dg.low:
            preg_note = dg.info.get("preg_note") or (
                "⛔ ممنوع في الحمل -- Clarithromycin.\n"
                "ارتبط بزيادة الإجهاض (Andersen, PLoS One 2013) وإشارة لتشوهات في الثلث "
                "الأول مع الماكروليدات (Fan, BMJ 2020).\n"
                "BNF 2025: تجنّب في الحمل.\n"
                "البديل الآمن: Azithromycin."
            )
            out.ban(build_banned_item(
                dg.name, "pregnancy",
                preg_note.splitlines()[0],
                preg_note,
            ))
            return

        # ── 5. Any remaining preg_status="Banned": BANNED ─────────────────
        elif preg_status_of(dg.info) == "Banned":
            preg_note = dg.info.get("preg_note") or "⛔ ممنوع في الحمل."
            out.ban(build_banned_item(
                dg.name, "pregnancy",
                preg_note.splitlines()[0],
                preg_note,
            ))
            return

        # ── 6. Fluoroquinolones: USE WITH CAUTION ────────────────────────
        elif "fluoroquinolone" in dg.cls:
            out.preg_item = {
                "name": dg.name, **dg.info,
                "preg_note": dg.info.get("preg_note") or (
                    "⚠️ Use with Caution -- Fluoroquinolone في الحمل:\n"
                    "الأدلة الحديثة (ENTIS 2024): خطر التشوهات أقل مما كان يُعتقد.\n"
                    "لا يُستخدم كخط أول -- فقط عند غياب البديل الأكثر أمانًا.\n"
                    ">>> القرار النهائي للطبيب المعالج حصراً. <<<"
                ),
            }

        # ── 7. Nitrofurantoin: CAUTION (trimester-dependent) ─────────────
        elif "nitrofurantoin" in dg.low:
            out.preg_item = {
                "name": dg.name, **dg.info,
                "preg_note": dg.info.get("preg_note") or (
                    "⚠️ Nitrofurantoin -- Use with Caution في الحمل:\n"
                    "الثلث الأول: فقط عند غياب بديل مناسب (ACOG CO 717).\n"
                    "✅ الثلث الثاني وبداية الثالث: مقبول لالتهاب المثانة.\n"
                    "⛔ تجنّب في الـ 3rd trimester وعند الـ term (≥36 أسبوع):\n"
                    "   خطر hemolytic anemia جنينية (G6PD) ونيونيتل hemolysis.\n"
                    "البديل في 3rd trim: Fosfomycin جرعة واحدة أو Cephalexin.\n"
                    ">>> القرار النهائي للطبيب المعالج حسب الـ trimester. <<<"
                ),
            }

        # ── 8. Metronidazole / Nitroimidazoles: CAUTION ───────────────────
        elif "nitroimidazole" in dg.cls or "metronidazole" in dg.low:
            out.preg_item = {
                "name": dg.name, **dg.info,
                "preg_note": dg.info.get("preg_note") or (
                    "⚠️ Metronidazole -- Use with Caution:\n"
                    "ACOG 2021: مقبول في كل trimesters عند الضرورة.\n"
                    "يُفضل تجنبه في الـ 1st trimester إن وُجد بديل آمن.\n"
                    ">>> القرار النهائي للطبيب المعالج حصراً. <<<"
                ),
            }

        # ── 9. Carbapenems / Vancomycin / Colistin (Warn): physician ──────
        elif preg_status_of(dg.info) == "Warn":
            out.preg_item = {"name": dg.name, **dg.info}

        # v6.7: the English form travels with every pregnancy caution, so the
        # English PDF prints the trimester rule instead of a generic sentence.
        if out.preg_item is not None and not out.preg_item.get("preg_note_en"):
            out.preg_item["preg_note_en"] = preg_note_en(dg.name)
