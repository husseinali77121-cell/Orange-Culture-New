# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""MDR / XDR / PDR classification (Magiorakos 2012)."""
from typing import Any
from typing import Dict
from typing import List

from cdss.ocr.ocr_parsing import normalize_sir_map
from cdss.therapy.intrinsic import (
    _remove_intrinsic_resistance,
)


# =========================================================
# MDR / XDR / PDR Classification -- CDC & ECDC 2017
# =========================================================
# تعريف الفئات حسب Magiorakos et al. 2012 (ECDC/CDC)
MDR_CATEGORIES = {
    "Aminoglycosides":         ["Gentamicin","Amikacin","Tobramycin","Netilmicin"],
    "Antipseudomonal Penics":  ["Piperacillin + Tazobactam"],
    # Magiorakos Table 1 counts 3rd AND 4th generation as ONE category. Splitting
    # them across three entries double-counted ONE cephalosporin mechanism.
    #
    # CORRECTION (2026-07): an earlier revision of this comment claimed a plain
    # ESBL should score 1 category and come back NOT MDR. That is wrong, and the
    # code below is right. Magiorakos Table 3 lists Penicillins, Penicillins +
    # BLI, Non-extended-spectrum cephalosporins and Extended-spectrum
    # cephalosporins as FOUR SEPARATE categories, so an ESBL E. coli that is
    # non-susceptible to ampicillin, amoxicillin-clavulanate, cefuroxime and
    # ceftriaxone is non-susceptible in four -- MDR, which is also how ESBL-E are
    # reported throughout the literature. Do not "fix" the code to match the old
    # comment; merging 3rd and 4th generation agents into one entry is the whole
    # of the intended change.
    "Extended-Sp Cephalosporins": ["Ceftriaxone","Cefotaxime","Cefixime",
                                   "Ceftazidime","Cefoperazone",
                                   "Cefoperazone + Sulbactam","Cefepime"],
    # 1st/2nd generation: a distinct Magiorakos category that had no entry, so
    # resistance to it counted for nothing. Cefuroxime is 2nd gen and moves here.
    "Non-Extended-Sp Cephalosporins": ["Cephalexin","Cefadroxil","Cephradine",
                                       "Cefazolin","Cefaclor","Cefuroxime",
                                       "Cefuroxime sodium"],
    "Cephamycins":             ["Cefoxitin"],
    "Monobactams":             ["Aztreonam"],
    # Penicillin (benzylpenicillin) had no category at all, so a penicillin-R
    # pneumococcus scored zero for the one class that defines PRSP.
    "Penicillins":             ["Ampicillin","Amoxicillin","Penicillin"],
    "Carbapenems":             ["Imipenem/Cilastatin","Meropenem","Ertapenem"],
    # Moxifloxacin and Gatifloxacin were in the formulary but in NO category, so
    # resistance to them counted for nothing. Magiorakos lists moxifloxacin under
    # Fluoroquinolones for S. aureus, Enterococcus and Enterobacteriaceae alike.
    "Fluoroquinolones":        ["Ciprofloxacin","Levofloxacin","Ofloxacin","Norfloxacin",
                                "Moxifloxacin","Gatifloxacin"],
    "Folate PI":               ["Trimethoprim/Sulfamethoxazole"],
    "Penicillins+BLI":         ["Amoxicillin + Clavulanic acid","Ampicillin/Sulbactam"],
    "Polymyxins":              ["Colistin"],
    # Teicoplanin added 2026-11-10 (Magiorakos Tables 1-2 list it).
    "Glycopeptides":           ["Vancomycin", "Teicoplanin"],
    "Oxazolidinones":          ["Linezolid"],
    # Kept for any external caller; no organism set counts it any more --
    # nitrofurantoin appears in NO Magiorakos table (2026-11-10).
    "Nitrofurans":             ["Nitrofurantoin"],
    # Categories added 2026-11-10 -- in the Magiorakos tables and now stocked:
    "Glycylcyclines":          ["Tigecycline"],
    "Lipopeptides":            ["Daptomycin"],
    "Anti-MRSA Cephalosporins": ["Ceftaroline"],
    "Fosfomycins":             ["Fosfomycin", "Fosfomycin IV"],
    "Tetracyclines":           ["Doxycycline", "Tetracycline", "Minocycline"],
    "Macrolides":              ["Azithromycin", "Clarithromycin", "Erythromycin"],
    "Lincosamides":            ["Clindamycin"],
    "Rifamycins":              ["Rifampicin"],
    # ── Categories that had NO entry at all before ────────────────────────────
    # Magiorakos Table 1 (S. aureus): "Anti-staphylococcal beta-lactams (or
    # cephamycins)" with oxacillin OR cefoxitin as the marker agent. Neither
    # Oxacillin nor Penicillin belonged to any category, and Cephamycins was
    # excluded from the Gram-positive set -- so a textbook MRSA (oxacillin R,
    # cefoxitin R, penicillin R, erythromycin R, ciprofloxacin R) scored only
    # 2 categories and came back level=None. This category is used ONLY in the
    # staphylococcal set, so Cefoxitin is never double-counted against the
    # Gram-negative "Cephamycins" entry.
    "Anti-staphylococcal Beta-lactams": ["Oxacillin", "Cefoxitin"],
    # Magiorakos Table 1: "Fucidanes". Fusidic acid was in the formulary with no
    # category, so fusidic-acid resistance in S. aureus counted for nothing.
    "Fusidanes":               ["Fusidic acid"],
    # Pneumococci are OUTSIDE the Magiorakos scope (the paper covers S. aureus,
    # Enterococcus, Enterobacteriaceae, P. aeruginosa and Acinetobacter only).
    # This single "Cephalosporins" bucket follows the conventional MDRSP
    # definition and deliberately merges 2nd/3rd-generation agents, so one
    # PBP-mediated mechanism cannot be counted twice.
    "Cephalosporins (pneumococcal)": ["Cefuroxime", "Cefuroxime sodium",
                                      "Ceftriaxone", "Cefotaxime", "Cefixime"],
}

# Categories meaningful for Gram-negative organisms (Enterobacterales / non-fermenters)
# FIX 2026-11-10: "Nitrofurans" removed (in no Magiorakos table -- it padded
# the denominator and could push an isolate away from an XDR call);
# "Glycylcyclines" (tigecycline, Magiorakos Table 3) added.
MDR_CATEGORIES_GRAM_NEG = frozenset([
    "Aminoglycosides", "Antipseudomonal Penics", "Extended-Sp Cephalosporins",
    "Carbapenems", "Fluoroquinolones", "Folate PI", "Penicillins+BLI",
    "Polymyxins", "Non-Extended-Sp Cephalosporins", "Cephamycins",
    "Monobactams", "Penicillins", "Glycylcyclines",
    "Fosfomycins", "Tetracyclines",
])

# ── Gram-positive category sets — ONE SET PER ORGANISM GROUP ────────────────
# A single flat "Gram-positive" set cannot be correct, because Magiorakos builds
# a DIFFERENT category list for each organism. The old flat set contained
# neither Penicillins nor any anti-staphylococcal beta-lactam entry, so the two
# resistances that define MRSA and ampicillin-resistant E. faecium were both
# invisible to the classifier, while Nitrofurans (a urinary agent that appears
# in no Magiorakos table) padded the denominator and pushed isolates away from
# an XDR call.
#
# Magiorakos et al., Clin Microbiol Infect 2012;18:268-281.

# Table 1 — Staphylococcus aureus.
# Categories present in this formulary; those with no agent stocked here
# (anti-MRSA cephalosporins, glycylcyclines, lipopeptides, phenicols,
# streptogramins, ansamycins) simply never contribute.
MDR_CATEGORIES_STAPH = frozenset([
    "Anti-staphylococcal Beta-lactams", "Aminoglycosides", "Fluoroquinolones",
    "Folate PI", "Fusidanes", "Glycopeptides", "Lincosamides", "Macrolides",
    "Oxazolidinones", "Tetracyclines", "Rifamycins", "Fosfomycins",
    # 2026-11-10: Magiorakos Table 1 categories now stocked in the formulary.
    "Anti-MRSA Cephalosporins", "Lipopeptides", "Glycylcyclines",
])

# Table 2 — Enterococcus spp.
# Note what is ABSENT and must stay absent: cephalosporins and folate-pathway
# inhibitors (intrinsic / no in-vivo activity) and nitrofurantoin (not a
# Magiorakos category). Penicillins here means AMPICILLIN — the single most
# important marker for E. faecium, previously uncounted.
MDR_CATEGORIES_ENTEROCOCCUS = frozenset([
    "Penicillins", "Aminoglycosides", "Carbapenems", "Fluoroquinolones",
    "Glycopeptides", "Oxazolidinones", "Tetracyclines",
    # 2026-11-10: Magiorakos Table 2 categories now stocked.
    "Lipopeptides", "Glycylcyclines",
])

# Streptococci (incl. S. pneumoniae) — NOT a Magiorakos organism.
# Follows the conventional MDRSP definition: non-susceptibility to >=3 of
# penicillin, cephalosporins, macrolides, lincosamides, tetracyclines,
# folate-pathway inhibitors, fluoroquinolones, glycopeptides, oxazolidinones.
# Flagged as a non-Magiorakos basis in the returned `basis` field.
MDR_CATEGORIES_STREP = frozenset([
    "Penicillins", "Cephalosporins (pneumococcal)", "Macrolides",
    "Lincosamides", "Tetracyclines", "Folate PI", "Fluoroquinolones",
    "Glycopeptides", "Oxazolidinones",
])

# Retained for backward compatibility with any external caller / older test that
# still imports the flat name. It is the union of the three sets above and is
# NOT used by classify_mdr any more.
MDR_CATEGORIES_GRAM_POS = frozenset([
    "Anti-staphylococcal Beta-lactams", "Cephalosporins (pneumococcal)",
    "Penicillins", "Aminoglycosides", "Carbapenems", "Fluoroquinolones",
    "Folate PI", "Fusidanes", "Glycopeptides", "Lincosamides", "Macrolides",
    "Oxazolidinones", "Tetracyclines", "Rifamycins", "Fosfomycins",
    "Anti-MRSA Cephalosporins", "Lipopeptides", "Glycylcyclines",
])

GRAM_POSITIVE_ORGANISMS = frozenset([
    "staphylococcus aureus", "mrsa", "mssa",
    "staphylococcus epidermidis", "staphylococcus saprophyticus",
    "staphylococcus lugdunensis", "coagulase-negative staphylococci",
    "enterococcus faecalis", "enterococcus faecium", "enterococcus spp.", "vre",
    "streptococcus pneumoniae", "streptococcus pyogenes",
    "streptococcus agalactiae", "streptococcus viridans",
    "listeria monocytogenes", "corynebacterium",
])

# ── Organisms for which the MDR/XDR/PDR framework does not apply at all ──────
# Returning "XDR" for an anaerobe or a Legionella is not a conservative error --
# it is a fabricated alarm that drives escalation to reserve agents. Before this
# guard, `Anaerobes` and `Legionella pneumophila` were routed into the
# GRAM-NEGATIVE category set (they match no Gram-positive key) and, having no
# intrinsic-resistance row to strip their EXPECTED beta-lactam and
# aminoglycoside resistance, both came back XDR on 9 of 11 categories.
#
#  * no cell wall            -> every beta-lactam/glycopeptide result is expected
#  * obligate intracellular  -> AST is not performed and has no breakpoints
#  * anaerobes               -> intrinsically resistant to aminoglycosides;
#                               Magiorakos builds no category table for them
MDR_NOT_APPLICABLE = (
    "mycoplasma", "ureaplasma", "chlamydia", "chlamydophila",
    "legionella", "rickettsia", "coxiella", "bartonella", "brucella",
    "treponema", "borrelia", "leptospira",
    "anaerobe", "لاهوائي", "bacteroides", "clostrid", "fusobacterium",
    "peptostreptococcus", "prevotella", "veillonella", "actinomyces",
    "mycobacter",
    # Fungi. Found on re-review: "Candida albicans" matched no Gram-positive key,
    # fell through to the GRAM-NEGATIVE branch and was returned as MDR with the
    # basis "Magiorakos 2012, Tables 3-5" -- a bacterial framework applied to a
    # yeast, citing a paper that never mentions it. Antifungal susceptibility has
    # its own categories (CLSI M27/M60, EUCAST antifungal tables) and no
    # MDR/XDR/PDR definition at all.
    "candida", "aspergillus", "cryptococc", "fungus", "fungal", "yeast",
    "mucor", "rhizopus", "fusarium", "trichosporon", "malassezia",
    "histoplasma", "blastomyces", "coccidioides", "pneumocystis",
    "فطر", "خميرة",
)

# Aerobic organisms that ARE routinely classified in the literature but sit
# outside the five species Magiorakos actually tabulated. They keep a level, but
# the read-out says which authority it rests on so nobody quotes "Magiorakos
# XDR" for a Stenotrophomonas.
MDR_OUTSIDE_MAGIORAKOS = (
    "stenotrophomonas", "burkholderia", "salmonella", "shigella",
    "campylobacter", "haemophilus", "influenzae", "aeromonas",
    "moraxella", "neisseria", "vibrio", "yersinia", "listeria",
    "corynebacterium", "streptococc",
)

def classify_mdr(organism: str, sir_map: Dict[str, str]) -> Dict[str, Any]:
    """
    MDR/XDR/PDR classification -- Magiorakos et al. 2012 (ECDC/CDC).
    Key principles implemented:
    • Non-susceptible = R + I (not R alone)
    • Intrinsic resistance excluded before counting
    • Gram-pos / Gram-neg category sets applied per organism
    • Category counts as non-susceptible if non-susceptible to ≥1 agent in it
      (a category is "susceptible" only when EVERY tested agent in it is S)
    • PDR = non-susceptible to ALL agents in ALL categories (no S anywhere)
    • XDR/PDR held to MDR on thin panels (<6 categories or <3 multi-agent cats)
    • Reliability warning when too few categories testable
    • Also returns `conservative_resistant_categories` (the stricter "all agents
      lost" view) as METADATA only — never used to set the level.
    """
    sir_map = normalize_sir_map(sir_map)
    if not sir_map:
        return {"level": None, "resistant_categories": [], "total_tested": 0}

    org_l = (organism or "").lower().strip()

    # 0. Organisms the framework was never built for -> refuse, do not guess.
    if any(k in org_l for k in MDR_NOT_APPLICABLE):
        return {
            "level": None, "resistant_categories": [], "total_tested": 0,
            "not_applicable": True,
            "basis": "not applicable",
            "warnings": [
                "ℹ️ تصنيف MDR/XDR/PDR غير منطبق على هذا الكائن — المقاومة "
                "الظاهرة هنا متوقعة جوهرياً (لا جدار خلوي / لاهوائي / داخل "
                "خلوي إجباري) وليست مقاومة مكتسبة. Magiorakos 2012 لا يضع "
                "جدول فئات لهذه المجموعة."
            ],
        }

    # 1. Strip intrinsic resistance (Magiorakos: an intrinsically-resistant
    #    category is removed BEFORE the criteria are applied) -- but keep the
    #    ACQUIRED mecA / van resistances, which the same criteria count.
    clean_map = _remove_intrinsic_resistance(organism, sir_map, keep_acquired=True)

    # 2. Choose the category set for THIS organism group, not one flat
    #    Gram-positive list. Order matters: enterococci and streptococci must be
    #    tested before the generic staphylococcal branch.
    if any(k in org_l for k in ("enterococc", "vre")):
        applicable, _group, _basis = (MDR_CATEGORIES_ENTEROCOCCUS, "enterococcus",
                                      "Magiorakos 2012, Table 2")
    elif "streptococc" in org_l or "pneumococc" in org_l:
        applicable, _group, _basis = (MDR_CATEGORIES_STREP, "streptococcus",
                                      "MDRSP convention — outside Magiorakos scope")
    elif any(k in org_l for k in ("staphylococc", "staph", "mrsa", "mssa")):
        # Magiorakos Table 1 is S. AUREUS. Coagulase-negative staphylococci
        # (epidermidis, saprophyticus, haemolyticus, "CoNS") are not in the paper
        # at all, so labelling their result "Magiorakos 2012, Table 1" overstates
        # the authority behind it. The category set is the closest reasonable fit
        # and is kept; only the citation is corrected.
        _is_aureus = ("aureus" in org_l or org_l in ("mrsa", "mssa")
                      or "mrsa" in org_l or "mssa" in org_l)
        applicable, _group, _basis = (
            MDR_CATEGORIES_STAPH, "staphylococcus",
            "Magiorakos 2012, Table 1" if _is_aureus
            else "S. aureus categories applied to CoNS — outside Magiorakos scope")
    elif (any(g in org_l for g in GRAM_POSITIVE_ORGANISMS)
          or "gram-positive" in org_l or "gram positive" in org_l):
        # "Gram-positive cocci (unidentified)" (added 2026-11-10) matched no
        # key here and fell through to the GRAM-NEGATIVE set, reported as
        # "Magiorakos 2012, Tables 3-5" -- a Gram-negative framework applied to
        # a Gram-positive isolate (FIX 2026-11-11, round 4).
        applicable, _group, _basis = (MDR_CATEGORIES_GRAM_POS, "gram-positive (other)",
                                      "outside Magiorakos scope")
    else:
        applicable, _group, _basis = (MDR_CATEGORIES_GRAM_NEG, "gram-negative",
                                      "Magiorakos 2012, Tables 3-5")
        # Magiorakos Table 5 (Acinetobacter) has no glycylcycline category:
        # counting tigecycline-S as a susceptible category moved a CRAB with
        # only polymyxin + minocycline left from XDR down to MDR (v6.6).
        if "acinetobacter" in org_l:
            applicable = applicable - {"Glycylcyclines"}
            _basis = "Magiorakos 2012, Table 5"
    # An isolate identified only by its Gram stain is not one of the organisms
    # Magiorakos tabulated; say so rather than quote the paper for it.
    if (("unidentified" in org_l or "unspeciated" in org_l or "non-fermenting" in org_l)
            and "enterobacterales" not in org_l and "Magiorakos" in _basis):
        _basis = "organism not identified — provisional, outside Magiorakos scope"
    if any(k in org_l for k in MDR_OUTSIDE_MAGIORAKOS) and "Magiorakos" in _basis:
        _basis = "outside Magiorakos scope — literature convention"
    is_gram_pos = _group != "gram-negative"

    resistant_cats     = []
    susceptible_cats   = []
    single_drug_cats   = []   # categories judged on only 1 tested agent
    conservative_resistant_cats = []  # "therapeutic loss" view — metadata only

    for cat, drugs in MDR_CATEGORIES.items():
        if cat not in applicable:
            continue
        tested = [d for d in drugs if d in clean_map]
        if not tested:
            continue
        if len(tested) == 1:
            single_drug_cats.append(cat)
        # Magiorakos et al. 2012 (the international definition): a category counts
        # as NON-SUSCEPTIBLE — i.e. it contributes toward MDR/XDR — when the
        # isolate is non-susceptible (R or I) to AT LEAST ONE tested agent in it.
        # A category is "susceptible" only when EVERY tested agent in it is S.
        # (Requiring ALL agents to be non-S before counting the category is
        # stricter than Magiorakos and systematically UNDER-counts MDR/XDR — that
        # was the previous bug.)
        if any(clean_map.get(d) in ("R", "I") for d in tested):
            resistant_cats.append(cat)
        else:
            susceptible_cats.append(cat)
        # Supplementary conservative "Orange" view: a category is fully lost only
        # when NO tested agent is S. Kept purely as metadata for the therapeutic
        # read-out and for the PDR test below — it must NEVER drive the MDR/XDR
        # level, or the tool drifts below world references again.
        if not any(clean_map.get(d) == "S" for d in tested):
            conservative_resistant_cats.append(cat)

    total_cats = len(resistant_cats) + len(susceptible_cats)
    r_count    = len(resistant_cats)

    if total_cats == 0:
        return {"level": None, "resistant_categories": [], "total_tested": 0}

    # XDR/PDR require enough categories tested to be meaningful (Magiorakos:
    # XDR = susceptible to ≤2 categories out of the full applicable panel).
    # Without a broad panel we cannot reliably call XDR/PDR -> cap at MDR.
    _enough_for_xdr = total_cats >= 6

    # A category judged on a SINGLE tested agent is weak evidence: one disc can
    # be an error/outlier. XDR/PDR is a severe call, so it must rest on
    # categories confirmed by ≥2 agents. Count how many RESISTANT categories are
    # multi-agent; if fewer than 3, we do not make a categorical XDR/PDR call.
    _single = set(single_drug_cats)
    _multidrug_resistant = [c for c in resistant_cats if c not in _single]
    _enough_multidrug = len(_multidrug_resistant) >= 3

    # PDR (Magiorakos): non-susceptibility to ALL agents in ALL categories — i.e.
    # not susceptible to a single tested agent anywhere. Under the corrected
    # category counting, "every category is non-susceptible" (r_count == total)
    # is NOT the same as PDR, because a category can be non-susceptible while
    # still holding one S agent. PDR requires the conservative count (no S in any
    # category) to cover every evaluable category.
    # NOTE on "I". Magiorakos counts non-susceptible = I or R, and this engine
    # follows it. The paper predates the 2019 EUCAST redefinition of I as
    # "susceptible, increased exposure" -- a USABLE result at a higher dose, not
    # a failing one. Consequence: a panel reported entirely as I is classified
    # MDR here. That is faithful to the published criteria and errs toward
    # flagging, but it is a real divergence from current EUCAST language and is
    # recorded so nobody mistakes it for an oversight.
    _no_susceptible_anywhere = (len(conservative_resistant_cats) == total_cats)

    # Magiorakos Table 1, criterion (i): "an MRSA is always considered MDR by
    # virtue of being an MRSA" -- because oxacillin/cefoxitin resistance predicts
    # non-susceptibility to every beta-lactam category in the document except the
    # anti-MRSA cephalosporins. Detected from the AST MARKERS, not from the
    # organism name, so it fires on an isolate the lab reported as plain
    # "Staphylococcus aureus" with Oxacillin R -- which is how most labs report.
    _is_staph_grp = _group == "staphylococcus"
    _mrsa_by_marker = clean_map.get("Oxacillin") in ("R", "I") or \
                      clean_map.get("Cefoxitin") in ("R", "I")
    _mrsa_by_name = org_l == "mrsa" or "methicillin-resistant" in org_l \
                    or "methicillin resistant" in org_l
    _is_mrsa_mdr = _is_staph_grp and (_mrsa_by_marker or _mrsa_by_name)

    if _no_susceptible_anywhere and _enough_for_xdr and _enough_multidrug:
        level = "PDR"
    elif (total_cats - r_count) <= 2 and r_count >= 3 and _enough_for_xdr and _enough_multidrug:
        level = "XDR"
    elif r_count >= 3:
        level = "MDR"
    elif _is_mrsa_mdr:
        level = "MDR"
    else:
        level = None

    # If pattern looks like XDR/PDR but the panel is too thin (few categories,
    # or resistant categories rest mostly on single agents), flag it but hold at
    # MDR rather than over-calling XDR/PDR.
    _capped = False
    if r_count >= 3 and (total_cats - r_count) <= 2 and not (_enough_for_xdr and _enough_multidrug):
        _capped = True

    # ── "Possible" XDR / PDR (Magiorakos 2012, v6.6) ─────────────────────────
    # The paper defines XDR and PDR against ALL the categories of the organism's
    # table and calls the result "possible XDR" / "possible PDR" when the
    # isolate was not tested in all of them. A category left out because every
    # agent in it is intrinsically inactive is not "untested".
    untested_cats = []
    for cat in sorted(applicable):
        cat_drugs = MDR_CATEGORIES.get(cat, [])
        if not cat_drugs or any(d in clean_map for d in cat_drugs):
            continue
        if cat == "Fosfomycins" and "pseudomonas" in org_l:
            continue   # in Magiorakos Table 4, but no CLSI/EUCAST breakpoint today: cannot be tested
        if _remove_intrinsic_resistance(organism, {d: "R" for d in cat_drugs},
                                        keep_acquired=True):
            untested_cats.append(cat)
    provisional = level in ("XDR", "PDR") and bool(untested_cats)

    # Reliability flag
    reliable = total_cats >= 4
    warnings = []
    if not reliable:
        warnings.append(f"⚠️ Only {total_cats} categories testable -- MDR classification may be unreliable.")
    if single_drug_cats:
        warnings.append(f"⚠️ Categories judged on a single agent: {', '.join(single_drug_cats)}")
    if _is_mrsa_mdr and level == "MDR" and r_count < 3:
        warnings.append("ℹ️ MDR بحكم التعريف: كل MRSA يُصنَّف MDR — مقاومة "
                        "Oxacillin/Cefoxitin تتنبأ بعدم الحساسية لكل فئات "
                        "البيتا-لاكتام (Magiorakos 2012, Table 1, criterion i).")
    if "outside" in _basis or "MDRSP" in _basis:
        warnings.append(f"ℹ️ أساس التصنيف: {_basis}. Magiorakos 2012 يغطي "
                        "S. aureus · Enterococcus · Enterobacteriaceae · "
                        "P. aeruginosa · Acinetobacter فقط.")
    if provisional:
        warnings.append(
            f"⚠️ {level} محتمل (possible {level} — Magiorakos 2012): التصنيف يُؤكَّد فقط عند "
            f"اختبار كل الفئات. لم تُختبر {len(untested_cats)} فئة: {', '.join(untested_cats)}.")
    if _capped:
        warnings.append("⚠️ Resistance pattern suggests XDR/PDR, but the evidence is too thin "
                        "(few categories, or resistant categories rest on a single agent each) -- "
                        "reported as MDR. Expand the panel with ≥2 agents per category to confirm.")

    return {
        "level":                  level,
        "resistant_categories":   resistant_cats,
        "susceptible_categories": susceptible_cats,
        "total_tested":           total_cats,
        "total_categories_evaluable": total_cats,
        "resistant_count":        r_count,
        "single_drug_categories": single_drug_cats,
        "conservative_resistant_categories": conservative_resistant_cats,
        "reliable":               reliable,
        "warnings":               warnings,
        "gram":                   "positive" if is_gram_pos else "negative",
        "group":                  _group,
        "basis":                  _basis,
        "mrsa_rule_applied":      bool(_is_mrsa_mdr),
        "not_applicable":         False,
        "untested_categories":    untested_cats,
        "provisional":            provisional,
    }


def mdr_display_label(mdr_result: Dict[str, Any]) -> str:
    """The label to print: 'possible XDR' when not every category was tested."""
    level = (mdr_result or {}).get("level")
    if not level:
        return ""
    label = MDR_INFO.get(level, {}).get("label", level)
    if (mdr_result or {}).get("provisional"):
        n = len(mdr_result.get("untested_categories") or [])
        label = f"Possible {label} ({n} categor{'y' if n == 1 else 'ies'} not tested)"
    return label

def physician_mdr_level(mdr_result: Dict[str, Any]) -> str:
    """The level a PHYSICIAN-facing report prints (v7.0, review 2026-11-19).

    A provisional XDR/PDR ("possible XDR": not every category was tested) is
    printed as MDR, which IS established (>= 3 categories non-susceptible).
    "Possible XDR" stays on the screen and in the internal QA report, where
    the untested categories are listed and can be acted on.
    """
    level = (mdr_result or {}).get("level") or ""
    if level in ("XDR", "PDR") and (mdr_result or {}).get("provisional"):
        return "MDR"
    return level


def physician_mdr_label(mdr_result: Dict[str, Any]) -> str:
    level = physician_mdr_level(mdr_result)
    return MDR_INFO.get(level, {}).get("label", level) if level else ""


def physician_mdr_categories(mdr_result: Dict[str, Any], sir_map: Dict[str, Any],
                             usable=None) -> List[str]:
    """Non-susceptible categories, each marked with the agents in it that are still S.

    "Aminoglycosides" in the resistant list beside gentamicin as the first
    choice read as a contradiction; "Aminoglycosides (gentamicin S)" does not.
    Magiorakos counts a category non-susceptible when ONE agent is I/R.
    """
    out: List[str] = []
    for cat in (mdr_result or {}).get("resistant_categories") or []:
        # `usable` (the advisory's allowed / caution names): only an agent the
        # report actually offers is worth naming -- "Cefixime S" inside an ESBL
        # category, or an uninterpretable cefoperazone-sulbactam, is not.
        s_agents = [d for d in MDR_CATEGORIES.get(cat, [])
                    if str((sir_map or {}).get(d, "")).strip().upper() == "S"
                    and (usable is None or d in usable)]
        out.append(f"{cat} ({', '.join(s_agents)} S)" if s_agents else cat)
    return out


# v7.4 (external case review): the image printed "MDR: non-susceptible 6/9
# categories" beside three category names. Every counted category is named
# now, and the QA sheet shows the calculation (agent results per category).
_SHORT_CAT = {
    "Extended-Sp Cephalosporins": "3rd/4th-gen cephalosporins",
    "Non-Extended-Sp Cephalosporins": "1st/2nd-gen cephalosporins",
    "Antipseudomonal Penics": "anti-pseudomonal penicillin+BLI",
    "Penicillins+BLI": "penicillins+BLI",
    "Folate PI": "folate-pathway inhibitors",
    "Fluoroquinolones": "fluoroquinolones",
    "Tetracyclines": "tetracyclines",
    "Aminoglycosides": "aminoglycosides",
    "Carbapenems": "carbapenems",
}


_COMPACT_CAT = {
    "Extended-Sp Cephalosporins": "3rd/4th-gen ceph", "Non-Extended-Sp Cephalosporins": "1st/2nd-gen ceph",
    "Antipseudomonal Penics": "pip-tazo", "Penicillins+BLI": "pen+BLI", "Folate PI": "folate PI",
    "Fluoroquinolones": "FQ", "Aminoglycosides": "aminoglycosides", "Carbapenems": "carbapenems",
    "Tetracyclines": "tetracyclines",
}


def mdr_short_categories(categories, compact: bool = False) -> List[str]:
    """Short, readable names for category labels (image / compact lines)."""
    table = _COMPACT_CAT if compact else _SHORT_CAT
    return [table.get(c, _SHORT_CAT.get(c, c)) for c in (categories or [])]


def mdr_breakdown(mdr_result: Dict[str, Any], sir_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per tested category: the agents in it with their results, and the verdict.

    [{category, agents: [(drug, result)], non_susceptible: bool}] -- resistant
    categories first, in the order classify_mdr() reports them. A category is
    non-susceptible when ONE agent in it is I or R (Magiorakos 2012).
    """
    sir = {str(k): str(v or "").strip().upper() for k, v in (sir_map or {}).items()}
    out: List[Dict[str, Any]] = []
    for cats, ns in (((mdr_result or {}).get("resistant_categories") or [], True),
                     ((mdr_result or {}).get("susceptible_categories") or [], False)):
        for cat in cats:
            agents = [(d, sir[d]) for d in MDR_CATEGORIES.get(cat, []) if d in sir]
            out.append({"category": cat, "agents": agents, "non_susceptible": ns})
    return out


MDR_INFO = {
    "MDR": {
        "label":  "MDR -- Multi-Drug Resistant",
        "color":  "warning",
        "icon":   "⚠️",
        "detail": "مقاوم لعامل واحد على الأقل في 3 فئات دوائية أو أكثر.",
        "action": "تجنب الأدوية المقاومة. استشر الصيدلي السريري.",
    },
    "XDR": {
        "label":  "XDR -- Extensively Drug Resistant",
        "color":  "error",
        "icon":   "🔴",
        "detail": "مقاوم لمعظم الفئات الدوائية -- حساس لفئتين أو أقل فقط.",
        "action": "يستلزم استشارة متخصص. الخيارات محدودة جداً.",
    },
    "PDR": {
        "label":  "PDR -- Pan-Drug Resistant",
        "color":  "error",
        "icon":   "🚨",
        "detail": "مقاوم لجميع الفئات الدوائية المتاحة.",
        "action": "حالة طارئة -- استشارة معدية فورية. لا خيارات قياسية.",
    },
}
