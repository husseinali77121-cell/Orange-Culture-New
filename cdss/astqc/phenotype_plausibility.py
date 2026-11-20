# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Phenotype-plausibility rules: patterns that are not impossible, but that no
single resistance mechanism explains, and the reflex tests they call for.

Added v7.0 (2026-11-19) after an external review of a catheter-associated UTI
(Klebsiella spp.: cephalosporins R/I, aztreonam S, piperacillin-tazobactam S,
ertapenem I, cefepime "I", ofloxacin S with norfloxacin I). Every existing QC
engine reported "Errors: 0" -- each result was possible on its own; it was the
COMBINATION that needed a second look, and the panel lacked the tests that
would settle it (meropenem, a carbapenemase test, ciprofloxacin/levofloxacin).

What a rule returns (`check_plausibility`):
    id, severity ("error" | "warning" | "info"), drugs, title/detail/action
    in Arabic and English, reference, and `reflex`: agents or tests to add.
`reflex_tests` gives only the agents, for the panel-completeness check, which
promotes an untested reflex agent to "critical missing".

Rules (Enterobacterales unless stated):
  PL1  ESBL-type cephalosporin resistance with aztreonam S AND
       piperacillin-tazobactam S and a non-susceptible carbapenem: no single
       mechanism fits (an ESBL hydrolyses aztreonam; an MBL spares aztreonam
       but not piperacillin-tazobactam; OXA-48 does not explain the
       cephalosporins). Verify the identification and the AST; confirm by MIC.
  PL2  Ertapenem I or R: carbapenemase test (mCIM / eCIM -- CLSI M100 Ed36
       Tables 3B / 3C) and meropenem (or imipenem) MIC. An untested
       meropenem becomes critical missing.
  PL3  A CLSI "no-I" pair reported I: cefepime and piperacillin-tazobactam in
       Enterobacterales, ceftaroline in S. aureus, daptomycin in E. faecium.
       CLSI M100 Ed36 has SDD there, not I. The I may be SDD or R by the
       breakpoint version: obtain the MIC. The program never converts it.
  PL4  Fluoroquinolone discordance: ofloxacin or norfloxacin S while another
       quinolone is I/R (or ciprofloxacin/levofloxacin I/R while ofloxacin
       is S). CLSI revised the ciprofloxacin/levofloxacin breakpoints for
       Enterobacterales in 2019 (M100-Ed29); ofloxacin and norfloxacin were
       not revised and can read S over a first-step QRDR mutation. Test
       ciprofloxacin/levofloxacin before relying on any quinolone.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

_ENTERO = ("escherichia", "e. coli", "e.coli", "klebsiella", "enterobacter", "citrobacter",
           "serratia", "proteus", "morganella", "providencia", "salmonella", "shigella",
           "hafnia", "raoultella", "pantoea", "enterobacterales")

_3GC = ("Ceftriaxone", "Cefotaxime", "Ceftazidime")
_CARBA_TESTS = ("Meropenem", "Imipenem/Cilastatin")
_FQ_OLD = ("Ofloxacin", "Norfloxacin")
_FQ_NEW = ("Ciprofloxacin", "Levofloxacin")

# CLSI M100 Ed36 pairs that have SDD and no I. v7.7 (external review of v7.6):
# read from the SDD table itself -- the two copies disagreed on "VRE".
from cdss.therapy.clsi_categories import SDD_REGIMENS as _SDD_REGIMENS  # noqa: E402
NO_I_PAIRS: Dict[str, tuple] = {drug: reg[0] for drug, reg in _SDD_REGIMENS.items()}

_REF_CARBA = "CLSI M100 Ed36 Tables 3B / 3C (mCIM / eCIM) · IDSA AMR Guidance 2026"


def _v(sir: Dict[str, Any], drug: str) -> str:
    return str((sir or {}).get(drug, "") or "").strip().upper()


def _ns(sir, drug) -> bool:
    return _v(sir, drug) in ("I", "R", "SDD")


def _is_entero(org_l: str) -> bool:
    return any(t in org_l for t in _ENTERO)


def no_i_pair(name: str, organism: str) -> bool:
    """True when CLSI M100 Ed36 has SDD, not I, for this drug-organism pair."""
    toks = NO_I_PAIRS.get(name)
    o = (organism or "").lower()
    return bool(toks) and any(t in o for t in toks)


def check_plausibility(organism: str, sir_map: Dict[str, Any],
                       sdd: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """Plausibility findings for this panel (see the module docstring).

    `sdd` -- the drugs the laboratory reported as SDD. Needed to tell a real I
    from an SDD that an upstream step already folded into I; when it is None
    every I on a no-I pair is treated as reported I.
    """
    org_l = (organism or "").lower()
    sir = dict(sir_map or {})
    sdd_set: Set[str] = set(sdd or ())
    out: List[Dict[str, Any]] = []
    if not sir or not org_l:
        return out
    entero = _is_entero(org_l)

    # ── PL3: CLSI pairs without an I category ──────────────────────────────
    for name in NO_I_PAIRS:
        if _v(sir, name) == "I" and name not in sdd_set and no_i_pair(name, organism):
            out.append({
                "id": f"PL3:{name}", "severity": "warning", "drugs": [name],
                # v7.7 (external review of v7.6): this text still said "the
                # program reads it as SDD" -- untrue since v7.1, and it invited
                # correcting the report to SDD without an MIC.
                "title_en": f"{name} reported I -- CLSI M100 Ed36 has no I here (SDD or R)",
                "title_ar": f"{name} مُبلَّغ I — CLSI M100 Ed36 مالوش I هنا (SDD أو R)",
                "detail_en": ("CLSI M100 Ed36 does not define an Intermediate (I) category for "
                              "this organism-drug combination. The reported I may correspond to "
                              "SDD or R depending on the breakpoint version. Obtain the MIC and "
                              "verify the breakpoint edition. Do not automatically convert I to "
                              "SDD."),
                "detail_ar": ("لا يعرّف CLSI M100 Ed36 فئة Intermediate (I) لهذا المضاد مع هذا "
                              "الكائن. قد تمثل النتيجة SDD أو R طبقاً لإصدار معايير الحساسية "
                              "المستخدم. يجب مراجعة الـ MIC وإصدار الـ Breakpoints، ولا يجوز "
                              "تحويل I تلقائياً إلى SDD."),
                "action_en": ("Obtain the MIC and the breakpoint edition; report SDD only if the "
                              "MIC falls in the CLSI SDD range, otherwise R."),
                "action_ar": ("اطلب الـ MIC وإصدار الـ breakpoints؛ SDD فقط لو الـ MIC في مدى SDD "
                              "عند CLSI، وإلا R."),
                "reference": "CLSI M100 Ed36 (SDD: Tables 2A / 2C / 2D)",
                "reflex": [],
            })

    if entero:
        ceph_ns = [d for d in _3GC if _ns(sir, d)]
        etp = _v(sir, "Ertapenem")
        atm_s = _v(sir, "Aztreonam") == "S"
        tzp_s = _v(sir, "Piperacillin + Tazobactam") == "S"
        carba_untested = [d for d in _CARBA_TESTS if d not in sir]

        # ── PL1: no single mechanism fits ──────────────────────────────────
        # BOTH aztreonam and pip-tazo S: aztreonam S alone with a non-susceptible
        # carbapenem is the textbook metallo-beta-lactamase (PL2 handles it), and
        # pip-tazo S alone fits ESBL + porin loss.
        if len(ceph_ns) >= 2 and atm_s and tzp_s and etp in ("I", "R"):
            _spared = [d for d, ok in (("Aztreonam", atm_s),
                                       ("Piperacillin + Tazobactam", tzp_s)) if ok]
            out.append({
                "id": "PL1:mixed_betalactam_phenotype", "severity": "error",
                "short": "implausible beta-lactam phenotype",
                "drugs": ceph_ns + _spared + ["Ertapenem"],
                "title_en": ("Implausible beta-lactam phenotype -- verify the identification and "
                             "the AST, confirm by MIC"),
                "title_ar": "نمط بيتا-لاكتام غير منطقي — راجِع التعريف والحساسية وأكّد بـ MIC",
                "detail_en": (f"{', '.join(ceph_ns)} non-susceptible with {', '.join(_spared)} S "
                              f"and ertapenem {etp}. No single mechanism explains it: an ESBL "
                              "hydrolyses aztreonam; a metallo-beta-lactamase spares aztreonam "
                              "but not piperacillin-tazobactam; OXA-48 does not explain the "
                              "cephalosporins; porin loss + ESBL/AmpC would not leave aztreonam "
                              "S. A mixed culture, a disk / reading error or two mechanisms "
                              "together are more likely."),
                "detail_ar": (f"{', '.join(ceph_ns)} غير حسّاسة مع {', '.join(_spared)} = S و "
                              f"Ertapenem = {etp}. لا توجد آلية واحدة تفسّر ذلك: الـ ESBL يحلّل "
                              "Aztreonam، والـ MBL يترك Aztreonam لكن لا يترك Pip-Tazo، و OXA-48 لا "
                              "يفسّر السيفالوسبورينات، وفقد البورين + ESBL/AmpC لا يترك Aztreonam "
                              "حساساً. الأرجح مزرعة مختلطة أو خطأ قرص/قراءة أو آليتان معاً."),
                "action_en": ("Check purity (subculture), repeat the AST, and confirm aztreonam, "
                              "piperacillin-tazobactam and the carbapenems by MIC before release."),
                "action_ar": ("تأكّد من نقاء المزرعة (subculture) وأعِد الحساسية، وأكّد Aztreonam و "
                              "Pip-Tazo والكاربابينيمات بـ MIC قبل إصدار التقرير."),
                "reference": "CLSI M100 Ed36 Appendix A · EUCAST Expert Rules (unusual phenotypes)",
                "reflex": ["MIC: Aztreonam", "MIC: Piperacillin + Tazobactam"] + carba_untested[:1],
            })

        # ── PL2: ertapenem non-susceptible ─────────────────────────────────
        if etp in ("I", "R"):
            out.append({
                "id": "PL2:ertapenem_ns", "severity": "error" if carba_untested else "warning",
                "short": f"ertapenem {etp}",
                "drugs": ["Ertapenem"] + [d for d in _CARBA_TESTS if d in sir],
                "title_en": (f"Ertapenem {etp} -- carbapenemase test (mCIM / eCIM) and a "
                             "meropenem MIC are required"),
                "title_ar": f"Ertapenem = {etp} — يلزم اختبار كاربابينيميز (mCIM / eCIM) و MIC للـ Meropenem",
                "detail_en": ("A non-susceptible carbapenem in Enterobacterales is a carbapenemase "
                              "until proven otherwise (CLSI M100 Ed36 Tables 3B / 3C). Ertapenem "
                              "is the most sensitive indicator; meropenem decides whether a "
                              "carbapenem is still an option and which novel agent fits (IDSA "
                              "2026)." + (" Meropenem / imipenem were NOT tested." if carba_untested
                                          else "")),
                "detail_ar": ("كاربابينيم غير حساس في Enterobacterales = كاربابينيميز حتى يثبت العكس "
                              "(CLSI M100 Ed36 Tables 3B / 3C). Ertapenem أكثرها حساسية للكشف، "
                              "و Meropenem يحدد إن كان الكاربابينيم لا يزال خياراً وأي دواء حديث يناسب "
                              "(IDSA 2026)." + (" Meropenem / Imipenem لم يُختبرا." if carba_untested
                                                else "")),
                "action_en": ("Run mCIM (+ eCIM) or a rapid carbapenemase test and add a meropenem MIC."
                              + (" Aztreonam S with a non-susceptible carbapenem is the metallo-"
                                 "beta-lactamase pattern: an eCIM matters here."
                                 if atm_s and not tzp_s else "")),
                "action_ar": "اعمل mCIM (+ eCIM) أو اختبار كاربابينيميز سريع، وأضف MIC للـ Meropenem.",
                "reference": _REF_CARBA,
                "reflex": (["Meropenem"] if "Meropenem" not in sir else [])
                          + ["Carbapenemase test (mCIM / eCIM)"],
            })

    # ── PL4: fluoroquinolone discordance (any Gram-negative) ───────────────
    old_s = [d for d in _FQ_OLD if _v(sir, d) == "S"]
    any_ns = [d for d in _FQ_OLD + _FQ_NEW if _v(sir, d) in ("I", "R")]
    if old_s and any_ns:
        new_untested = [d for d in _FQ_NEW if d not in sir]
        out.append({
            "id": "PL4:fq_discordance", "severity": "warning",
            "short": "quinolone discordance",
            "drugs": old_s + any_ns,
            "title_en": (f"{', '.join(old_s)} S with {', '.join(any_ns)} non-susceptible -- "
                         "low-level fluoroquinolone resistance"),
            "title_ar": (f"{', '.join(old_s)} = S مع {', '.join(any_ns)} غير حساس — مقاومة "
                         "فلوروكينولون منخفضة المستوى"),
            "detail_en": ("A split quinolone result points to a first-step QRDR (gyrA) mutation. "
                          "CLSI revised the ciprofloxacin / levofloxacin breakpoints for "
                          "Enterobacterales in 2019 (M100-Ed29); the ofloxacin and norfloxacin "
                          "criteria were not revised and can still read S over that mutation, "
                          "so an ofloxacin S here does not predict clinical success."),
            "detail_ar": ("الاختلاف بين الكينولونات يشير لطفرة أولى في QRDR (gyrA). CLSI عدّل "
                          "breakpoints الـ Ciprofloxacin / Levofloxacin للـ Enterobacterales في 2019 "
                          "(M100-Ed29)، ولم تُعدَّل معايير Ofloxacin و Norfloxacin، فقد تُقرأ S رغم "
                          "الطفرة — Ofloxacin S هنا لا يضمن النجاح العلاجي."),
            "action_en": ("Test ciprofloxacin and levofloxacin (MIC) before relying on any "
                          "fluoroquinolone."),
            "action_ar": "اختبر Ciprofloxacin و Levofloxacin (MIC) قبل الاعتماد على أي فلوروكينولون.",
            "reference": "CLSI M100 Ed36 Table 2A (fluoroquinolones; Ed29 revision)",
            "reflex": new_untested,
        })
    return out


def fq_discordant(sir_map: Dict[str, Any]) -> bool:
    """PL4 condition alone, for the treatment engine."""
    sir = sir_map or {}
    return (any(_v(sir, d) == "S" for d in _FQ_OLD)
            and any(_v(sir, d) in ("I", "R") for d in _FQ_OLD + _FQ_NEW))


def reflex_tests(organism: str, sir_map: Dict[str, Any],
                 sdd: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """{agent: why} for every untested AGENT a plausibility rule calls for."""
    out: Dict[str, str] = {}
    for f in check_plausibility(organism, sir_map, sdd):
        for r in f.get("reflex") or []:
            if r in (sir_map or {}) or r.startswith("MIC:") or " test" in r:
                continue
            out.setdefault(r, f.get("short") or f["title_en"])
    return out


def format_finding(f: Dict[str, Any], lang: str = "ar") -> Dict[str, str]:
    """message / fix / reference in one language, like ast_reportability.format_issue."""
    ar = (lang or "ar").lower().startswith("ar")
    k = "ar" if ar else "en"
    reflex = [r for r in (f.get("reflex") or [])]
    extra = (("\nأضِف: " if ar else "\nAdd: ") + ", ".join(reflex)) if reflex else ""
    return {
        "message": f"⚠️ **{f.get('title_' + k, '')}** — {f.get('detail_' + k, '')}",
        "fix": f"✏️ {f.get('action_' + k, '')}{extra}",
        "reference": f"📖 {f.get('reference', '')}",
    }


__all__ = ["check_plausibility", "reflex_tests", "fq_discordant", "no_i_pair",
           "format_finding", "NO_I_PAIRS"]
