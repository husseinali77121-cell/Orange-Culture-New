# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Why each EUCAST-sourced rule is still in the program (audit 2026-11-19).

Decision D1 (2026-11-14) made CLSI M100 Ed36 the reference for everything.
Forty-one rows of the guideline registry still name a EUCAST document as their
source, because that is where they were first checked. This table has 42
entries: those 41, plus nobp_cefoperazone, which was CONVERTED and now cites
CLSI M100 (v7.2: the header said 41 and the table held 42). It records, row by
row, which of three things is true -- and the test suite fails if a
EUCAST-sourced row has no entry here, so a new one cannot slip in silently.

  CLSI_CONCORDANT  CLSI states the same rule. The rule stays exactly as it is
                   and is now CITED CLSI FIRST (`citation_line`, the QC
                   reference strings). EUCAST remains as a second citation.

  EUCAST_ONLY      CLSI has no counterpart (no CLSI criterion, no CLSI
                   statement either way) and nothing in CLSI contradicts it.
                   Kept because removing it would lose a real safety check
                   (a laboratory-error pattern, an impossible result). The
                   reason it is kept is written next to it.

  CONVERTED        CLSI (or the FDA criteria CLSI defers to) says something
                   different. The behaviour was changed
                   to CLSI on 2026-11-19 (v7.0); the EUCAST reading survives
                   only as an explanatory caution where it helps.

Verified against: EUCAST Intrinsic Resistance and Unusual Phenotypes v3.3
(2021-10-18) table titles and footnotes (Table 1 = Enterobacterales, 2 =
non-fermenters, 3 = other Gram-negatives, 4 = Gram-positives, 5 = anaerobes);
CLSI M100 archived-drugs table; a CLSI-based US antibiogram reporting Serratia
tetracycline as tested (19% S) while marking it intrinsic only for the Proteeae;
CLSI 2019 cefoperazone criteria for Enterobacterales (S <= 16, I 32, R >= 64
mg/L) as quoted in PMC9617991. CLSI M100 itself is a licensed document: every
CLSI locus below still needs Dr. Tarek's reading before countersignature.
"""
from __future__ import annotations

from typing import Dict

CLSI_CONCORDANT = "clsi_concordant"
EUCAST_ONLY = "eucast_only"
CONVERTED = "converted"
DECISIONS = (CLSI_CONCORDANT, EUCAST_ONLY, CONVERTED)

AUDITED_ON = "2026-11-19"


def _c(clsi: str, why: str) -> Dict[str, str]:
    return {"decision": CLSI_CONCORDANT, "clsi": clsi, "why": why}


def _e(why: str, clsi: str = "") -> Dict[str, str]:
    return {"decision": EUCAST_ONLY, "clsi": clsi, "why": why}


def _x(clsi: str, why: str) -> Dict[str, str]:
    return {"decision": CONVERTED, "clsi": clsi, "why": why}


AUDIT: Dict[str, Dict[str, str]] = {
    # ── Intrinsic resistance ────────────────────────────────────────────────
    "intr_anaerobes_aminoglycosides_polymyxins": _c(
        "CLSI M11-Ed9 (aminoglycosides inactive against anaerobes)",
        "CLSI states the aminoglycoside part. The polymyxin part has no CLSI counterpart "
        "and nothing contradicts it."),
    "intr_haemophilus_gram_pos_agents": _e(
        "CLSI publishes no Haemophilus criteria for glycopeptides, oxazolidinones, "
        "daptomycin, fusidic acid or clindamycin, so there is nothing to convert to. "
        "Kept because it blocks a Gram-positive-only agent reported S on a Gram-negative.",
        clsi="CLSI M100 Ed36 Table 2E (no criteria for these agents)"),
    "intr_entero_gram_pos_agents": _c(
        "CLSI M100 Ed36 Appendix B1 (header list for all Enterobacterales)",
        "Same list in CLSI: clindamycin, daptomycin, fusidic acid, glycopeptides, "
        "linezolid, macrolides (Salmonella/Shigella azithromycin excepted), rifampin."),
    "intr_klebsiella_ampicillin": _c("CLSI M100 Ed36 Appendix B1",
                                     "CLSI lists ampicillin for K. pneumoniae and K. oxytoca."),
    "intr_proteus_mirabilis": _c(
        "CLSI M100 Ed36 Appendix B1",
        "CLSI lists tetracyclines, nitrofurantoin and polymyxins for P. mirabilis."),
    "intr_morganella_providencia_proteus_vulgaris": _c(
        "CLSI M100 Ed36 Appendix B1",
        "The tribe pattern (aminopenicillins, 1st-generation cephalosporins, "
        "tetracyclines, nitrofurantoin, polymyxins) is the same in CLSI."),
    "intr_proteus_vulgaris_penneri": _c("CLSI M100 Ed36 Appendix B1",
                                        "Same entries in CLSI for P. vulgaris and P. penneri."),
    "intr_serratia": _x(
        "CLSI M100 Ed36 Appendix B1 (S. marcescens: no tetracycline entry)",
        "EUCAST v3.3 Table 1 fn.5 makes tetracycline and doxycycline intrinsic for "
        "S. marcescens; CLSI does not, and CLSI-based laboratories report them as tested. "
        "v7.0: they left the intrinsic list (reported as tested) and carry a treatment "
        "caution instead (prefer minocycline or another agent). The rest of the row is "
        "the same in CLSI."),
    "intr_hafnia_colistin": _c("CLSI M100 Ed36 Appendix B1",
                               "CLSI lists polymyxin B / colistin for Hafnia alvei."),
    "intr_pseudomonas": _c("CLSI M100 Ed36 Appendix B2", "Same entries in CLSI."),
    "intr_stenotrophomonas": _c("CLSI M100 Ed36 Appendix B2", "Same entries in CLSI."),
    "intr_mrsa_betalactams": _c(
        "CLSI M100 Ed36 Table 2C",
        "CLSI: oxacillin-resistant staphylococci are resistant to other beta-lactams "
        "except the anti-MRSA cephalosporins."),
    "intr_mycoplasma_cellwall_agents": _c("CLSI M43",
                                          "No cell wall: the same statement in CLSI M43."),
    "intr_staph_gram_neg_agents": _c(
        "CLSI M100 Ed36 Appendix B3",
        "CLSI lists aztreonam, polymyxins and nalidixic acid. Temocillin has no CLSI "
        "criteria at all; that entry is EUCAST only and harmless."),
    "intr_enterococcus_cephalosporins": _c(
        "CLSI M100 Ed36 Appendix B4 · Table 2D",
        "CLSI: cephalosporins, clindamycin and fusidic acid may appear active in vitro "
        "but are not effective clinically; aztreonam from the Gram-positive header."),
    "intr_strep_enterococcus_aminoglycosides": _c(
        "CLSI M100 Ed36 Table 2D (HLAR screen only)",
        "CLSI tests only high-level aminoglycoside resistance for synergy."),
    "intr_enterococcus_sxt_invivo": _c(
        "CLSI M100 Ed36 Table 2D / Appendix B4",
        "CLSI: TMP-SMX may appear active in vitro but is not effective clinically."),
    "intr_listeria_cephalosporins": _c("CLSI M45 Ed3 (Listeria)",
                                       "CLSI M45: cephalosporins are not active."),
    "intr_nonfermenter_narrow_spectrum": _c("CLSI M100 Ed36 Appendix B2",
                                            "Same entries in CLSI."),
    "intr_citrobacter_koseri_klebsiella_oxytoca_classA": _c(
        "CLSI M100 Ed36 Appendix B1",
        "CLSI lists ampicillin (and piperacillin / ticarcillin) for C. koseri and "
        "K. oxytoca; inhibitor combinations are not intrinsic in either."),

    # ── No breakpoints ─────────────────────────────────────────────────────
    "nobp_nonfermenter_narrow_spectrum": _c(
        "CLSI M100 Ed36 Tables 2B-2 / 2B-3 / 2B-4 (no criteria)",
        "CLSI publishes no criteria for these agents either."),
    "nobp_azithromycin_enterobacterales": _c(
        "CLSI M100 Ed36 Table 2A (azithromycin: Salmonella Typhi and Shigella only)",
        "Same restriction in CLSI."),
    "nobp_cefoperazone": _x(
        "CLSI M100 Table 2A (cefoperazone, Enterobacterales: S <= 16, I 32, R >= 64 mg/L) · "
        "CLSI archived-drugs table",
        "CLSI keeps a criterion for cefoperazone ALONE against Enterobacterales and "
        "archived it for P. aeruginosa and staphylococci; cefoperazone-sulbactam has none "
        "anywhere. v7.0: cefoperazone alone is read by the CLSI criterion for "
        "Enterobacterales (with a caution that it dates from the original dosing); the "
        "no-breakpoint flag stays for cefoperazone-sulbactam and for every other "
        "organism (new row nobp_cefoperazone_non_enterobacterales)."),
    "nobp_fosfomycin_oral_non_ecoli": _c(
        "CLSI M100 Ed36 Table 2A (fosfomycin: E. coli urinary isolates only)",
        "Same restriction in CLSI (CLSI's other fosfomycin criterion, E. faecalis urine, "
        "is outside this Enterobacterales rule)."),
    "nobp_tigecycline_proteae": _x(
        "CLSI M100 Ed36 (no tigecycline criteria) · FDA label (decreased activity: "
        "Morganella, Proteus, Providencia)",
        "Proteeae part concordant: CLSI has no tigecycline criteria and the FDA label states "
        "their reduced activity. Serratia part converted: EUCAST v16.1 calls tigecycline "
        "activity 'insufficient' in Serratia, but the FDA STIC Enterobacterales criteria "
        "cover Serratia, so v7.0 removed Serratia from this no-breakpoint rule and keeps "
        "the EUCAST remark as a treatment caution (organism profile)."),

    # ── Rare / method ──────────────────────────────────────────────────────
    "rare_linezolid_gram_pos": _c(
        "CLSI M100 Ed36 Appendix A (linezolid-resistant: confirm ID and AST)",
        "CLSI lists the same confirmation."),
    "rare_colistin_disc": _c(
        "CLSI M100 Ed36 Tables 2A / 2B-1 / 2B-2 (colistin: broth microdilution, CBDE or "
        "CAT only)",
        "CLSI: disk diffusion and gradient strips are not valid for colistin."),

    # ── Consistency / hierarchy ────────────────────────────────────────────
    "equiv_ctx_cro": _c("CLSI M100 Ed36 Table 2A (identical criteria)",
                        "Cefotaxime and ceftriaxone share the same CLSI criteria."),
    "equiv_amc_sam": _e(
        "A laboratory-consistency check (a split result is unexpected - verify; v7.2 "
        "severity 'warning'). CLSI has no statement either way. Kept: it catches "
        "transcription and reading errors."),
    "hier_amp_vs_amc": _e(
        "Logic, not a breakpoint: adding an inhibitor does not lower activity. No CLSI "
        "counterpart is needed and none contradicts it. v7.3: a verify flag (warning), "
        "as the registry row says."),
    "hier_pip_vs_tzp": _e("Same logic as hier_amp_vs_amc; the CLSI pip-tazo and "
                          "piperacillin breakpoints differ, so verify (warning)."),
    "hier_mem_vs_etp": _e(
        "Mechanism logic (ertapenem is the most labile carbapenem). CLSI uses the same "
        "fact for carbapenemase screening; no contradiction."),
    "hier_tet_vs_doxy": _c(
        "CLSI M100 Ed36 Table 2A (tetracycline-S predicts doxycycline and minocycline-S)",
        "The same prediction rule in CLSI."),
    "hier_van_vs_tei_enterococcus": _e(
        "Mechanism logic (VanA / VanB / VanC). No CLSI counterpart; no contradiction."),
    "hier_pen_vs_cro_pneumococcus": _c(
        "CLSI M100 Ed36 Table 2G",
        "CLSI: penicillin-susceptible pneumococci can be considered susceptible to "
        "ceftriaxone. v7.3: a verify flag -- a non-meningitis penicillin S (MIC <= 2) "
        "with a meningitis ceftriaxone R is possible."),
    "hier_pen_vs_ctx_pneumococcus": _c("CLSI M100 Ed36 Table 2G",
                                       "Same for cefotaxime."),
    "QC003": _e(
        "An unusual-phenotype verification prompt (carbapenem-S, colistin-R amid broad "
        "resistance). CLSI has no counterpart; asking to confirm the ID harms nothing."),
    "QC004": _c("CLSI M100 Ed36 Tables 3B / 3C (mCIM / eCIM)",
                "CLSI: carbapenem-non-susceptible Enterobacterales -> carbapenemase test."),
    "QC004b": _c(
        "CLSI M100 Ed36 Table 2A (imipenem comment: Proteus, Providencia, Morganella) · "
        "Tables 3B / 3C",
        "CLSI states the Proteeae imipenem exception and the carbapenemase test."),
    "QC006": _c(
        "CLSI M100 Ed36 Table 3A (current breakpoints: report as tested, no ESBL editing)",
        "CLSI: with current cephalosporin breakpoints, ESBL testing is not needed for "
        "reporting and results are not edited."),
    "SPEC-URN": _c("CLSI M100 Ed36 Table 1 ('U' = urinary isolates only)",
                   "CLSI restricts nitrofurantoin, fosfomycin and norfloxacin to urine."),
    "REP-GPO-GN": _c(
        "CLSI M100 Ed36 Appendix B1 / B2 (Gram-negative: glycopeptides, oxazolidinones, "
        "daptomycin)",
        "Same statement in CLSI."),
}


def entry(rule_id: str) -> Dict[str, str]:
    """The audit decision for a registry row, or {} when it was never EUCAST-sourced."""
    return AUDIT.get(rule_id, {})


def summary() -> Dict[str, int]:
    """How many rows took each decision (for the docs and the release notes)."""
    out = {d: 0 for d in DECISIONS}
    for row in AUDIT.values():
        out[row["decision"]] += 1
    return out
