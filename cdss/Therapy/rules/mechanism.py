# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Resistance-mechanism rules: ESBL / AmpC / carbapenemase versus the beta-lactams.

Every rule has the same shape:  rule(cx, dg, out) -> None
    cx   TherapyContext  the case: organism, specimen, host, mechanism (read-only)
    dg   DrugUnderTest   one agent of the panel and its S/I/R result (read-only)
    out  Outcome         where the rule records a ban / caution / note
"""
from cdss.therapy.drug_classes import _is_bli_combo
from cdss.therapy.drug_classes import _is_carbapenem
from cdss.therapy.drug_classes import _is_penicillin_or_ceph
from cdss.therapy.intrinsic import build_banned_item
from cdss.therapy.therapy_rules import NOVEL_BL_AGENTS
from cdss.therapy.therapy_rules import carb_tx_text as _carb_tx_text


def rule_esbl_not_excluded(cx, dg, out):
    """ESBL 'moderate' (not excluded): say so on the beta-lactams outside cystitis."""
    # ── ESBL "moderate" = not excluded: say so on the beta-lactams ───────
    if (cx.mech_prob == "moderate" and dg.result in ("S", "I")
            and not (cx.spec_cat == "urine" and not cx.uti_upper)
            and dg.name not in NOVEL_BL_AGENTS and "carbapenem" not in dg.cls
            and ("cephalosporin" in dg.cls
                 or dg.name in ("Piperacillin + Tazobactam", "Aztreonam",
                             "Amoxicillin + Clavulanic acid", "Ampicillin/Sulbactam"))):
        out.note(dg.name, "warn", (
            "ESBL غير مستبعد (مقاومة سيفالوسبورين بلوحة محدودة): في العدوى الغازية لا "
            "يُعتمد على هذا البيتا-لاكتام قبل نفي ESBL (اختبر Ceftriaxone/Ceftazidime أو "
            "DDST) — الكاربابينيم أضمن (IDSA AMR Guidance 2026)."), "organism_caution")


def rule_ampc_cefepime(cx, dg, out):
    """AmpC + cefepime (IDSA AMR Guidance): S is the suggested agent, SDD/I raises co-ESBL."""
    # ── AmpC + Cefepime (IDSA AMR Guidance 2024 / 2026) ───────────────────
    # FIX 2026-11-10: AmpC was routed through the ESBL branch below and
    # cefepime was demoted with an "ESBL ... avoid in bacteraemia" note.
    # IDSA suggests cefepime for moderate/high-risk AmpC organisms when the
    # isolate is susceptible; an SDD/I result raises the possibility of a
    # co-produced ESBL, and then a carbapenem is preferred.
    if (not out.skip_mech and cx.mech_prob in ("ampc", "ampc_plasmid")
            and dg.name == "Cefepime" and dg.result in ("S", "I")):
        if dg.result == "S":
            out.note(dg.name, "allow", (
                "AmpC: Cefepime ثابت أمام AmpC وهو الخيار المقترح للعدوى الغازية "
                "(IDSA 2026) طالما النتيجة S (MIC ≤ 2)."), "ampc_cefepime")
        else:
            out.note(dg.name, "warn", (
                "AmpC مع Cefepime SDD/I: احتمال ESBL مرافق — فضّل الكاربابينيم في "
                "العدوى الغازية (IDSA 2026)."), "ampc_sdd")
        out.skip_mech = True


def rule_esbl_cefepime(cx, dg, out):
    """ESBL + cefepime: cystitis only (IDSA AMR Guidance)."""
    # Cefepime + ESBL (IDSA AMR 2024/2026): not suggested for pyelonephritis,
    # cUTI or bloodstream infection even when S; acceptable for cystitis.
    # FIX 2026-11-10: was WARNED on blood while S pip-tazo on the same blood
    # culture was BANNED -- the weaker agent got the softer verdict.
    if (not out.skip_mech and cx.is_esbl_like and not cx.is_carbapenemase
            and cx.mech_prob not in ("ampc", "ampc_plasmid")
            and dg.name == "Cefepime" and dg.result in ("S", "I")):
        if cx.urine_lower:
            _wc = dict(dg.info)
            _wc["warning_reason"] = "esbl_bli_uti_only"
            _wc["esbl_note"] = (
                "كائن ESBL: Cefepime حسّاس معملياً ويُبلَّغ كما هو. مقبول لالتهاب المثانة البسيط "
                "فقط. غير مقترح لالتهاب الحويضة أو cUTI أو تجرثم الدم (IDSA 2026).")
            _wc["esbl_note_en"] = (
                "ESBL organism: cefepime is susceptible and reported as tested. Acceptable "
                "for uncomplicated cystitis only; not suggested for pyelonephritis, cUTI "
                "or bacteraemia (IDSA AMR Guidance 2026).")
            out.caution({"name": dg.name, **_wc})
            # Cefepime has had its own ESBL verdict: the generic ESBL-vs-beta-lactam
            # rule below must not add a second, vaguer one to the same drug.
            out.skip_mech = True
            return
        out.ban(build_banned_item(
            dg.name, "organism", "ESBL: Cefepime غير مقترح لهذه العدوى (IDSA 2026).",
            "كائن منتج لـ ESBL: Cefepime غير مقترح لالتهاب الحويضة أو cUTI أو تجرثم الدم "
            "حتى مع الحساسية المعملية (IDSA AMR Guidance 2026). تُبلَّغ النتيجة كما هي. "
            + ("البديل في البول العلوي: TMP-SMX أو Ciprofloxacin/Levofloxacin إذا كانت حساسة، وإلا Carbapenem."
               if cx.spec_cat == "urine" else f"البديل: {cx.invasive_tx}.")))
        return


def rule_possible_carbapenemase_betalactam(cx, dg, out):
    """Suspected (unconfirmed) carbapenemase: warn on penicillins / cephalosporins, never ban."""
    if (not out.skip_mech and cx.is_possible_carb and _is_penicillin_or_ceph(dg.info, dg.name)
            and dg.result in ("S", "I")):
        _w = dict(dg.info)
        _w["warning_reason"] = "possible_carbapenemase"
        _w["esbl_note"] = (
            "⚠️ يوجد اشتباه في كاربابينيميز (كاربابينيم واحد فقط R أو "
            "Meropenem I) — والاشتباه **ليس** تأكيداً؛ النمط قد يكون فقد "
            "بورين مع ESBL/AmpC. هذا الدواء حسّاس معملياً ويُبلَّغ كما هو "
            "(EUCAST v16). أكّد بـ mCIM أو PCR قبل التصعيد، وفي العدوى "
            "الشديدة فضّل الكاربابينيم أو استشر الأمراض المعدية."
        )
        _w["esbl_note_en"] = (
            "Carbapenemase is SUSPECTED (a single carbapenem R, or meropenem I) - a "
            "suspicion, not a confirmation; porin loss with ESBL/AmpC gives the same "
            "pattern. This agent tests susceptible and is reported as such (EUCAST v16). "
            "Confirm with mCIM or PCR before escalating; in severe infection prefer a "
            "carbapenem or seek infectious-diseases advice."
        )
        out.caution({"name": dg.name, **_w})
        return


def rule_esbl_or_carbapenemase_betalactam(cx, dg, out):
    """ESBL / AmpC / confirmed carbapenemase versus penicillins, cephalosporins and aztreonam."""
    if (not out.skip_mech and (cx.is_esbl_like or cx.is_carbapenemase)
            and _is_penicillin_or_ceph(dg.info, dg.name)):
        if (not cx.is_carbapenemase and dg.result in ("S", "I") and cx.urine_lower):
            _w = dict(dg.info)
            _w["warning_reason"] = "esbl_bli_uti_only"
            _w["esbl_note"] = (
                f"كائن {cx.mech_label}: هذا البيتا-لاكتام حسّاس معملياً -- يُبلَّغ **كما هو** "
                "(EUCAST v16؛ لا تُحوّل الحساس إلى R). خيار ممكن لالتهاب المثانة البسيط فقط "
                "(المفضّل: Nitrofurantoin أو TMP-SMX؛ Fosfomycin لـ E. coli). تجنّبه في "
                f"التهاب الحويضة وتجرثم الدم -- {cx.invasive_tx}."
            )
            _w["esbl_note_en"] = (
                f"{cx.mech_label} organism: this beta-lactam is susceptible in vitro -- report "
                "it AS TESTED (EUCAST v16). An option for uncomplicated cystitis only "
                "(preferred: nitrofurantoin or TMP-SMX; fosfomycin for E. coli). Avoid in "
                "pyelonephritis and bacteraemia (IDSA AMR Guidance 2026)."
            )
            out.caution({"name": dg.name, **_w})
            return
        if cx.is_carbapenemase:
            out.ban(build_banned_item(
                dg.name, "organism", "غير مُوصى به -- كائن منتج لـ Carbapenemase.",
                "الكائن منتج لـ Carbapenemase: لا يُعتمد على البنسلينات أو السيفالوسبورينات "
                "التقليدية حتى لو ظهرت حساسة. العلاج النهائي: " + _carb_tx_text(cx.carb_type) + "."))
        else:
            out.ban(build_banned_item(
                dg.name, "organism", f"غير مُوصى به -- كائن منتج لـ {cx.mech_label}.",
                f"الكائن منتج لـ {cx.mech_label}. الحساسية المعملية تُبلَّغ كما هي، لكن "
                f"{cx.invasive_why}. الخيار العلاجي: {cx.invasive_tx}."))
        return


def rule_carbapenemase_carbapenem(cx, dg, out):
    """Confirmed carbapenemase: carbapenems are not relied on."""
    # ── Carbapenemase: also suppress carbapenems ──────────────────────────
    if not out.skip_mech and cx.is_carbapenemase and _is_carbapenem(dg.info):
        out.ban(build_banned_item(
            dg.name, "organism",
            "غير فعّال -- كائن منتج لـ Carbapenemase.",
            "الكائن منتج لإنزيم Carbapenemase: لا يُعتمد على الكاربابينيم منفرداً. "
            "العلاج النهائي: " + _carb_tx_text(cx.carb_type) + ".",
        ))
        return


def rule_possible_carbapenemase_bli(cx, dg, out):
    """Suspected carbapenemase versus beta-lactamase-inhibitor combinations."""
    # ── BLI combinations (Amox-Clav, Amp-Sulb, Pip-Tazo, Cefop-Sulb) ──────
    # A *suspicion* of carbapenemase: warn and ask for confirmation, never
    # ban (pip-tazo is the more robust agent against the porin-loss/AmpC
    # phenotype that most often explains an isolated ertapenem R).
    if (not out.skip_mech and cx.is_possible_carb
            and not (cx.is_esbl_like or cx.is_carbapenemase)
            and _is_bli_combo(dg.info, dg.name) and dg.result in ("S", "I")):
        _w = dict(dg.info)
        _w["warning_reason"] = "possible_carbapenemase"
        if not cx.urine_lower:
            _w["esbl_note"] = (
                "⛔ لا تستخدمه كعلاج نهائي منفرد في هذه العينة. اشتباه كاربابينيميز "
                "غير مؤكد (كاربابينيم واحد R أو Meropenem I). "
                "التوليفة حسّاسة معملياً وتُبلَّغ كما هي (EUCAST v16). "
                "ابدأ بالكاربابينيم وأكّد بـ mCIM أو PCR، ولا تنزل لهذه التوليفة إلا "
                "بعد نفي الإنزيم واستشارة الأمراض المعدية."
            )
            _w["esbl_note_en"] = (
                "DO NOT use as definitive monotherapy for this specimen. Unconfirmed "
                "carbapenemase suspicion. Susceptible in vitro and reported as tested "
                "(EUCAST v16). Start a carbapenem, confirm with mCIM/PCR, and de-escalate "
                "only once the enzyme is excluded and ID has been consulted."
            )
        else:
            _w["esbl_note"] = (
                "⚠️ اشتباه كاربابينيميز غير مؤكد (كاربابينيم واحد R أو Meropenem I). "
                "هذه التوليفة حسّاسة معملياً وتُبلَّغ كما هي (EUCAST v16). خيار مقبول "
                "لالتهاب المثانة البسيط عند ثبوت الحساسية؛ أكّد بـ mCIM أو PCR."
            )
            _w["esbl_note_en"] = (
                "Unconfirmed carbapenemase suspicion. Susceptible in vitro and reported "
                "as tested (EUCAST v16). Acceptable for uncomplicated cystitis when proven "
                "S; confirm with mCIM or PCR."
            )
        out.caution({"name": dg.name, **_w})
        return


def rule_esbl_or_carbapenemase_bli(cx, dg, out):
    """ESBL / AmpC / carbapenemase versus beta-lactamase-inhibitor combinations."""
    if (not out.skip_mech and (cx.is_esbl_like or cx.is_carbapenemase)
            and _is_bli_combo(dg.info, dg.name)):
        _is_pt = "piperacillin" in dg.low
        if cx.is_carbapenemase:
            out.ban({**dg.info, **build_banned_item(
                name=dg.name, category="organism",
                reason_short="Carbapenemase -- المثبط التقليدي غير كافٍ.",
                reason_detail=("Tazobactam و Sulbactam و Clavulanate لا تثبّط الكاربابينيميز. "
                               "العلاج النهائي: " + _carb_tx_text(cx.carb_type) + "."))})
            return
        # cUTI / pyelonephritis: IDSA AMR Guidance 2026 lists pip-tazo as an
        # ALTERNATIVE for ESBL-E cUTI (TMP-SMX / FQ preferred); not amox-clav.
        if (cx.spec_cat == "urine" and cx.uti_upper and _is_pt
                and dg.result in ("S", "I")):
            _w = dict(dg.info)
            _w["warning_reason"] = "esbl_bli_uti_only"
            _w["esbl_note"] = (
                (f"كائن {cx.mech_label} + التهاب حويضة / cUTI: Pip-Tazo بديل مقبول (IDSA 2026) "
                 "بجرعة 4.5 g q6h وتسريب ممتد، والمفضّل TMP-SMX أو Ciprofloxacin/Levofloxacin إذا كانت "
                 "حساسة. في حالة الصدمة أو تجرثم الدم: Carbapenem.")
                if cx.mech_label == "ESBL" else
                ("AmpC + التهاب حويضة: Cefepime (إذا S) مقدَّم على Pip-Tazo (IDSA 2026)."))
            out.caution({"name": dg.name, **_w})
            return
        if not cx.urine_lower:
            out.ban({**dg.info, **build_banned_item(
                name=dg.name, category="organism",
                reason_short=(f"{cx.mech_label} + عدوى غازية/علوية -- BLI غير مقترح."),
                reason_detail=(
                    (f"كائن منتج لـ ESBL في {'التهاب حويضة / cUTI' if cx.spec_cat == 'urine' else 'عينة غير بولية'}: "
                     + ("Amoxicillin-clavulanate / Ampicillin-sulbactam لالتهاب المثانة فقط (IDSA 2026). "
                        if not _is_pt else
                        "Pip-Tazo أظهر وفيات أعلى من Meropenem في تجرثم الدم (MERINO 2018: 12.3% مقابل 3.7%). ")
                     + f"البديل: {cx.invasive_tx}.")
                    if cx.mech_label == "ESBL" else
                    (f"{cx.invasive_why}. البديل: {cx.invasive_tx}.")),
            )})
            return
        _w = dict(dg.info)
        _w["warning_reason"] = "esbl_bli_uti_only"
        _w["esbl_note"] = (f"كائن {cx.mech_label}: هذه التوليفة مقبولة لالتهاب المثانة البسيط عند "
                           "ثبوت الحساسية (IDSA 2026). لا تُستخدم في تجرثم الدم أو العدوى الشديدة "
                           f"-- {cx.invasive_tx}.")
        _w["esbl_note_en"] = (f"{cx.mech_label} organism: this BLI combination is acceptable for "
                              "uncomplicated cystitis when proven susceptible (IDSA 2026). Not "
                              "for bacteraemia or serious infection.")
        out.caution({"name": dg.name, **_w})
        return
