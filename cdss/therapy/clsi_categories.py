# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""What a culture result of I or SDD means, read by CLSI M100 Ed36.

Decision D1 (2026-11-14, Dr. Hussein Ali): the program reads every result by
CLSI M100 Ed36. Until v6.8 an I was read by the EUCAST definition
("susceptible, increased exposure": works at a higher dose, wherever it is).
CLSI's Intermediate is narrower:

    "The intermediate category implies clinical efficacy in body sites where
     the drugs are physiologically concentrated (eg, quinolones and beta-lactams
     in urine) or when a higher than normal dosage of a drug can be used
     (eg, beta-lactams). This category also includes a buffer zone."
                                                     -- CLSI M100, Instructions

So what an I is worth depends on the class and on the site, and
intermediate_note() says it for each case. The engine's verdict does not
change: an I (or SDD) agent is never "allowed" as it stands -- it is a caution,
ranked after every S -- only the explanation does.

Decision D4 (same date): SDD -- susceptible-dose dependent -- is entered and
shown as its own category (no MIC entry). CLSI M100 Ed36 defines it for

    cefepime and piperacillin-tazobactam   Enterobacterales
    ceftaroline                            Staphylococcus aureus
    daptomycin                             Enterococcus faecium

and the SDD breakpoint is valid only at the higher-exposure regimen it was set
for (CLSI M100 Appendix E; FDA STIC rationale for piperacillin-tazobactam). The
engine still sees an SDD as I; the SDD fact rides beside it (cx.sdd) and the
note names that regimen.
"""
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

# Every spelling a report prints for the category. Upper-case, as compared.
SDD_TOKENS = frozenset({"SDD", "SUSCEPTIBLE-DOSE DEPENDENT", "SUSCEPTIBLE DOSE DEPENDENT",
                        "SUSCEPTIBLE - DOSE DEPENDENT"})


def is_sdd(value: Any) -> bool:
    """True if a raw panel value is the CLSI SDD category."""
    return str(value or "").strip().upper().replace("_", " ") in SDD_TOKENS


def sdd_drugs(panel: Optional[Mapping[str, Any]], organism: str = "") -> Set[str]:
    """The drugs the LABORATORY wrote as SDD (names trimmed, like the engine trims them).

    SDD is a result the laboratory reports, never one entered in the app: the
    entry form offers S / I / R only (v7.7), and a laboratory SDD read by the
    OCR is shown as a note under the drug. An "I" is never read as SDD (since
    v7.1): on a pair CLSI defines as S / SDD / R it may be SDD or R by the
    breakpoint version, so it stays I with the "obtain the MIC" note
    (intermediate_note) and the QC flag (phenotype_plausibility PL3).
    `organism` is accepted for older callers and ignored.
    """
    del organism
    return {str(d or "").strip() for d, v in (panel or {}).items()
            if is_sdd(v) and str(d or "").strip()}


def canonical_panel(panel: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """The panel with SDD written as I -- what every S/I/R consumer expects.

    Other values pass through untouched (the consumers normalise them as they
    always have); only the category those consumers have never seen is mapped.
    """
    return {d: ("I" if is_sdd(v) else v) for d, v in (panel or {}).items()}


# ── SDD: the regimen each CLSI SDD breakpoint was set for ──────────────────
# (organism keys, Arabic, English). organism keys are lower-case substrings.
_ENTEROBACTERALES = ("escherichia", "e. coli", "e.coli", "klebsiella", "enterobacter",
                     "citrobacter", "serratia", "proteus", "morganella", "providencia",
                     "salmonella", "shigella", "hafnia", "raoultella", "pantoea",
                     "enterobacterales")
SDD_REGIMENS: Dict[str, Tuple[Tuple[str, ...], str, str]] = {
    "Cefepime": (
        _ENTEROBACTERALES,
        "2 g IV q8h (إذا MIC 8)، أو 1 g q8h / 2 g q12h (إذا MIC 4) — مع ضبط الجرعة على CrCl",
        "2 g IV q8h (MIC 8), or 1 g q8h / 2 g q12h (MIC 4) -- adjusted to CrCl"),
    "Piperacillin + Tazobactam": (
        _ENTEROBACTERALES,
        "4.5 g IV q6h بتسريب 3 ساعات، أو 4.5 g q8h بتسريب 4 ساعات (تسريب ممتد)",
        "4.5 g IV q6h over 3 h, or 4.5 g q8h over 4 h (extended infusion)"),
    "Ceftaroline": (
        ("staphylococcus aureus", "mrsa", "mssa"),
        "600 mg IV q8h بتسريب ساعتين",
        "600 mg IV q8h over 2 h"),
    # v7.7 (external review of v7.6): "vre" removed. VRE is not always
    # E. faecium (E. faecalis too -- organism_profile says so); the SDD category
    # is E. faecium's alone, and NO_I_PAIRS (PL3) never had "vre": the two lists
    # disagreed. PL3 now reads THIS table, so they cannot disagree again.
    "Daptomycin": (
        ("enterococcus faecium", "e. faecium"),
        "8–12 mg/kg IV q24h — باستشارة الأمراض المعدية، ويُفضَّل في توليفة",
        "8-12 mg/kg IV q24h -- with ID consultation, preferably in combination"),
}


def sdd_defined(drug: str, organism: str) -> bool:
    """True when CLSI M100 Ed36 defines an SDD category for this drug + organism.

    v7.6 (owner's question "SDD is not on my culture report -- what is it?" and
    the instruction to follow the guidelines where there is a choice): SDD exists
    only for cefepime and piperacillin-tazobactam in Enterobacterales,
    ceftaroline in S. aureus and daptomycin in E. faecium (CLSI M100 Ed36 Table
    2 dosages; IDSA AMR Guidance 2026 Table 2). The entry form offers it only
    there (decision D4 revised).
    """
    reg = SDD_REGIMENS.get(str(drug or "").strip())
    org = str(organism or "").lower()
    return bool(reg and org and any(k in org for k in reg[0]))


def sir_options_for(drug: str = "", organism: str = "", current: Any = None) -> List[str]:
    """The categories an AST entry form offers: S / I / R, for every drug.

    v7.7 (owner's decision after the external review of v7.6, D4 revised
    again): SDD is not an entry choice anywhere. A laboratory SDD is kept from
    the report itself (the OCR reads it) and shown as a NOTE under the drug,
    as I and dose-adjustment notes are; the arguments are kept for callers.
    """
    del drug, organism, current
    return ["S", "I", "R"]


def panel_display(drug: str, organism: str, value: Any,
                  lab_value: Any = None) -> Tuple[str, str, str]:
    """How the entry form shows one result: (choice, note level, Arabic note).

    choice      -- "S" / "I" / "R", or "--" when the operator must choose
    note level  -- "" | "info" | "warning" | "error"

      * the laboratory wrote SDD on a pair CLSI defines it for -> I, with the
        SDD note and its regimen (the engine keeps the SDD);
      * the laboratory wrote SDD where CLSI defines none -> "--" until the
        operator chooses S / I / R (read as I meanwhile, reports blocked: V14);
      * an I on a pair CLSI defines as S / SDD / R (no I) -> I, with "SDD or
        R -- obtain the MIC". It is never turned into SDD.
    """
    lab_sdd = is_sdd(lab_value) or is_sdd(value)
    if is_sdd(value):
        if sdd_defined(drug, organism):
            reg = SDD_REGIMENS[drug]
            return ("I", "info",
                    f"🟠 تقرير المعمل: **SDD** — حسّاس بشرط نظام تعرّض أعلى: {reg[1]}. "
                    "التقرير هيكتب SDD والجرعة دي.")
        return ("--", "error",
                f"🛑 تقرير المعمل كاتب SDD لـ {drug}، و CLSI M100 Ed36 ما بيعرّفش SDD هنا. "
                "اختار S أو I أو R حسب الـ MIC — لحد ما تختار بيتحسب I والتقارير موقوفة.")
    v = str(value or "").strip().upper()
    if v == "I" and not lab_sdd:
        from cdss.astqc.phenotype_plausibility import no_i_pair
        if no_i_pair(drug, organism):
            return ("I", "warning",
                    f"⚠️ CLSI M100 Ed36 مالوش فئة I لـ {drug} مع الكائن ده: ممكن تكون SDD أو R حسب "
                    "نسخة الـ breakpoints. اطلب الـ MIC — البرنامج مش بيحوّلها SDD.")
    return (v if v in ("S", "I", "R") else "--", "", "")


def _is_beta_lactam(name: str, cls: str) -> bool:
    c, n = (cls or "").lower(), (name or "").lower()
    return (any(k in c for k in ("penicillin", "cephalosporin", "cephamycin", "carbapenem",
                                 "monobactam", "beta-lactam", "penem"))
            or any(k in n for k in ("cillin", "cef", "ceph", "penem", "aztreonam")))


def intermediate_note(name: str, cls: str, spec_cat: str, uti_upper: bool,
                      sdd: bool = False, organism: str = "") -> Tuple[str, str]:
    """(Arabic, English) explanation of an I or SDD result for this drug at this site."""
    org = (organism or "").lower()
    if sdd:
        reg = SDD_REGIMENS.get(name)
        if reg and any(k in org for k in reg[0]):
            return (
                "CLSI M100: النتيجة SDD (Susceptible-dose dependent) — حسّاس فقط بنظام تعرّض "
                f"أعلى من الجرعة المعتادة: {reg[1]}. بالجرعة المعتادة يُعامَل كغير حسّاس.",
                "CLSI M100: Susceptible-dose dependent (SDD) -- susceptible only at a "
                f"higher-exposure regimen than the standard dose: {reg[2]}. At the standard "
                "dose treat it as not susceptible.")
        return (
            "النتيجة مكتوبة SDD، لكن CLSI M100 Ed36 يعرّف SDD فقط لـ Cefepime و Pip-Tazo "
            "(Enterobacterales) و Ceftaroline (S. aureus) و Daptomycin (E. faecium) — راجِع "
            "القراءة. حتى ذلك تُعامل كـ I: لا تُستخدم إلا بالجرعة القصوى وإن لم يوجد دواء S.",
            "The result is written SDD, but CLSI M100 Ed36 defines SDD only for cefepime and "
            "piperacillin-tazobactam (Enterobacterales), ceftaroline (S. aureus) and daptomycin "
            "(E. faecium) -- check the reading. Until then it is treated as I: use only at the "
            "maximum dose and only if no S agent fits.")
    urine_lower = spec_cat == "urine" and not uti_upper
    fq = "fluoroquinolone" in (cls or "").lower()
    if org:
        from cdss.astqc.phenotype_plausibility import no_i_pair
        if no_i_pair(name, organism):
            # v7.1: CLSI M100 Ed36 has no I for this pair (S / SDD / R).
            return (
                f"CLSI M100 Ed36 لا يعرّف فئة I لـ {name} مع هذا الكائن (S / SDD / R فقط): الـ I "
                "المطبوع جاء من إصدار breakpoints آخر — بمعايير CLSI الحالية قد يكون SDD أو R. "
                "اطلب قيمة الـ MIC: جرعة SDD فقط إذا وقع الـ MIC في مدى SDD، وإلا عامله كـ R. "
                "لا يُستخدم بالجرعة المعتادة.",
                f"CLSI M100 Ed36 has no I category for {name} with this organism (S / SDD / R "
                "only): the printed I comes from another breakpoint version - by current CLSI it "
                "may be SDD or R. Obtain the MIC: SDD dosing only if the MIC falls in the SDD "
                "range, otherwise treat it as R. Not at the standard dose.")
    # v7.9 (external case review): ertapenem I in a Klebsiella got the generic
    # beta-lactam text ("efficacy possible at a higher dose") and nothing about
    # the work-up the QA sheet called critical. A carbapenem I in
    # Enterobacterales is carbapenem NON-SUSCEPTIBILITY: it triggers a
    # carbapenemase test and a meropenem MIC, and it is not, by itself, a
    # carbapenemase.
    if "carbapenem" in (cls or "").lower() or name in ("Ertapenem", "Meropenem",
                                                         "Imipenem/Cilastatin"):
        from cdss.astqc.phenotype_plausibility import _is_entero
        if _is_entero(org):
            _etp_ar = (" معايير Ertapenem مبنية على 1 جم مرة يومياً ولا يوجد نظام جرعة أعلى معتمد له."
                       if name == "Ertapenem" else "")
            _etp_en = (" The ertapenem breakpoints assume 1 g once daily; there is no approved "
                       "higher-dose ertapenem regimen." if name == "Ertapenem" else "")
            return (
                "CLSI M100: النتيجة Intermediate (I) لكاربابينيم في Enterobacterales = عدم حساسية "
                "للكاربابينيم. ليست دليلاً على كاربابينيميز (ESBL / AmpC مع فقد البورين يعطيان نفس "
                "النتيجة)، لكنها تستلزم اختبار كاربابينيميز (mCIM، والـ eCIM يُقرأ لو mCIM موجب) و MIC "
                "للـ Meropenem قبل الاعتماد على أي كاربابينيم." + _etp_ar + " لا تعتمد على هذا الدواء "
                "حتى تظهر النتيجتان، والأفضل دواء S.",
                "CLSI M100: Intermediate (I) for a carbapenem in Enterobacterales = carbapenem "
                "non-susceptibility. Not proof of a carbapenemase (ESBL / AmpC with porin loss gives "
                "the same result), but a carbapenemase test (mCIM; eCIM read if the mCIM is "
                "positive) and a meropenem MIC are required before any carbapenem is relied on."
                + _etp_en + " Do not rely on this agent until both are back; prefer an S agent.")
    if _is_beta_lactam(name, cls):
        if urine_lower:
            return (
                "CLSI M100: النتيجة Intermediate (I) — فعّال حيث يتركّز الدواء فسيولوجياً "
                "(البيتا-لاكتام في البول): مقبول لالتهاب المثانة إن لم يناسب دواء S. في "
                "الـ pyelonephritis أو أي عدوى غازية: بالجرعة القصوى المعتمدة فقط، والأفضل دواء S.",
                "CLSI M100: Intermediate (I) -- efficacy is expected where the drug is "
                "physiologically concentrated (beta-lactams in urine): acceptable for cystitis "
                "if no S agent fits. For pyelonephritis or any invasive infection use it only "
                "at the maximum approved dose, and prefer an S agent.")
        return (
            "CLSI M100: النتيجة Intermediate (I) — في البيتا-لاكتام الفاعلية ممكنة فقط بجرعة "
            "أعلى من المعتادة، وفقط حيث يوجد نظام جرعة عالية معتمد لهذا الدواء (ليست رخصة "
            "عامة لكل بيتا-لاكتام): راجِع الـ MIC مقابل الـ breakpoint والنظام المعتمد. الأفضل "
            "دواء S، ولا يُستخدم الـ I إلا إن لم يوجد بديل.",
            "CLSI M100: Intermediate (I) -- for a beta-lactam, efficacy is possible only at a "
            "higher-than-normal dose, and only where an approved high-dose regimen exists for "
            "THIS drug (not a general licence for every beta-lactam): check the MIC against the "
            "breakpoint and the approved regimen. Prefer an S agent; use the I agent only if "
            "none fits.")
    if fq and urine_lower:
        return (
            "CLSI M100: النتيجة Intermediate (I) — الفلوروكينولون يتركّز في البول: مقبول "
            "لالتهاب المثانة إن لم يناسب دواء S، وليس للـ pyelonephritis أو الدم أو أي موقع آخر.",
            "CLSI M100: Intermediate (I) -- fluoroquinolones are concentrated in urine: "
            "acceptable for cystitis if no S agent fits; not for pyelonephritis, bacteraemia "
            "or any other site.")
    return (
        "CLSI M100: النتيجة Intermediate (I) — فاعلية غير مؤكدة (منطقة فاصلة بين S و R). "
        "اختر دواءً S؛ ولا يُستخدم الـ I إلا إن لم يوجد بديل، وبالتشاور مع الأمراض المعدية / "
        "الصيدلة الإكلينيكية.",
        "CLSI M100: Intermediate (I) -- uncertain efficacy (a buffer zone between S and R). "
        "Choose an S agent; use the I agent only if none exists, with ID / clinical-pharmacy "
        "input.")


def intermediate_fields(name: str, info: Mapping[str, Any], spec_cat: str, uti_upper: bool,
                        sdd: Iterable[str], organism: str) -> Dict[str, Any]:
    """The fields an I / SDD item carries: culture_sdd and the note in both languages."""
    is_s = name in set(sdd or ())
    ar, en = intermediate_note(name, str((info or {}).get("class", "")), spec_cat, uti_upper,
                               is_s, organism)
    return {"culture_sdd": is_s, "intermediate_note": ar, "intermediate_note_en": en}


def result_label(name: str, result: Any, sdd: Iterable[str] = ()) -> str:
    """The result as a report prints it: SDD for an SDD agent, otherwise as given."""
    if result == "I" and name in set(sdd or ()):
        return "SDD"
    return "" if result is None else str(result)
