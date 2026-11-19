# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""The five agents IDSA AMR Guidance 2026 added to the ESBL / AmpC / CRE algorithms.

Added v6.9 (2026-11-14, decision D5). Pivmecillinam, sulopenem, gepotidacin,
cefepime-enmetazobactam and IV fosfomycin are judged HERE, on their own
activity, and never by the old-beta-lactam mechanism rules (which would ban
mecillinam -- an ESBL-stable penicillin that IDSA PREFERS for ESBL cystitis --
as "a penicillin against an ESBL"). This rule sets `out.skip_mech` for them,
exactly as rule_novel_agents does for the novel BL/BLIs.

What it checks, per agent:

  1. Interpretive criteria exist for THIS organism (decision D1: CLSI first).
       mecillinam               CLSI M100: E. coli (uUTI)
       sulopenem                FDA STIC: E. coli, K. pneumoniae, P. mirabilis
       gepotidacin              FDA STIC: E. coli, K. pneumoniae, C. freundii,
                                S. saprophyticus, E. faecalis
       cefepime-enmetazobactam  FDA STIC: Enterobacterales, P. aeruginosa
       IV fosfomycin            FDA STIC / EUCAST IV: E. coli
     Another Enterobacterales species: a caution ("no_breakpoint"); anything
     else: banned, the result has no interpretive criteria.
  2. The resistance mechanism, by IDSA 2026:
       carbapenemase  sulopenem / cefepime-enmetazobactam banned; pivmecillinam
                      banned for KPC (0% of 174 KPC producers S), otherwise a
                      caution ("only if KPC is unlikely"); gepotidacin a caution
                      (CRE data "extremely limited").
       AmpC only      cefepime-enmetazobactam is "preferentially reserved for
                      ESBL-E or AmpC + ESBL co-producers": a caution.
  3. The site: oral sulopenem for pyelonephritis / cUTI only as a step-down
     after clinical improvement. (Pivmecillinam and gepotidacin outside the
     bladder are removed by postprocess.apply_upper_uti and the site matrix.)
"""
from cdss.resistance.mechanism import is_esbl_producer
from cdss.therapy.intrinsic import build_banned_item

NEW_IDSA_2026_AGENTS = frozenset({
    "Pivmecillinam", "Sulopenem", "Gepotidacin", "Cefepime + Enmetazobactam", "Fosfomycin IV",
})

_E_COLI = ("e. coli", "escherichia", "e.coli")
_K_PNEUMO = ("klebsiella pneumoniae", "klebsiella spp.", "k. pneumoniae")

# agent -> (organism tokens with criteria, who sets them)
_SCOPE = {
    "Pivmecillinam": (_E_COLI, "CLSI M100 (E. coli, uUTI)"),
    "Sulopenem": (_E_COLI + _K_PNEUMO + ("proteus mirabilis",),
                  "FDA STIC (E. coli, K. pneumoniae, P. mirabilis)"),
    "Gepotidacin": (_E_COLI + _K_PNEUMO + ("citrobacter freundii", "saprophyticus",
                                           "enterococcus faecalis", "e. faecalis"),
                    "FDA STIC (E. coli, K. pneumoniae, C. freundii, S. saprophyticus, E. faecalis)"),
    "Cefepime + Enmetazobactam": ((), "FDA STIC (Enterobacterales, P. aeruginosa)"),
    "Fosfomycin IV": (_E_COLI, "FDA STIC / EUCAST IV (E. coli)"),
}


def _in_scope(name: str, org_l: str, organism: str) -> str:
    """'yes' | 'enterobacterales' (another species of the order) | 'no'."""
    tokens, _src = _SCOPE[name]
    if name == "Cefepime + Enmetazobactam":
        if is_esbl_producer(organism) or "pseudomonas aeruginosa" in org_l:
            return "yes"
        return "no"
    if any(t in org_l for t in tokens):
        return "yes"
    return "enterobacterales" if is_esbl_producer(organism) else "no"


def rule_new_agents(cx, dg, out):
    """IDSA 2026 agents: breakpoint scope, mechanism and site, judged on their own activity."""
    if dg.name not in NEW_IDSA_2026_AGENTS:
        return
    out.skip_mech = True            # never the old-beta-lactam mechanism rules
    if dg.result not in ("S", "I"):
        return
    scope = _in_scope(dg.name, cx.org_l, cx.organism)
    src = _SCOPE[dg.name][1]
    if scope == "no":
        out.ban(build_banned_item(
            dg.name, "no_breakpoint",
            f"لا توجد معايير تفسير لـ {dg.name} مع هذا الكائن.",
            f"{dg.name}: معايير التفسير المتاحة {src} فقط — النتيجة مع {cx.organism or 'هذا الكائن'} "
            "بلا معيار ولا يُبنى عليها علاج (CLSI M100 Ed36 / FDA STIC)."))
        return
    if scope == "enterobacterales":
        out.note(dg.name, "warn", (
            f"{dg.name}: معايير التفسير {src} فقط — النتيجة مع {cx.organism} غير مُعايَرة."
            + (" EUCAST يمدّ breakpoints الـ mecillinam إلى Klebsiella و Citrobacter و "
               "Enterobacter و Raoultella و P. mirabilis (uUTI)." if dg.name == "Pivmecillinam" else "")
            + (" Klebsiella تحمل fosA كروموسومياً — IDSA 2026: تقدير حذر." if dg.name == "Fosfomycin IV"
               else "")), "no_breakpoint")

    # ── mechanism (IDSA AMR Guidance 2026) ─────────────────────────────────
    carb = cx.is_carbapenemase
    if carb and dg.name in ("Sulopenem", "Cefepime + Enmetazobactam"):
        out.ban(build_banned_item(
            dg.name, "organism", "Carbapenemase — غير مُعتمد عليه.",
            f"{dg.name}: لا يُعتمد عليه أمام منتجي الكاربابينيميز (لا يُختبر عليهم، والمثبط لا "
            "يغطي KPC / OXA-48 / MBL بثقة) — IDSA AMR Guidance 2026. العلاج حسب نوع الإنزيم."))
        return
    if dg.name == "Pivmecillinam" and (carb or cx.is_possible_carb):
        if str(cx.carb_type or "").upper() == "KPC":
            out.ban(build_banned_item(
                dg.name, "organism", "KPC — mecillinam غير فعّال.",
                "IDSA 2026: mecillinam حسّاس في 0% من 174 منتج KPC — لا يُستخدم مع KPC-CRE."))
            return
        out.note(dg.name, "warn", (
            "CRE / اشتباه كاربابينيميز: IDSA 2026 تقترح Pivmecillinam كبديل لالتهاب المثانة فقط إذا "
            "كان KPC غير مرجّح (0% حساسية في منتجي KPC) — أكّد نوع الإنزيم."), "idsa_new_agent")
    if dg.name == "Gepotidacin" and (carb or cx.is_possible_carb):
        out.note(dg.name, "warn", (
            "CRE: بيانات Gepotidacin محدودة جداً — بديل فقط لالتهاب المثانة (IDSA 2026)."),
            "idsa_new_agent")
    if dg.name == "Cefepime + Enmetazobactam":
        if cx.is_possible_carb:
            out.note(dg.name, "warn", (
                "اشتباه كاربابينيميز غير مؤكد: لا يُعتمد على Cefepime-enmetazobactam قبل نفي الإنزيم "
                "(mCIM / PCR)."), "idsa_new_agent")
        elif cx.mech_prob in ("ampc", "ampc_plasmid"):
            out.note(dg.name, "warn", (
                "AmpC بدون ESBL: IDSA 2026 تحفظ Cefepime-enmetazobactam لـ ESBL-E أو AmpC + ESBL — "
                "استخدم Cefepime نفسه إذا كان S."), "idsa_new_agent")

    # ── the label's population ─────────────────────────────────────────────
    # Pivmecillinam, sulopenem and gepotidacin were licensed on trials in
    # women; the note says so for a man, without demoting the agent.
    if (dg.name in ("Pivmecillinam", "Sulopenem", "Gepotidacin")
            and str(cx.sex or "").strip().lower() in ("male", "m", "ذكر")):
        out.note(dg.name, "allow", (
            f"{dg.name}: الترخيص (FDA) لالتهاب المثانة البسيط في النساء — البيانات في الرجال "
            "محدودة؛ تأكّد أنها عدوى مثانة بسيطة وليست prostatitis أو cUTI."), "label_population")

    # ── site ───────────────────────────────────────────────────────────────
    if dg.name == "Sulopenem" and cx.spec_cat == "urine" and cx.uti_upper:
        out.note(dg.name, "warn", (
            "Sulopenem في الـ pyelonephritis / cUTI: IDSA 2026 تقترحه بديلاً **فقط كتنزيل فموي بعد "
            "التحسن الإكلينيكي**، و FDA لا يرخّصه لـ cUTI (ولا للتنزيل بعد العلاج الوريدي)."),
            "idsa_new_agent")
