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
    """ESBL 'moderate' (not excluded): say so on every ESBL-labile beta-lactam.

    v7.6 (random end-to-end sweep, V05): two gaps let an ESBL-labile agent be
    RANKED under the "Suspected ESBL" heading the same report printed --
      * the class list named cephalosporins and the BL/BLI pairs but not the
        plain penicillins, so ampicillin S was ranked while cefuroxime S was
        cautioned (an ESBL hydrolyses ampicillin first);
      * in cystitis nothing was said at all, while an ESBL called "high" is
        already "an option for cystitis only" (rule below).
    Now every penicillin / cephalosporin / aztreonam S or I gets the caution;
    in cystitis it stays an option, under caution, not first-ranked.
    """
    if (out.skip_mech or cx.mech_prob != "moderate" or dg.result not in ("S", "I")
            or dg.name in NOVEL_BL_AGENTS or "carbapenem" in dg.cls
            or not (_is_penicillin_or_ceph(dg.info, dg.name) or "cephalosporin" in dg.cls
                    or dg.name in ("Piperacillin + Tazobactam", "Aztreonam",
                                   "Amoxicillin + Clavulanic acid", "Ampicillin/Sulbactam"))):
        return
    if cx.spec_cat == "urine" and not cx.uti_upper:
        out.note(dg.name, "warn", (
            "ESBL غير مستبعد: هذا البيتا-لاكتام حسّاس معملياً ويُبلَّغ كما هو — خيار لالتهاب "
            "المثانة البسيط فقط (المفضّل: Nitrofurantoin أو TMP-SMX؛ Fosfomycin لـ E. coli). "
            "لو ظهرت حرارة أو ألم في الجنب أو تجرثم دم لا يُعتمد عليه قبل نفي ESBL "
            "(IDSA AMR Guidance 2026)."), "esbl_not_excluded_cystitis")
        return
    out.note(dg.name, "warn", (
        "ESBL غير مستبعد (مقاومة سيفالوسبورين بلوحة محدودة): في العدوى الغازية لا "
        "يُعتمد على هذا البيتا-لاكتام قبل نفي ESBL (اختبر Ceftriaxone/Ceftazidime أو "
        "DDST) — الكاربابينيم أضمن (IDSA AMR Guidance 2026)."), "esbl_not_excluded")


def rule_ampc_cefepime(cx, dg, out):
    """AmpC + cefepime (IDSA AMR Guidance 2026): preferred while the MIC is <=8 (S or SDD)."""
    # ── AmpC + Cefepime (IDSA AMR Guidance 2024 / 2026) ───────────────────
    # FIX 2026-11-10: AmpC was routed through the ESBL branch below and
    # cefepime was demoted with an "ESBL ... avoid in bacteraemia" note.
    # IDSA suggests cefepime for moderate/high-risk AmpC organisms when the
    # isolate is susceptible -- and, from the 2026 update, also when it is SDD
    # (see the SDD branch below).
    if (not out.skip_mech and cx.mech_prob in ("ampc", "ampc_plasmid")
            and dg.name == "Cefepime" and dg.result in ("S", "I")):
        if dg.result == "S":
            out.note(dg.name, "allow", (
                "AmpC: Cefepime ثابت أمام AmpC وهو الخيار المقترح للعدوى الغازية "
                "(IDSA 2026) طالما MIC ≤ 8 (S، أو SDD بالجرعة العالية)."), "ampc_cefepime")
        else:
            # v6.9: IDSA 2026 (Q2.3) changed this. Cefepime is preferred while
            # the MIC is <=8 (S or SDD) unless an ESBL gene has been identified
            # -- "available evidence does not suggest an association between
            # cefepime SDD MICs and ESBL production". The 2024 text (SDD ->
            # suspect co-ESBL -> carbapenem) is retired. It stays a caution: an
            # SDD needs the high-exposure regimen (CLSI M100).
            out.note(dg.name, "warn", (
                "AmpC مع Cefepime SDD (MIC 4–8): IDSA 2026 — يظل Cefepime هو المفضّل طالما MIC ≤ 8 "
                "ولم يُكتشف جين ESBL (الأدلة لا تربط SDD بإنتاج ESBL)، لكن **بنظام الجرعة العالية "
                "2 g q8h** (CLSI SDD). إذا ثبت ESBL: Carbapenem."), "ampc_sdd")
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
            "(CLSI M100 Ed36 Table 3A). أكّد بـ mCIM أو PCR قبل التصعيد، وفي العدوى "
            "الشديدة فضّل الكاربابينيم أو استشر الأمراض المعدية."
        )
        _w["esbl_note_en"] = (
            "Carbapenemase is SUSPECTED (a single carbapenem R, or meropenem I) - a "
            "suspicion, not a confirmation; porin loss with ESBL/AmpC gives the same "
            "pattern. This agent tests susceptible and is reported as such (CLSI M100 Ed36 Table 3A). "
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
                "(CLSI M100 Ed36 Table 3A؛ لا تُحوّل الحساس إلى R). خيار ممكن لالتهاب المثانة البسيط فقط "
                "(المفضّل: Nitrofurantoin أو TMP-SMX؛ Fosfomycin لـ E. coli). تجنّبه في "
                f"التهاب الحويضة وتجرثم الدم -- {cx.invasive_tx}."
            )
            _w["esbl_note_en"] = (
                f"{cx.mech_label} organism: this beta-lactam is susceptible in vitro -- report "
                "it AS TESTED (CLSI M100 Ed36 Table 3A). An option for uncomplicated cystitis only "
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
                "التوليفة حسّاسة معملياً وتُبلَّغ كما هي (CLSI M100 Ed36 Table 3A). "
                "ابدأ بالكاربابينيم وأكّد بـ mCIM أو PCR، ولا تنزل لهذه التوليفة إلا "
                "بعد نفي الإنزيم واستشارة الأمراض المعدية."
            )
            _w["esbl_note_en"] = (
                "DO NOT use as definitive monotherapy for this specimen. Unconfirmed "
                "carbapenemase suspicion. Susceptible in vitro and reported as tested "
                "(CLSI M100 Ed36 Table 3A). Start a carbapenem, confirm with mCIM/PCR, and de-escalate "
                "only once the enzyme is excluded and ID has been consulted."
            )
        else:
            _w["esbl_note"] = (
                "⚠️ اشتباه كاربابينيميز غير مؤكد (كاربابينيم واحد R أو Meropenem I). "
                "هذه التوليفة حسّاسة معملياً وتُبلَّغ كما هي (CLSI M100 Ed36 Table 3A). خيار مقبول "
                "لالتهاب المثانة البسيط عند ثبوت الحساسية؛ أكّد بـ mCIM أو PCR."
            )
            _w["esbl_note_en"] = (
                "Unconfirmed carbapenemase suspicion. Susceptible in vitro and reported "
                "as tested (CLSI M100 Ed36 Table 3A). Acceptable for uncomplicated cystitis when proven "
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
            # v7.4 (external case review): the note named TMP-SMX and ciprofloxacin
            # as "preferred when susceptible" on an isolate R to both, and gave
            # 4.5 g q6h as if renal function did not matter. It now reads THIS
            # isolate's results and says the dose is for normal renal function.
            _pref = [(n, str((cx.sir or {}).get(n) or "")) for n in
                     ("Trimethoprim/Sulfamethoxazole", "Ciprofloxacin", "Levofloxacin")]
            _pref_s = [n for n, r in _pref if r == "S"]
            _pref_state = ", ".join(f"{'TMP-SMX' if n.startswith('Trim') else n} "
                                    f"{r or 'not tested'}" for n, r in _pref)
            if _pref_s:
                _pref_en = (f"{', '.join(_pref_s)} tested S on this isolate and is preferred over "
                            "piperacillin-tazobactam (IDSA 2026).")
                _pref_ar = (f"{', '.join(_pref_s)} حساس في هذه المزرعة ومفضّل على Pip-Tazo "
                            "(IDSA 2026).")
            else:
                _pref_en = (f"Preferred agents unavailable here ({_pref_state}): a carbapenem "
                            "is preferred.")
                _pref_ar = (f"الأدوية المفضّلة غير متاحة في هذه المزرعة ({_pref_state})؛ "
                            "الكاربابينيم مفضّل، و Pip-Tazo بديل (IDSA 2026).")
            _w["esbl_note"] = (
                (f"اشتباه {cx.mech_label} + التهاب حويضة / cUTI: Pip-Tazo بديل (IDSA 2026) فقط "
                 "لو المريض مش في حالة حرجة ومفيش تجرثم دم؛ احتمال فشل العلاج قائم — تابِع "
                 f"الاستجابة. {_pref_ar} الجرعة 4.5 g q6h بتسريب ممتد لوظائف كلى طبيعية — "
                 "تُعدَّل حسب CrCl. في الصدمة أو تجرثم الدم: Carbapenem.")
                if cx.mech_label == "ESBL" else
                ("AmpC + التهاب حويضة: Cefepime (إذا S) مقدَّم على Pip-Tazo (IDSA 2026)."))
            # v6.7: the English PDF had no English form of this note.
            _w["esbl_note_en"] = (
                (f"Suspected {cx.mech_label} + pyelonephritis / cUTI: pip-tazo is an alternative "
                 "(IDSA 2026) if not critically ill and not bacteraemic - monitor the response. "
                 f"{_pref_en} 4.5 g q6h extended infusion if renal function is normal - adjust to "
                 "CrCl. Shock / bacteraemia: a carbapenem.")
                if cx.mech_label == "ESBL" else
                ("AmpC + pyelonephritis: cefepime (if S) is preferred over "
                 "piperacillin-tazobactam (IDSA 2026)."))
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
