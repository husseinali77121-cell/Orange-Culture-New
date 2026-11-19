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
from typing import Any, Dict, Iterable, Mapping, Optional, Set, Tuple

# Every spelling a report prints for the category. Upper-case, as compared.
SDD_TOKENS = frozenset({"SDD", "SUSCEPTIBLE-DOSE DEPENDENT", "SUSCEPTIBLE DOSE DEPENDENT",
                        "SUSCEPTIBLE - DOSE DEPENDENT"})


def is_sdd(value: Any) -> bool:
    """True if a raw panel value is the CLSI SDD category."""
    return str(value or "").strip().upper().replace("_", " ") in SDD_TOKENS


def sdd_drugs(panel: Optional[Mapping[str, Any]], organism: str = "") -> Set[str]:
    """The drugs a raw panel reports as SDD (names trimmed, like the engine trims them).

    v7.0 (review 2026-11-19): with `organism`, an "I" on a pair CLSI M100 Ed36
    defines as S / SDD / R -- cefepime or piperacillin-tazobactam in
    Enterobacterales, ceftaroline in S. aureus, daptomycin in E. faecium -- is
    the SDD range under the old label, and is read as SDD (the QC panel asks
    the laboratory to correct it: phenotype_plausibility PL3).
    """
    out = {str(d or "").strip() for d, v in (panel or {}).items()
           if is_sdd(v) and str(d or "").strip()}
    if organism:
        from cdss.astqc.phenotype_plausibility import no_i_pair
        for d, v in (panel or {}).items():
            n = str(d or "").strip()
            if (n and str(v or "").strip().upper() in ("I", "INTERMEDIATE")
                    and no_i_pair(n, organism)):
                out.add(n)
    return out


def reported_sdd(panel: Optional[Mapping[str, Any]]) -> Set[str]:
    """Only the drugs the laboratory itself wrote as SDD (for the QC check)."""
    return sdd_drugs(panel)


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
    "Daptomycin": (
        ("enterococcus faecium", "e. faecium", "vre"),
        "8–12 mg/kg IV q24h — باستشارة الأمراض المعدية، ويُفضَّل في توليفة",
        "8-12 mg/kg IV q24h -- with ID consultation, preferably in combination"),
}


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
            "أعلى من المعتادة (الجرعة القصوى المعتمدة / تسريب ممتد). الأفضل دواء S؛ ولا يُستخدم "
            "الـ I إلا إن لم يوجد بديل، وبنظام الجرعة العالية.",
            "CLSI M100: Intermediate (I) -- for a beta-lactam, efficacy is possible only at a "
            "higher-than-normal dose (maximum approved dose / extended infusion). Prefer an S "
            "agent; use the I agent only if none fits, at the high-dose regimen.")
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
