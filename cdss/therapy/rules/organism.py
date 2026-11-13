# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Organism-specific rules: intrinsic resistance, MRSA, CLSI/EUCAST reporting restrictions.

Every rule has the same shape:  rule(cx, dg, out) -> None
    cx   TherapyContext  the case: organism, specimen, host, mechanism (read-only)
    dg   DrugUnderTest   one agent of the panel and its S/I/R result (read-only)
    out  Outcome         where the rule records a ban / caution / note
"""
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.therapy.drug_classes import _BLI_TOKENS
from cdss.therapy.drug_classes import _cls_and_name
from cdss.therapy.intrinsic import build_banned_item
from cdss.therapy.intrinsic import is_intrinsically_avoided
from cdss.therapy.therapy_rules import NOVEL_BL_AGENTS
from cdss.therapy.therapy_rules import novel_agent_verdict as _novel_agent_verdict


def rule_intrinsic(cx, dg, out):
    """Intrinsic resistance (EUCAST Expert Rules v3.3 table) and the organism's clinical avoid list."""
    _avoid_src = is_intrinsically_avoided(cx.organism, dg.name, dg.info, return_source=True)
    if _avoid_src == "intrinsic":
        out.ban(build_banned_item(
            dg.name, "organism",
            f"غير فعال لـ {cx.organism} طبيعياً.",
            f"{dg.name} لديه مقاومة طبيعية أو عدم فعالية ضد {cx.organism}.",
        ))
        return
    if _avoid_src == "profile":
        # FIX 2026-11-10: a profile "avoid" is a CLINICAL recommendation,
        # not intrinsic resistance, and must not be worded as one.
        out.ban(build_banned_item(
            dg.name, "organism",
            f"غير موصى به لـ {cx.organism}.",
            f"{dg.name}: مدرج في قائمة التجنّب السريرية لهذا الكائن (ملف الكائن). "
            "ليس مقاومة جوهرية — راجع الملاحظة الخاصة بالكائن.",
        ))
        return


def rule_mrsa(cx, dg, out):
    """MRSA (mecA/PBP2a): every beta-lactam except ceftaroline fails."""
    # ── MRSA: ALL beta-lactams (penicillins + cephalosporins) fail ────────
    # Detected from AST (Oxacillin/Cefoxitin R) OR organism name = MRSA.
    # Exception: carbapenems also fail for MRSA but are caught here too.
    #
    # FIX 2026-08-01: the filter read ONLY the class string, for the tokens
    # penicillin / cephalosporin / carbapenem. Amoxicillin + Clavulanic acid
    # is classed "Beta-lactamase Inhibitor Combination" -- none of the three
    # -- so it escaped and reached the CAUTION bucket, while every other BLI
    # combo (Amp-Sulbactam, Pip-Tazo, Cefoperazone-Sulbactam) was caught
    # only because its class text happens to spell out "Penicillin" or
    # "Cephalosporin". Worse, the same isolate typed as "MRSA" rather than
    # "Staphylococcus aureus + Oxacillin-R" got Amox-Clav BANNED by the
    # intrinsic table -- two different verdicts for one organism, decided by
    # how the technologist spelled the name.
    # mecA/PBP2a is an ALTERED TARGET, not a beta-lactamase: no inhibitor
    # rescues any beta-lactam. Match on class AND name, and include the
    # inhibitor tokens.
    # FIX 2026-11-10: Ceftaroline binds PBP2a and is THE anti-MRSA
    # cephalosporin; the "cef" token banned it on every MRSA.
    if cx.is_mrsa and dg.name != "Ceftaroline" and any(k in _cls_and_name(dg.info, dg.name)
                        for k in ("penicillin", "cephalosporin", "carbapenem",
                                  "cillin", "cef", "ceph", "penem",
                                  "monobactam", "aztreonam", *_BLI_TOKENS)):
        out.ban(build_banned_item(
            dg.name, "organism", "بيتا-لاكتام -- لا يعمل على MRSA.",
            "MRSA يحمل جين mecA (PBP2a) -> مقاوم لكل البيتا-لاكتام (البنسلينات، "
            "السيفالوسبورينات التقليدية، والكاربابينيمات) حتى لو أظهرت المزرعة حساسية. "
            "العلاج: Vancomycin / Linezolid / Daptomycin (حسب الموقع والحساسية).",
        ))
        return


def rule_possible_mrsa(cx, dg, out):
    """Unconfirmed MRSA: caution on beta-lactams until cefoxitin / mecA is known."""
    # Unconfirmed MRSA: caution, never silent approval. See _possible_mrsa.
    if cx.possible_mrsa and dg.name != "Ceftaroline" and any(k in _cls_and_name(dg.info, dg.name)
                              for k in ("penicillin", "cephalosporin",
                                        "carbapenem", "cillin", "cef",
                                        "ceph", "penem", *_BLI_TOKENS)):
        # The note must describe the panel that is actually there. It used to say
        # "the panel has neither oxacillin nor cefoxitin" unconditionally -- also
        # when one of them WAS reported susceptible and the real finding is a
        # discordant result, which calls for a repeat, not for a first screen.
        _screen_s = [d for d in ("Cefoxitin", "Oxacillin") if cx.sir.get(d) == "S"]
        _screen_i = [d for d in ("Cefoxitin", "Oxacillin") if cx.sir.get(d) == "I"]
        if _screen_i:
            _note = (
                "⚠️ **فحص الميثيسيلين غير صالح — مقاومة الميثيسيلين غير مستبعدة.** "
                f"{' و '.join(_screen_i)} = I، ولا توجد فئة Intermediate لهذا الاختبار في "
                "المكورات العنقودية (EUCAST v16 / CLSI M100): النتيجة إما S أو R.\n"
                "**قبل الاعتماد على أي بيتا-لاكتام:** أعِد Cefoxitin disk أو اطلب PCR "
                "(mecA/mecC). في تجرثم الدم ابدأ بـ Vancomycin تجريبياً حتى تُحسم النتيجة.")
        elif _screen_s:
            _note = (
                "⚠️ **نتائج متعارضة — مقاومة الميثيسيلين غير مستبعدة.** "
                f"{' و '.join(_screen_s)} = S على اللوحة، لكن بيتا-لاكتام آخر مقاوم مع "
                "Vancomycin/Linezolid حسّاس. النمط غير متّسق (BORSA / mecC / خطأ قراءة).\n"
                "**قبل الاعتماد على أي بيتا-لاكتام:** أعِد Cefoxitin disk أو اطلب PCR "
                "(mecA/mecC). في تجرثم الدم ابدأ بـ Vancomycin تجريبياً حتى يُحسم التعارض.")
        else:
            _note = (
                "⚠️ **اشتباه MRSA غير مؤكَّد.** اللوحة لا تحتوي Oxacillin "
                "ولا Cefoxitin، والنمط (بيتا-لاكتام مقاوم + Vancomycin/"
                "Linezolid حسّاس) يوحي بمقاومة الميثيسيلين. لو كانت MRSA "
                "فكل البيتا-لاكتام سيفشل بغض النظر عن نتيجة القرص "
                "(mecA/PBP2a هدف مُعدَّل وليس إنزيماً).\n"
                "**قبل استخدام أي بيتا-لاكتام:** اطلب Cefoxitin disk أو "
                "PCR (mecA). في تجرثم الدم ابدأ بـ Vancomycin تجريبياً "
                "حتى يظهر التأكيد.")
        _w = {"name": dg.name, **dg.info,
              "warning_reason": "possible_mrsa",
              "possible_mrsa_note": _note}
        out.caution(_w)
        return


def rule_novel_agents(cx, dg, out):
    """Novel beta-lactam / BLI agents are judged on their own activity (IDSA AMR Guidance)."""
    # ── Novel beta-lactams / BLIs (2026-11-10) ─────────────────────────────
    # Judged on their OWN activity, never by the old-beta-lactam mechanism
    # bans below (see _novel_agent_verdict for the defect this closes).
    out.skip_mech = False
    if dg.name in NOVEL_BL_AGENTS:
        _nv, _nn = _novel_agent_verdict(dg.name, cx.organism, cx.mech, cx.carb_type, cx.sir)
        if _nv == "ban":
            out.ban(build_banned_item(dg.name, "organism", _nn[:170], _nn))
            return
        out.note(dg.name, _nv, _nn, "novel_agent")
        out.skip_mech = True


def rule_pseudomonas_aminoglycosides(cx, dg, out):
    """P. aeruginosa: gentamicin removed, amikacin urinary only (CLSI M100 Ed33)."""
    # ── P. aeruginosa + aminoglycosides (CLSI M100 Ed33, 2023) ────────────
    # CLSI eliminated gentamicin as a treatment option for P. aeruginosa
    # (suppress or report R) and limited amikacin to urinary isolates.
    if "pseudomonas" in cx.org_l and dg.name == "Gentamicin":
        out.ban(build_banned_item(
            dg.name, "no_breakpoint",
            "CLSI 2023: Gentamicin لم يعد خياراً ضد P. aeruginosa.",
            "CLSI M100 Ed33 (2023) ألغى Gentamicin كخيار علاجي لـ P. aeruginosa "
            "(أقصى MIC يحقق التثبيط 0.5 µg/mL، أقل بكثير من الـ ECV). "
            "يُحجب من التقرير أو يُبلَّغ R. البديل من نفس الصنف: Tobramycin."))
        return
    if ("pseudomonas" in cx.org_l and dg.name == "Amikacin"
            and cx.spec_cat != "urine"):
        out.note(dg.name, "warn", (
            "CLSI M100 Ed33: breakpoints الأميكاسين لـ P. aeruginosa على عزلات البول فقط. "
            "خارج البول لا يُستخدم الأمينوجليكوزيد إلا في توليفة مع بيتا-لاكتام فعّال."),
            "aminoglycoside_pseudomonas")


def rule_surrogate_and_no_breakpoint(cx, dg, out):
    """Agents that are a screening surrogate, or have no clinical breakpoint, for this organism."""
    # ── Added v6.6 (2026-11-13, final review) ─────────────────────────────
    # Cefoxitin in staphylococci is the mecA SCREEN (CLSI M100, EUCAST): the
    # result is reported as oxacillin and is never a cefoxitin treatment option.
    # It was on the recommended list for MSSA bacteraemia, after vancomycin.
    if dg.name == "Cefoxitin" and cx.is_staph_r2 and dg.result in ("S", "I"):
        out.ban(build_banned_item(
            dg.name, "no_breakpoint",
            "Cefoxitin في Staphylococcus = اختبار كشف MRSA فقط — يُقرأ كـ Oxacillin وليس علاجاً.",
            "CLSI M100 و EUCAST: قرص Cefoxitin في المكورات العنقودية بديل (surrogate) لكشف "
            "mecA، ونتيجته تُبلَّغ كـ Oxacillin (S = MSSA ← Cefazolin أو Oxacillin؛ R = MRSA). "
            "Cefoxitin نفسه لا يُستخدم لعلاج المكورات العنقودية."))
        return
    # Vancomycin and Listeria: no CLSI (M45) or EUCAST breakpoint, and treatment
    # failures in meningitis are documented. It ranked second for Listeria CSF.
    if dg.name == "Vancomycin" and "listeria" in cx.org_l and dg.result in ("S", "I"):
        out.ban(build_banned_item(
            dg.name, "no_breakpoint",
            "Listeria: لا توجد نقاط قطع لـ Vancomycin — ليس خياراً علاجياً.",
            "CLSI M45 و EUCAST لا يضعان breakpoints لـ Vancomycin مع Listeria monocytogenes، "
            "وفشل العلاج به في التهاب السحايا موثّق. الخيار: Ampicillin أو Penicillin G بجرعة "
            "عالية (± Gentamicin)؛ البديل: TMP-SMX (IDSA bacterial meningitis)."))


def rule_organism_cautions(cx, dg, out):
    """Organism-specific cautions and agent notes from ORGANISM_PROFILE."""
    # ── Organism-specific clinical cautions (2026-11-10) ──────────────────
    # Not intrinsic resistance: an agent that tests S and works, but whose
    # use depends on the infection (e.g. a 3rd-gen cephalosporin against a
    # moderate-risk AmpC organism, IDSA AMR Guidance 2026).
    # The mechanism blocks below still run: an ESBL/carbapenemase verdict
    # is stronger than an organism caution and must not be skipped.
    _prof_aa = ORGANISM_PROFILE.get(cx.organism) or {}
    _pcaut = _prof_aa.get("caution") or {}
    if dg.name in _pcaut and dg.result in ("S", "I"):
        # IDSA 2026: for AmpC organisms the 3rd-gen caution is about
        # INVASIVE infection -- in uncomplicated cystitis the S agent is
        # reasonable, so it stays recommended with the note attached.
        _cyst = (cx.spec_cat == "urine" and not cx.uti_upper
                 and "AmpC" in str(_pcaut[dg.name]))
        out.note(dg.name, "allow" if _cyst else "warn", _pcaut[dg.name], "organism_caution")
    _pnote = (_prof_aa.get("agent_notes") or {}).get(dg.name)
    if _pnote and dg.result in ("S", "I", None):
        out.note(dg.name, "allow", _pnote, "organism_note")


def rule_colistin(cx, dg, out):
    """Colistin: no S category, broth microdilution only."""
    # ── Colistin: no S category, BMD only (CLSI M100 / EUCAST) ───────────
    if dg.name == "Colistin" and dg.result in ("S", "I"):
        out.note(dg.name, "warn", (
            "Colistin: لا توجد فئة S في CLSI (I ≤ 2 / R ≥ 4 µg/mL) والاختبار بـ broth "
            "microdilution فقط — نتيجة القرص أو الشريط غير صالحة. دواء Reserve يُستخدم في "
            "توليفة مع مراقبة الكلى، و IDSA لا تفضّله لـ CRE أو DTR-PA عند توفر بديل حديث."),
            "colistin")


def rule_oral_fosfomycin(cx, dg, out):
    """Oral fosfomycin breakpoints exist for E. coli (and E. faecalis in CLSI) only."""
    # ── Oral fosfomycin outside E. coli (CLSI / EUCAST) ───────────────────
    if (dg.name == "Fosfomycin" and dg.result in ("S", "I")
            and not any(k in cx.org_l for k in ("e. coli", "escherichia", "e.coli",
                                                 "enterococcus faecalis"))):
        out.note(dg.name, "warn", (
            "Fosfomycin الفموي: breakpoints في CLSI و EUCAST لـ E. coli (و E. faecalis في "
            "CLSI) فقط. Klebsiella تحمل fosA كروموسومياً — النتيجة هنا غير مُعايَرة."),
            "no_breakpoint")


def rule_staph_penicillin_note(cx, dg, out):
    """Penicillin-S staphylococci need a negative penicillinase test (CLSI M100)."""
    # ── Penicillin-S S. aureus needs a negative penicillinase test ────────
    if (dg.name in ("Penicillin", "Ampicillin", "Amoxicillin") and dg.result == "S"
            and ("staph" in cx.org_l or "mssa" in cx.org_l)):
        # cx.penicillinase comes from the RAW panel (cdss.common.aux_tests); the
        # normalised S/I/R map this used to read never contained it.
        _bz = cx.penicillinase
        if _bz == "POSITIVE":
            # A positive penicillinase test overrides an in-vitro "S": the isolate
            # is reported penicillin-resistant (CLSI M100).
            out.ban(build_banned_item(
                dg.name, "penicillinase_producer",
                "Penicillinase موجب — يُبلَّغ مقاوماً",
                "اختبار البنسليناز (zone-edge / nitrocefin / blaZ) موجب: البنسلينات الحسّاسة "
                "للبنسليناز تُبلَّغ مقاومة مهما كانت نتيجة القرص/MIC — CLSI M100. "
                "استخدم Cefazolin أو Oxacillin (MSSA)."))
            return
        if _bz != "NEGATIVE":
            out.note(dg.name, "warn", (
                "Penicillin = S في Staphylococcus يحتاج تأكيد سلبية البنسليناز (zone-edge "
                "أو nitrocefin أو blaZ PCR) قبل الاعتماد عليه — CLSI M100."),
                "penicillinase_unconfirmed")


def rule_strep_tmp_smx(cx, dg, out):
    """Beta-haemolytic streptococci + TMP-SMX: skin and soft tissue only (CLSI M100 Ed36)."""
    # ── Beta-haemolytic streptococci + TMP-SMX (CLSI M100 Ed36) ───────────
    if (("trimethoprim" in dg.low or "sulfamethox" in dg.low)
            and any(k in cx.org_l for k in ("streptococcus pyogenes",
                                             "streptococcus agalactiae"))):
        if cx.spec_cat not in ("wound", "pus"):
            out.ban(build_banned_item(
                dg.name, "no_breakpoint",
                "CLSI 2026: breakpoints لعدوى الجلد فقط.",
                "CLSI M100 Ed36 أضاف breakpoints لـ TMP-SMX مع المكورات الحالّة بيتا "
                "لعدوى الجلد والأنسجة الرخوة فقط — لا تُبلَّغ في البلعوم أو البول أو الدم."))
            return
        out.note(dg.name, "warn", "CLSI M100 Ed36: مقبول لعدوى الجلد والأنسجة الرخوة فقط.",
                             "no_breakpoint")


def rule_macrolide_cross_resistance(cx, dg, out):
    """Erythromycin R predicts azithromycin / clarithromycin (CLSI M100)."""
    # ── Macrolides: erythromycin predicts azithromycin / clarithromycin ──
    # CLSI M100 Table 1 footnote: "susceptibility and resistance to
    # azithromycin and clarithromycin can be predicted by testing
    # erythromycin" (staphylococci, streptococci). erm / mef are shared.
    if (dg.name in ("Azithromycin", "Clarithromycin") and dg.result in ("S", "I")
            and cx.sir.get("Erythromycin") == "R"
            and (cx.is_staph_r2 or cx.is_strep_r2)):
        out.ban(build_banned_item(
            dg.name, "cross_resistance",
            "Erythromycin R ← مقاومة متصالبة لكل الماكروليدات.",
            f"{dg.name} ظهر حساساً بينما Erythromycin = R. في المكورات العنقودية والعقدية "
            "نتيجة Erythromycin تتنبأ بـ Azithromycin و Clarithromycin (CLSI M100، "
            "آلية erm/mef مشتركة) — النتيجة تُعامل كمقاومة ويُراجَع الاختبار."))
        return


def rule_enterococci(cx, dg, out):
    """Enterococci: fluoroquinolones urinary only; no meropenem/ertapenem; ampicillin R is predictive."""
    # ── Enterococci ───────────────────────────────────────────────────────
    if cx.is_entero_r2 and dg.result in ("S", "I"):
        # Fluoroquinolones: CLSI lists them for URINARY isolates only.
        if "fluoroquinolone" in dg.cls and cx.spec_cat != "urine":
            out.ban(build_banned_item(
                dg.name, "no_breakpoint",
                "CLSI: الفلوروكينولون مع Enterococcus للبول فقط.",
                "CLSI M100 يدرج Ciprofloxacin/Levofloxacin مع المكورات المعوية لعزلات "
                "البول فقط (Group U) — لا تُبلَّغ ولا تُستخدم في الدم أو الجروح أو غيرها. "
                "البديل: Ampicillin إن كان حساساً، وإلا Vancomycin / Linezolid / Daptomycin."))
            return
        # Meropenem / ertapenem: no enterococcal breakpoints, unreliable.
        if dg.name in ("Meropenem", "Ertapenem", "Meropenem + Vaborbactam"):
            out.ban(build_banned_item(
                dg.name, "no_breakpoint",
                "لا breakpoints لهذا الكاربابينيم مع Enterococcus.",
                f"{dg.name}: لا توجد breakpoints في CLSI أو EUCAST مع المكورات المعوية ونشاطه "
                "غير موثوق (Ertapenem بلا نشاط). Imipenem فقط يُتنبأ به من Ampicillin "
                "في E. faecalis."))
            return
        # Ampicillin R predicts the other penicillins and imipenem.
        if (cx.sir.get("Ampicillin") == "R"
                and dg.name in ("Penicillin", "Amoxicillin", "Amoxicillin + Clavulanic acid",
                             "Ampicillin/Sulbactam", "Piperacillin + Tazobactam",
                             "Imipenem/Cilastatin", "Imipenem + Relebactam")):
            out.ban(build_banned_item(
                dg.name, "cross_resistance",
                "Ampicillin R ← مقاومة متوقعة لهذا البيتا-لاكتام.",
                f"{dg.name} ظهر حساساً بينما Ampicillin = R. في Enterococcus نتيجة Ampicillin "
                "تتنبأ بـ Amoxicillin و Amoxicillin-clavulanate و Ampicillin-sulbactam و "
                "Piperacillin-tazobactam و Imipenem (CLSI M100) — تُعامل كمقاومة."))
            return


def rule_pneumococcus_csf(cx, dg, out):
    """S. pneumoniae meningitis breakpoints have no Intermediate category."""
    # ── S. pneumoniae in CSF: meningitis breakpoints have no "I" ─────────
    if cx.is_pneumo_r2 and cx.spec_cat == "csf" and dg.result == "I":
        if dg.name in ("Penicillin", "Ampicillin", "Amoxicillin"):
            out.ban(build_banned_item(
                dg.name, "no_breakpoint",
                "التهاب السحايا: Penicillin غير الحساس = مقاوم.",
                "breakpoints التهاب السحايا لـ S. pneumoniae (CLSI M100): S ≤ 0.06 و "
                "R ≥ 0.12 µg/mL — لا توجد فئة Intermediate. النتيجة I تُعامل كمقاومة: "
                "Ceftriaxone/Cefotaxime بجرعة عالية + Vancomycin حتى ظهور الـ MIC."))
            return
        if dg.name in ("Ceftriaxone", "Cefotaxime"):
            out.note(dg.name, "warn", (
                "التهاب السحايا بـ S. pneumoniae مع Ceftriaxone/Cefotaxime = I "
                "(MIC 1 µg/mL): لا يكفي منفرداً — أضف Vancomycin (IDSA Bacterial "
                "Meningitis)."), "organism_caution")


def rule_staph_fluoroquinolone(cx, dg, out):
    """S. aureus in blood / CSF: no fluoroquinolone monotherapy."""
    # ── S. aureus bacteraemia / CNS: no fluoroquinolone monotherapy ──────
    if (cx.is_staph_r2 and "fluoroquinolone" in dg.cls and dg.result in ("S", "I")
            and cx.spec_cat in ("blood", "csf")):
        out.note(dg.name, "warn", (
            "Staphylococcus في الدم/CSF: الفلوروكينولون منفرداً غير موصى به (مقاومة تظهر "
            "أثناء العلاج) — الخيار: Cefazolin أو Oxacillin (MSSA) / Vancomycin أو "
            "Daptomycin (MRSA)."), "organism_caution")
