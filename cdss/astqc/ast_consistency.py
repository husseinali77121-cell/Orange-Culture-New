"""Orange Lab — AST internal-consistency rules.

Answers a third question, distinct from both of its neighbours:

    ast_reportability : "should this agent be on this organism's panel?"
    ast_consistency   : "do these results contradict EACH OTHER?"   <- here
    AST_QC_RULES      : phenotype-level checks (ESBL/AmpC/carbapenemase logic)

Two kinds of contradiction, and the distinction decides the severity:

  * EQUIVALENCE — two agents so alike against this organism that they must give
    the same answer. Cefotaxime and ceftriaxone share MIC breakpoints and are
    hydrolysed near-identically by every common ESBL; one S and one R is not a
    resistance pattern, it is a laboratory error. Someone will act on whichever
    one reads S.

  * HIERARCHY — a logical impossibility. Adding a beta-lactamase inhibitor
    cannot make a drug work LESS well, so ampicillin-S with amox-clav-R is not
    a phenotype anyone has ever described.

What is deliberately NOT here matters as much as what is. Ceftazidime is a
third-generation cephalosporin, but CTX-M enzymes — the dominant ESBL family in
Egypt — hydrolyse cefotaxime far more efficiently than ceftazidime. So
cefotaxime-R with ceftazidime-S is a textbook CTX-M phenotype, NOT a
discrepancy, and flagging it would be flagging the single most common real ESBL
in the lab's population. Likewise ertapenem-R with meropenem-S is ordinary
OXA-48 or porin loss; only the REVERSE (meropenem-R, ertapenem-S) is impossible,
because ertapenem is the more labile of the two.

Separate module for the same reasons as ast_reportability: pure data plus a pure
function, testable without the clinical_data import wall, and every rule carries
the document it comes from so a microbiologist can overrule it.

Sources (verify against current editions):
  * EUCAST Clinical Breakpoint Tables v16.1 (valid 2026-01-01) — Enterobacterales
  * CLSI M100 Ed36 (2026) — Tables 2A/2B and the tetracycline-class predictive note
  * EUCAST Expert Rules and Intrinsic Resistance v3.3 (2021-10-18)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_NORM = re.compile(r"[^a-z0-9]")

ENTEROBACTERALES = [
    "escherichia", "e. coli", "e.coli", "klebsiella", "enterobacter",
    "citrobacter", "serratia", "proteus", "morganella", "providencia",
    "salmonella", "shigella", "hafnia", "pantoea", "raoultella", "yersinia",
]

# Imipenem is intrinsically less active against these, so an imipenem outlier is
# expected rather than suspicious.
_IMI_TOLERANT = ["proteus", "morganella", "providencia"]


def _nk(s: str) -> str:
    return _NORM.sub("", (s or "").lower())


def _org_in(organism: str, names: List[str]) -> bool:
    o = (organism or "").lower()
    return any(n in o for n in names)


def _find(sir_map: Dict[str, str], needle: str,
          exclude: Optional[List[str]] = None) -> Optional[str]:
    """First panel entry matching `needle`, honouring `exclude`.

    `exclude` is what stops "piperacillin" from matching
    "Piperacillin + Tazobactam" — the whole point of the hierarchy rules is that
    those two are DIFFERENT drugs, and a naive substring match collapses them
    into one and then finds no contradiction anywhere.
    """
    n = _nk(needle)
    for drug in sir_map:
        d = _nk(drug)
        if n not in d:
            continue
        if exclude and any(_nk(x) in d for x in exclude):
            continue
        return drug
    return None


def _find_tokens(sir_map: Dict[str, str], tokens: List[str]) -> Optional[str]:
    """First panel entry whose normalized name contains ALL tokens.

    Needed to name a specific inhibitor combination unambiguously: "sulbactam"
    alone matches both ampicillin-sulbactam and cefoperazone-sulbactam, so the
    ampicillin combo can only be pinned down by requiring both tokens.
    """
    toks = [_nk(t) for t in tokens]
    for drug in sir_map:
        d = _nk(drug)
        if all(t in d for t in toks):
            return drug
    return None


_INHIBITORS = ["clav", "sulbactam", "tazobactam", "avibactam", "vaborbactam",
               "relebactam"]


# ── 1. EQUIVALENCE ───────────────────────────────────────────────────────────
EQUIVALENCE_RULES: List[Dict[str, Any]] = [
    {
        # Oxacillin and cefoxitin are two readings of ONE mechanism, mecA/mecC.
        # A panel that disagrees with itself about methicillin resistance is the
        # single most consequential discrepancy a staphylococcal report can
        # carry: it decides whether every beta-lactam on the sheet is usable.
        # Nothing checked it -- the two markers were read independently and a
        # split result went out with no comment at all.
        "id": "equiv_oxa_fox",
        "organisms": ["staphylococc", "staph"],
        "a": "oxacillin", "a_exclude": [],
        "b": "cefoxitin", "b_exclude": [],
        # v7.3: not always "one disk is wrong" (mecC, BORSA); confirmation covers mecC.
        "reason_ar": ("Oxacillin و Cefoxitin مؤشّران لنفس المقاومة (mecA/mecC) واختلافهما على "
                      "نفس العزلة تعارض لازم يتحل — مش دايماً معناه إن قرص غلط: سلالات mecC "
                      "غالباً Cefoxitin-R مع Oxacillin-S، وسلالات حدّية (BORSA/MODSA) ممكن "
                      "تعمل العكس. Cefoxitin هو المؤشّر المعتمد لـ mecA في CLSI ويُقدَّم عند "
                      "التعارض."),
        "reason_en": ("Oxacillin and cefoxitin both report methicillin resistance "
                      "(mecA/mecC); a split on one isolate is a discrepancy to resolve - "
                      "not necessarily a faulty disk: mecC strains typically read "
                      "cefoxitin-R with oxacillin-S, and borderline (BORSA / MODSA) "
                      "strains can split the other way. Cefoxitin is the CLSI mecA "
                      "surrogate and takes precedence."),
        "fix_ar": ("أعِد الاختبار من مستعمرة نقية (ويُفضَّل MIC). عند استمرار التعارض: PBP2a "
                   "بكِت يكشف PBP2c/mecC (أغلب كِتات PBP2a لا تكشف mecC) أو PCR لـ mecA و mecC "
                   "معاً — PCR لـ mecA وحده لا ينفي mecC. بلِّغ البيتا-لاكتام كمقاومة حتى الحسم "
                   "حسب سياسة المعمل."),
        "fix_en": ("Repeat from a pure colony (MIC preferred). If the split persists: a PBP2a "
                   "test whose kit detects PBP2c / mecC (most PBP2a latex kits miss it), or "
                   "PCR for BOTH mecA and mecC - a mecA-only PCR does not exclude mecC. Report "
                   "beta-lactams as resistant until resolved, per laboratory policy."),
        "reference": "CLSI M100 Ed36 — cefoxitin as the mecA surrogate · EUCAST detection of resistance mechanisms v2.0 (mecC)",
        # error: the split decides every beta-lactam on the sheet and must be
        # resolved before release (borderline / mecC strains are why, not a reason
        # to report it as it stands).
        "severity": "error",
    },
    {
        "id": "equiv_ctx_cro",
        "organisms": ENTEROBACTERALES,
        "a": "cefotaxime", "a_exclude": _INHIBITORS,
        "b": "ceftriaxone", "b_exclude": _INHIBITORS,
        # v7.2: "verify" -- an MIC at the breakpoint or a zone reading can split them.
        "severity": "warning",
        "reason_ar": ("Cefotaxime و Ceftriaxone سيفالوسبورينان من الجيل الثالث "
                      "بنفس الـ breakpoints ضد الـ Enterobacterales، "
                      "والـ ESBL الشائعة تحلّلهما بكفاءة متقاربة: أن يكون أحدهما S والآخر R "
                      "على نفس العزلة غير متوقَّع — راجِع وأعِد قبل الإبلاغ (قد يكون MIC على "
                      "حافة الـ breakpoint أو قراءة zone)."),
        "reason_en": ("Cefotaxime and ceftriaxone are third-generation "
                      "cephalosporins with identical breakpoints against "
                      "Enterobacterales, and common ESBLs hydrolyse them similarly. "
                      "One S and one R on the same isolate is not expected - verify "
                      "and repeat before reporting (an MIC at the breakpoint or a "
                      "zone reading can produce it)."),
        "fix_ar": ("أعِد اختبار القرصين على نفس اللقاح، ويُفضَّل MIC. راجع: كثافة اللقاح "
                   "(0.5 McFarland) · صلاحية الأقراص وتخزينها · قياس الـ zone "
                   "(الحافة لا الظل) · نقاء المستعمرة."),
        "fix_en": ("Repeat both from the same inoculum, preferably by MIC. Check: inoculum "
                   "density (0.5 McFarland), disk potency and storage, zone edge "
                   "reading, colony purity."),
        "reference": "CLSI M100 Ed36 Table 2A (identical criteria) · EUCAST Breakpoint Tables v16.1",
    },
    {
        "id": "equiv_amc_sam",
        "organisms": ENTEROBACTERALES,
        # Two-token match so "sulbactam" does not also grab cefoperazone-sulbactam.
        "a_tokens": ["amoxicillin", "clav"],
        "b_tokens": ["ampicillin", "sulbactam"],
        # v7.2 (second external review): "verify". The English already said a
        # split is unusual rather than impossible while the Arabic called it a
        # laboratory error; sulbactam and clavulanate differ in potency and the
        # two carry different breakpoints and doses.
        "severity": "warning",
        "reason_ar": ("Amoxicillin/Clavulanate و Ampicillin/Sulbactam أمينوبنسلين مع مثبّط "
                      "بيتا-لاكتاماز من الفئة (A)، ويتصرّفان بشكل متقارب ضد الـ Enterobacterales — "
                      "لكن المثبّطين مختلفان في القوة، والـ breakpoints والجرعات مختلفة: "
                      "S مع R نتيجة غير متوقعة تحتاج مراجعة، لا خطأ معملي مؤكد."),
        "reason_en": ("Amoxicillin-clavulanate and ampicillin-sulbactam are an aminopenicillin "
                      "with a class-A beta-lactamase inhibitor and behave similarly against "
                      "Enterobacterales - but sulbactam and clavulanate differ in potency and "
                      "the two carry different breakpoints and doses, so one S and one R is "
                      "unexpected and needs verifying, not a proven laboratory error."),
        "fix_ar": ("أعِد اختبار التركيبتين من نفس اللقاح (MIC لو متاح)؛ تحقّق من صلاحية الأقراص "
                   "وقراءة الـ zone قبل الإبلاغ."),
        "fix_en": ("Repeat both combinations from the same inoculum (MIC if available); verify "
                   "disk potency and zone reading before reporting."),
        "reference": "EUCAST Expert Rules v3.1 (2016) — laboratory-consistency check (no CLSI counterpart, none contradicts it)",
    },
]


# ── 2. HIERARCHY ─────────────────────────────────────────────────────────────
# `worse` is the agent that CANNOT be less active than `better`.
HIERARCHY_RULES: List[Dict[str, Any]] = [
    {
        "id": "hier_amp_vs_amc",
        "organisms": ENTEROBACTERALES,
        "better": "ampicillin", "better_exclude": _INHIBITORS,
        "worse": "amoxicillin", "worse_needle_extra": "clav",
        # v7.3 (third review): "verify", as the signed registry row says.
        "severity": "warning",
        "reason_ar": ("Ampicillin حسّاس بينما Amoxicillin/Clavulanate مقاوم — نمط غير متوقَّع: "
                      "إضافة مثبّط بيتا-لاكتاماز لا تقلّل الفاعلية عادةً، فالأغلب خطأ قراءة أو "
                      "قرص تالف — أعِد الاختبار (MIC لو متاح) قبل الإبلاغ."),
        "reason_en": ("Ampicillin susceptible while amoxicillin-clavulanate is resistant is "
                      "unexpected: adding a beta-lactamase inhibitor does not normally reduce "
                      "activity, so a reading error or a degraded disk is likely - repeat (MIC "
                      "if available) before reporting."),
        "fix_ar": "أعِد اختبار القرصين (أو MIC). غالباً خطأ قراءة أو قرص تالف.",
        "fix_en": "Repeat both disks (or by MIC). Usually a reading error or a degraded disk.",
        "reference": "EUCAST Expert Rules v3.1 (2016) — beta-lactam hierarchy (logic; no CLSI counterpart needed)",
    },
    {
        "id": "hier_pip_vs_tzp",
        # v7.4 (review of v7.3): was [] (all). Only groups whose CLSI tables list both agents.
        "organisms": ENTEROBACTERALES + ["pseudomonas aeruginosa", "acinetobacter"],
        "better": "piperacillin", "better_exclude": _INHIBITORS,
        "worse": "piperacillin", "worse_needle_extra": "tazobactam",
        # v7.3: "verify", as the registry says (inoculum effect; different breakpoints).
        "severity": "warning",
        "reason_ar": ("Piperacillin حسّاس بينما Piperacillin/Tazobactam مقاوم — نمط غير متوقَّع "
                      "(المثبّط لا يقلّل الفاعلية عادةً). الـ breakpoints مختلفة بين الاتنين "
                      "(Pip-Tazo اتخفّض في CLSI للـ Enterobacterales)، فراجِع الـ MIC وأعِد "
                      "الاختبار قبل الإبلاغ."),
        "reason_en": ("Piperacillin susceptible while piperacillin-tazobactam is resistant is "
                      "unexpected (the inhibitor does not normally reduce activity). The two "
                      "carry different breakpoints (CLSI lowered pip-tazo for "
                      "Enterobacterales), so check the MICs and repeat before reporting."),
        "fix_ar": "أعِد اختبار القرصين وراجِع الـ MIC.",
        "fix_en": "Repeat both disks and check the MICs.",
        "reference": "EUCAST Expert Rules v3.1 (2016) — beta-lactam hierarchy (logic; no CLSI counterpart needed)",
    },
    {
        "id": "hier_mem_vs_etp",
        "organisms": ENTEROBACTERALES,
        "better": "ertapenem", "better_exclude": [],
        "worse": "meropenem", "worse_needle_extra": "",
        # v7.2 (second external review): "verify", not "error". Unusual rather
        # than impossible -- some carbapenemases (SME in Serratia, IMI / NMC-A in
        # Enterobacter) hit imipenem / meropenem harder than ertapenem.
        "severity": "warning",
        "reason_ar": ("Meropenem مقاوم بينما Ertapenem حسّاس — الاتجاه غير المعتاد. "
                      "الإرتابينيم هو الأضعف أمام آليات مقاومة الكاربابينيم، "
                      "فالمعتاد هو العكس (Ertapenem-R مع Meropenem-S = "
                      "OXA-48 أو فقد بورين). نادر لكن ممكن (مثل SME في Serratia و IMI في "
                      "Enterobacter): أكّد بـ MIC واختبار كاربابينيميز قبل الإبلاغ."),
        "reason_en": ("Meropenem resistant with ertapenem susceptible is the unusual "
                      "way round. Ertapenem is the most labile carbapenem, so the "
                      "usual pattern is the reverse (ertapenem-R with meropenem-S "
                      "= OXA-48 or porin loss). Rare but possible (e.g. SME in Serratia, "
                      "IMI in Enterobacter): confirm by MIC and a carbapenemase test "
                      "before reporting."),
        "fix_ar": "أعِد اختبار الكاربابينيمات وأكّد بـ MIC، واطلب اختبار كاربابينيميز (mCIM / CARBA-5).",
        "fix_en": "Repeat the carbapenems, confirm with an MIC method and test for a carbapenemase (mCIM / CARBA-5).",
        "reference": "CLSI M100 Ed36 Tables 3B / 3C · EUCAST Guidance on detection of resistance mechanisms",
    },
    {
        "id": "hier_tet_vs_doxy",
        # v7.3: only the groups whose CLSI tables carry the predictive note (it ran
        # for every organism); each table still needs Dr. Tarek's reading.
        "organisms": ENTEROBACTERALES + ["acinetobacter", "staphylococc", "staph",
                                         "mrsa", "mssa", "enterococc", "vre",
                                         "streptococc", "pneumococc"],
        "better": "tetracycline", "better_exclude": ["oxytetracycline"],
        "worse": "doxycycline", "worse_needle_extra": "",
        "reason_ar": ("Tetracycline حسّاس بينما Doxycycline مقاوم — يخالف قاعدة "
                      "CLSI التنبّؤية: العزلة الحسّاسة للتتراسيكلين تُعتبر حسّاسة "
                      "للدوكسيسيكلين والمينوسيكلين. (العكس مسموح: Tetracycline-R "
                      "لا يتنبّأ بمقاومة الدوكسيسيكلين — يجب اختباره منفصلاً.)"),
        "reason_en": ("Tetracycline susceptible with doxycycline resistant "
                      "contradicts the CLSI predictive rule: an isolate "
                      "susceptible to tetracycline is considered susceptible to "
                      "doxycycline and minocycline. (The reverse IS allowed — "
                      "tetracycline-R does not predict doxycycline-R, which is why "
                      "doxycycline must be tested separately.)"),
        "fix_ar": "أعِد اختبار القرصين.",
        "fix_en": "Repeat both disks.",
        "reference": "CLSI M100 Ed36 — tetracycline-class predictive note",
    },
    # ── Added v6.6 (2026-11-13, final review) — both passed silently before ──
    {
        "id": "hier_van_vs_tei_enterococcus",
        "organisms": ["enterococcus", "enterococc", "vre"],
        "better": "vancomycin", "better_exclude": [],
        "worse": "teicoplanin", "worse_needle_extra": "",
        "reason_ar": ("Vancomycin حسّاس بينما Teicoplanin مقاوم في Enterococcus — نمط غير "
                      "موجود: VanA مقاوم للاثنين، و VanB و VanC مقاومان للفانكومايسين "
                      "وحسّاسان للتيكوبلانين. العكس لا تنتجه أي آلية معروفة."),
        "reason_en": ("Vancomycin susceptible with teicoplanin resistant in an "
                      "Enterococcus matches no known mechanism: VanA is resistant to "
                      "both, VanB and VanC are vancomycin-resistant and "
                      "teicoplanin-susceptible. The reverse does not occur."),
        "fix_ar": "أعِد اختبار الجليكوببتيدات بـ MIC على مستعمرة نقية وأكّد التعريف.",
        "fix_en": "Repeat both glycopeptides by an MIC method on a pure colony and confirm the identification.",
        "reference": "Glycopeptide resistance phenotypes in enterococci (VanA / VanB / VanC; mechanism logic, read from a secondary summary) · EUCAST Breakpoint Tables v16.1 Enterococcus · CLSI M100 Ed36 Table 2D",
    },
    {
        "id": "hier_pen_vs_cro_pneumococcus",
        "organisms": ["streptococcus pneumoniae", "pneumococc"],
        "better": "penicillin", "better_exclude": ["piperacillin", "benzathine", "non-mening", "nonmening", "oral"],
        "worse": "ceftriaxone", "worse_needle_extra": "",
        # v7.3: "verify" -- non-meningitis penicillin S vs meningitis cephalosporin R.
        "severity": "warning",
        "reason_ar": ("Penicillin حسّاس بينما Ceftriaxone مقاوم في S. pneumoniae — غير متوقَّع "
                      "لو الاتنين مقروءين بنفس نوع الـ breakpoint، لكنه ممكن لو البنسلين مقروء "
                      "بمعيار غير السحايا (MIC ≤ 2) والسيفترياكسون بمعيار السحايا: راجِع الـ "
                      "MIC ونوع الـ breakpoint."),
        "reason_en": ("Penicillin susceptible with ceftriaxone resistant in S. pneumoniae is "
                      "unexpected when both are read with the same kind of breakpoint, but "
                      "possible when penicillin is read with the non-meningitis criterion "
                      "(MIC <= 2) and ceftriaxone with the meningitis one: check the MICs and "
                      "the breakpoints applied."),
        "fix_ar": ("أعِد الاختبار بـ MIC (لا يُعتمد على القرص للبيتا-لاكتام في المكورة "
                   "الرئوية) وتأكّد من نقطة القطع المستخدمة (سحايا أم غير سحايا)."),
        "fix_en": ("Repeat by MIC (disk diffusion is not used for beta-lactams in "
                   "pneumococci) and check which breakpoint was applied (meningitis or not)."),
        "reference": "CLSI M100 Ed36 Table 2G · EUCAST Clinical Breakpoint Tables v16.1 — S. pneumoniae",
    },
    {
        "id": "hier_pen_vs_ctx_pneumococcus",
        "organisms": ["streptococcus pneumoniae", "pneumococc"],
        "better": "penicillin", "better_exclude": ["piperacillin", "benzathine", "non-mening", "nonmening", "oral"],
        "worse": "cefotaxime", "worse_needle_extra": "",
        # v7.3: "verify" -- non-meningitis penicillin S vs meningitis cephalosporin R.
        "severity": "warning",
        "reason_ar": ("Penicillin حسّاس بينما Cefotaxime مقاوم في S. pneumoniae — غير متوقَّع "
                      "بنفس نوع الـ breakpoint، وممكن مع معيار غير السحايا للبنسلين ومعيار "
                      "السحايا للسيفوتاكسيم: راجِع الـ MIC ونوع الـ breakpoint."),
        "reason_en": ("Penicillin susceptible with cefotaxime resistant in S. pneumoniae is "
                      "unexpected with the same kind of breakpoint, and possible with the "
                      "non-meningitis penicillin and the meningitis cefotaxime criteria: check "
                      "the MICs and the breakpoints applied."),
        "fix_ar": "أعِد الاختبار بـ MIC وتأكّد من نقطة القطع المستخدمة.",
        "fix_en": "Repeat by MIC and check which breakpoint was applied.",
        "reference": "CLSI M100 Ed36 Table 2G · EUCAST Clinical Breakpoint Tables v16.1 — S. pneumoniae",
    },
]


# ── UNUSUAL BUT POSSIBLE (v6.6) ──────────────────────────────────────────────
# Not an impossibility, so not an `error`: a real mechanism produces it, but it
# is rare enough that the result must be confirmed before anyone acts on the S.
UNUSUAL_COMBINATIONS: List[Dict[str, Any]] = [
    {
        "id": "unusual_czav_r_carbapenem_s",
        "organisms": ENTEROBACTERALES,
        "resistant": "ceftazidime-avibactam", "resistant_tokens": ("ceftazidime", "avibactam"),
        "susceptible_any": ("meropenem", "imipenem"),
        "reason_ar": ("Ceftazidime-avibactam مقاوم مع كاربابينيم حسّاس — نادر. له سببان "
                      "حقيقيان: KPC متحوّر (مثل D179Y) بعد علاج بـ Ceftazidime-avibactam، أو "
                      "إنزيم MBL (NDM / VIM / IMP — شائع في مصر) بـ MIC كاربابينيم منخفض "
                      "يقع تحت نقطة القطع. وإلا فخطأ قراءة."),
        "reason_en": ("Ceftazidime-avibactam resistant with a carbapenem susceptible is "
                      "rare. Two real causes: a KPC variant (e.g. D179Y) selected during "
                      "ceftazidime-avibactam therapy, or a metallo-beta-lactamase (NDM / "
                      "VIM / IMP) with a low carbapenem MIC; otherwise a reading error."),
        "fix_ar": ("أكّد بـ MIC، واطلب اختبار كاربابينيميز (mCIM / NG-Test CARBA-5) — لا تعتمد "
                   "على الكاربابينيم الحسّاس قبل استبعاد MBL — واسأل عن علاج سابق بـ "
                   "Ceftazidime-avibactam."),
        "fix_en": ("Confirm by MIC and test for a carbapenemase (mCIM / NG-Test CARBA-5) "
                   "before relying on the susceptible carbapenem; ask about prior "
                   "ceftazidime-avibactam therapy."),
        "reference": "IDSA AMR Guidance 2026 — CRE; Shields et al., Antimicrob Agents Chemother 2017",
    },
]


_RANK = {"S": 0, "I": 1, "R": 2}



# ═══════════════════════════════════════════════════════════════════════
# EXCEPTIONAL PHENOTYPE RULES
# ----------------------------------------------------------------------
# The hierarchy and equivalence rules above catch results that contradict ONE
# ANOTHER. They cannot catch a result that is internally consistent but
# contradicts the world -- a vancomycin-resistant Staphylococcus aureus, a
# penicillin-resistant Streptococcus pyogenes. Nothing in the panel is
# self-contradictory, so every existing rule stayed silent and the report went
# out unchallenged.
#
# These are the phenotypes that, in a routine diagnostic laboratory, are far
# more likely to be a mixed culture, a misidentification, a contaminated disk or
# a transcription slip than a genuine finding. A true one is a notifiable public
# health event and still needs reference-laboratory confirmation before it is
# acted on -- so flagging costs nothing and missing it costs a great deal.
#
# `max_status` = the worst result that is UNREMARKABLE. Anything worse fires.
# ═══════════════════════════════════════════════════════════════════════
EXCEPTIONAL_PHENOTYPES: List[Dict[str, Any]] = [
    {
        "id": "rare_vrsa",
        "organisms": ["staphylococcus aureus", "staph aureus", "mrsa", "mssa"],
        "drug": "vancomycin", "exclude": [], "max_status": "I",
        "reason_ar": ("مقاومة الفانكومايسين في المكوّرات العنقودية الذهبية "
                      "(VRSA) وُثِّقت في حالات معدودة عالمياً منذ 2002. "
                      "الاحتمال الأرجح بفارق كبير: مزرعة مختلطة، أو خطأ تعريف، "
                      "أو قرص/شريط تالف."),
        "reason_en": ("Vancomycin resistance in S. aureus (VRSA) has been "
                      "documented in a very small number of cases worldwide "
                      "since 2002. A mixed culture, a misidentification or a "
                      "degraded disk is far more likely."),
        "fix_ar": ("أكِّد بـ MIC (broth microdilution أو gradient strip) على "
                   "مستعمرة نقية، وأعِد تعريف الكائن. لا تُصدِر النتيجة قبل "
                   "التأكيد، وأبلِغ المعمل المرجعي عند الثبوت."),
        "fix_en": ("Confirm by MIC (broth microdilution or gradient strip) on a "
                   "pure colony and re-identify. Do not release before "
                   "confirmation; notify the reference laboratory if confirmed."),
        "reference": "CLSI M100 Ed36 — S. aureus vancomycin MIC confirmation",
    },
    {
        "id": "rare_van_pneumococcus",
        "organisms": ["streptococcus pneumoniae", "pneumococc"],
        "drug": "vancomycin", "exclude": [], "max_status": "S",
        "reason_ar": ("لم تُوصَف مكوّرات رئوية مقاومة للفانكومايسين في الأدبيات. "
                      "النتيجة تشير على الأرجح إلى خطأ في التعريف — غالباً "
                      "Enterococcus أو Leuconostoc أو Lactobacillus."),
        "reason_en": ("Vancomycin-resistant S. pneumoniae has not been described. "
                      "This most likely indicates a misidentification -- "
                      "Enterococcus, Leuconostoc or Lactobacillus."),
        "fix_ar": ("أعِد تعريف الكائن (optochin، bile solubility). راجع نقاء "
                   "المستعمرة قبل إعادة الاختبار."),
        "fix_en": ("Re-identify (optochin, bile solubility) and check colony "
                   "purity before repeating."),
        "reference": "CLSI M100 Ed36 — S. pneumoniae identification",
    },
    {
        "id": "rare_pen_gas",
        "organisms": ["streptococcus pyogenes", "group a strep", "gas"],
        "drug": "penicillin", "exclude": ["combination"], "max_status": "S",
        "reason_ar": ("Streptococcus pyogenes لا يزال حسّاساً للبنسلين عالمياً — "
                      "لم تُوثَّق مقاومة سريرية. النتيجة تعني خطأ تعريف أو "
                      "خطأ قراءة."),
        "reason_en": ("S. pyogenes remains universally penicillin-susceptible; "
                      "clinical resistance has not been documented. This "
                      "indicates a misidentification or a reading error."),
        "fix_ar": ("أعِد التعريف (Lancefield grouping، bacitracin، PYR) وأعِد "
                   "قراءة القرص."),
        "fix_en": ("Re-identify (Lancefield grouping, bacitracin, PYR) and "
                   "re-read the disk.",),
        "reference": "CLSI M100 Ed36 — beta-haemolytic streptococci",
    },
    {
        "id": "rare_linezolid_gram_pos",
        "organisms": ["staphylococc", "enterococc", "streptococc", "mrsa", "vre"],
        "drug": "linezolid", "exclude": [], "max_status": "I",
        "reason_ar": ("مقاومة اللينيزوليد في الإيجابيات الجرام نادرة جداً وتستلزم "
                      "تأكيداً. تظهر عادةً بعد علاج مطوّل فقط."),
        "reason_en": ("Linezolid resistance in Gram-positives is very rare and "
                      "requires confirmation; it usually emerges only after "
                      "prolonged therapy."),
        "fix_ar": "أكِّد بـ MIC وراجع تاريخ علاج المريض باللينيزوليد.",
        "fix_en": "Confirm by MIC and review prior linezolid exposure.",
        # v7.3: this reference was a copy of the tetracycline rule's.
        "reference": "CLSI M100 Ed36 Appendix A (linezolid-resistant: confirm ID and AST) · EUCAST Breakpoint Tables v16.1 — oxazolidinones",
    },
    {
        "id": "rare_colistin_disc",
        "organisms": ["escherichia", "e. coli", "klebsiella", "enterobacter",
                      "pseudomonas", "acinetobacter"],
        # FIX 2026-11-10: max_status was "S", so the rule never fired on an
        # S -- the result a disk most often gets WRONG (false susceptibility),
        # although the text below says "invalid whatever it shows". It now
        # fires on every reported colistin result.
        "drug": "colistin", "exclude": [], "max_status": "S", "always": True,
        "reason_ar": ("نتيجة الكوليستين تستلزم broth microdilution. EUCAST و CLSI "
                      "يرفضان قياسه بالأقراص أو بالـ gradient strip — الجزيء لا ينتشر "
                      "في الآجار، فالنتيجة بالقرص غير صالحة أياً كانت (والخطأ الأشيع "
                      "حساسية كاذبة). CLSI لا يعرّف فئة S للكوليستين (I ≤ 2 / R ≥ 4)."),
        "reason_en": ("A colistin result requires broth microdilution. EUCAST and "
                      "CLSI both reject disk diffusion and gradient strips for "
                      "colistin -- the molecule does not diffuse in agar, so a disk "
                      "result is invalid whatever it shows (false susceptibility is "
                      "the common error). CLSI defines no S category (I <=2 / R >=4)."),
        "fix_ar": ("أكِّد بـ BMD. إذا كانت اللوحة تقيس الكوليستين بالقرص، "
                   "احذف النتيجة من التقرير نهائياً."),
        "fix_en": ("Confirm by BMD. If the panel measured colistin by disk, "
                   "remove the result from the report entirely."),
        "reference": "CLSI M100 Ed36 Tables 2A / 2B (colistin: BMD only) · EUCAST-CLSI Polymyxin Breakpoints Working Group (2016)",
    },
]



def _worse_than(a: Optional[str], b: Optional[str]) -> bool:
    """True when result `a` is categorically worse than result `b`."""
    if a not in _RANK or b not in _RANK:
        return False
    return _RANK[a] > _RANK[b]


def check_consistency(organism: str, sir_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Find results on this panel that contradict each other.

    Severity is set PER RULE (v7.2, second external review) and must match the
    confidence the registry row states (v7.3, third review). `error` = a split
    that decides every beta-lactam on the sheet (oxacillin / cefoxitin), the
    CLSI tetracycline predictive note, and a glycopeptide pattern no mechanism
    produces (vancomycin-S / teicoplanin-R in enterococci): not released until
    resolved. `warning` ("verify") = results expected to agree that need not
    always: cefotaxime / ceftriaxone, amoxicillin-clavulanate / ampicillin-
    sulbactam, ampicillin / amoxicillin-clavulanate, piperacillin / pip-tazo
    (different breakpoints), meropenem-R / ertapenem-S, and the pneumococcal
    penicillin / cephalosporin pairs (meningitis vs non-meningitis criteria).
    Unusual combinations are warnings; exceptional phenotypes carry no severity.
    """
    if not sir_map or not organism:
        return []
    issues: List[Dict[str, Any]] = []

    for rule in EQUIVALENCE_RULES:
        if rule["organisms"] and not _org_in(organism, rule["organisms"]):
            continue
        if "a_tokens" in rule:
            da = _find_tokens(sir_map, rule["a_tokens"])
            db = _find_tokens(sir_map, rule["b_tokens"])
        else:
            da = _find(sir_map, rule["a"], rule.get("a_exclude"))
            db = _find(sir_map, rule["b"], rule.get("b_exclude"))
        if not da or not db or da == db:
            continue
        va, vb = sir_map[da], sir_map[db]
        # S vs R only. S vs I is a one-step drift that ordinary technical
        # variation explains — flagging it would bury the real signal.
        if {va, vb} == {"S", "R"}:
            _sev = rule.get("severity", "error")
            issues.append({
                "id": f'{rule["id"]}:{da}|{db}',
                "category": "discrepancy" if _sev == "error" else "verify",
                "severity": _sev,
                "drugs": [da, db],
                "results": {da: va, db: vb},
                "reason_ar": rule["reason_ar"], "reason_en": rule["reason_en"],
                "fix_ar": rule["fix_ar"], "fix_en": rule["fix_en"],
                "reference": rule["reference"],
            })

    for rule in HIERARCHY_RULES:
        if rule["organisms"] and not _org_in(organism, rule["organisms"]):
            continue
        d_better = _find(sir_map, rule["better"], rule.get("better_exclude"))
        extra = rule.get("worse_needle_extra") or ""
        if extra:
            d_worse = next((d for d in sir_map
                            if _nk(rule["worse"]) in _nk(d) and _nk(extra) in _nk(d)),
                           None)
        else:
            d_worse = _find(sir_map, rule["worse"], _INHIBITORS)
        if not d_better or not d_worse or d_better == d_worse:
            continue
        if rule["id"] == "hier_mem_vs_etp" and _org_in(organism, _IMI_TOLERANT):
            continue
        if _worse_than(sir_map[d_worse], sir_map[d_better]) and \
                sir_map[d_better] == "S" and sir_map[d_worse] == "R":
            _sev = rule.get("severity", "error")
            issues.append({
                "id": f'{rule["id"]}:{d_better}|{d_worse}',
                "category": "discrepancy" if _sev == "error" else "verify",
                "severity": _sev,
                "drugs": [d_better, d_worse],
                "results": {d_better: sir_map[d_better], d_worse: sir_map[d_worse]},
                "reason_ar": rule["reason_ar"], "reason_en": rule["reason_en"],
                "fix_ar": rule["fix_ar"], "fix_en": rule["fix_en"],
                "reference": rule["reference"],
            })

    # ── exceptional phenotypes ────────────────────────────────────────────
    for rule in UNUSUAL_COMBINATIONS:
        if rule["organisms"] and not _org_in(organism, rule["organisms"]):
            continue
        d_r = next((d for d in sir_map
                    if all(_nk(t) in _nk(d) for t in rule["resistant_tokens"])), None)
        if not d_r or str(sir_map.get(d_r, "")).strip().upper() != "R":
            continue
        d_s = [d for d in sir_map
               if any(_nk(t) in _nk(d) for t in rule["susceptible_any"])
               and not any(_nk(x) in _nk(d) for x in ("vaborbactam", "relebactam"))
               and str(sir_map.get(d, "")).strip().upper() == "S"]
        if not d_s:
            continue
        issues.append({
            "id": f'{rule["id"]}:{d_r}|{d_s[0]}',
            "category": "unusual",
            "severity": "warning",
            "drugs": [d_r, d_s[0]],
            "results": {d_r: sir_map[d_r], d_s[0]: sir_map[d_s[0]]},
            "reason_ar": rule["reason_ar"], "reason_en": rule["reason_en"],
            "fix_ar": rule["fix_ar"], "fix_en": rule["fix_en"],
            "reference": rule["reference"],
        })

    for rule in EXCEPTIONAL_PHENOTYPES:
        if rule["organisms"] and not _org_in(organism, rule["organisms"]):
            continue
        drug = _find(sir_map, rule["drug"], rule.get("exclude"))
        if not drug:
            continue
        status = str(sir_map.get(drug, "")).strip().upper()
        if rule.get("always"):
            if status not in _RANK:
                continue
        elif _RANK.get(status, -1) <= _RANK.get(rule["max_status"], 2):
            continue
        _fix_ar = rule["fix_ar"]
        _fix_en = rule["fix_en"]
        issues.append({
            "id": f'{rule["id"]}:{drug}',
            "kind": "exceptional_phenotype",
            "drugs": [drug],
            "results": {drug: sir_map[drug]},
            "reason_ar": rule["reason_ar"], "reason_en": rule["reason_en"],
            "fix_ar": _fix_ar[0] if isinstance(_fix_ar, tuple) else _fix_ar,
            "fix_en": _fix_en[0] if isinstance(_fix_en, tuple) else _fix_en,
            "reference": rule["reference"],
        })

    return issues


def format_issue(issue: Dict[str, Any], lang: str = "ar") -> Dict[str, str]:
    """Render one discrepancy into the {message, fix} shape run_ast_qc uses."""
    drugs = " ↔ ".join(f'{d} [{issue["results"][d]}]' for d in issue["drugs"])
    if issue.get("category") == "unusual":
        head = ("⚠️ **نمط نادر — أكّد قبل الإصدار** — " if lang == "ar"
                else "⚠️ **Unusual combination — confirm before release** — ")
    elif issue.get("category") == "verify":
        head = ("🟠 **نتيجة غير متوقعة — راجِع وأكّد** — " if lang == "ar"
                else "🟠 **Unexpected result — verify and confirm** — ")
    else:
        head = ("🔴 **تناقض في اللوحة — أعِد الاختبار** — " if lang == "ar"
                else "🔴 **Panel discrepancy — repeat testing** — ")
    reason = issue["reason_ar"] if lang == "ar" else issue["reason_en"]
    fix = issue["fix_ar"] if lang == "ar" else issue["fix_en"]
    return {
        "message": f"{head}**{drugs}** — {reason}",
        "fix": f"{fix}  \n📖 {issue['reference']}",
    }


# ── 3. QC_RULE_OVERRIDES was deleted 2026-08-03: the QC006 correction (EUCAST:
# cephalosporins are reported as tested; an ESBL alone does not re-categorise)
# lives at source, in run_ast_qc()'s QC006 entry.
