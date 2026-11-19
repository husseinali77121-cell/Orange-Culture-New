# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""English pregnancy notes, one per agent that can reach the pregnancy bucket.

Added v6.7 (2026-11-14). The formulary's `preg_note` is Arabic. The English PDF
translated it with a phrase table, and any line the table could not finish was
dropped and replaced by one generic sentence ("not a first-line agent ...").
So the English report told the obstetric team nothing about the trimester rule
for nitrofurantoin, the near-term kernicterus rule for TMP-SMX or the
once-daily rule for gentamicin. These are the same notes, in English.

Same sources as the Arabic notes: ACOG Committee Opinion 717 (reaffirmed),
ACOG 2021/2023, BNF 2025, EMA 2025, ENTIS 2024, product labels.

Line prefixes are load-bearing: the PDF colours a line by its first character
(⚠ caution, ⛔/⊘ avoid, ✅/✓ acceptable, >>> decision line).
"""
from typing import Dict

_DECISION = ">>> Final decision: treating physician. <<<"
_DECISION_TRIM = ">>> Final decision: treating physician, by trimester. <<<"

_FQ = (
    "⚠️ Pregnancy caution — {name} (fluoroquinolone):\n"
    "Not a first-line agent in pregnancy.\n"
    "Recent evidence (ENTIS 2024): the malformation risk is lower than once thought.\n"
    "Use only when no safer alternative exists (beta-lactam / azithromycin).\n"
    + _DECISION
)

_AMINOGLYCOSIDE = (
    "⚠️ Pregnancy caution — {name}:\n"
    "Crosses the placenta; fetal ototoxicity is documented mainly with streptomycin and "
    "kanamycin — with gentamicin it is theoretical and rare.\n"
    "Acceptable when needed (chorioamnionitis: ampicillin + gentamicin; severe "
    "pyelonephritis or sepsis) as a once-daily dose, with levels, for the shortest course "
    "(ACOG).\n"
    + _DECISION
)

_NOVEL_LIMITED = (
    "⚠️ Pregnancy caution — {name}:\n"
    "Limited human data. Use only for a life-threatening infection with no effective "
    "alternative.\n"
    + _DECISION
)

PREG_NOTE_EN: Dict[str, str] = {
    "Ciprofloxacin": _FQ.format(name="Ciprofloxacin"),
    "Levofloxacin": _FQ.format(name="Levofloxacin"),
    "Ofloxacin": _FQ.format(name="Ofloxacin"),
    "Norfloxacin": _FQ.format(name="Norfloxacin").replace(
        _DECISION, "⚠️ Low bioavailability (35 %) — little drug outside the urine.\n" + _DECISION),
    "Gatifloxacin": _FQ.format(name="Gatifloxacin"),
    "Moxifloxacin": _FQ.format(name="Moxifloxacin"),
    "Nitrofurantoin": (
        "⚠️ Pregnancy caution — Nitrofurantoin:\n"
        "1st trimester: only when no suitable alternative exists (ACOG CO 717).\n"
        "✅ 2nd and early 3rd trimester: an acceptable first choice for cystitis.\n"
        "⛔ Avoid in the 3rd trimester and especially at term (≥ 36 weeks): fetal haemolytic "
        "anaemia (G6PD deficiency) and neonatal haemolysis.\n"
        "Alternative in the 3rd trimester: Fosfomycin (single dose) or Cephalexin.\n"
        + _DECISION_TRIM
    ),
    "Fosfomycin": (
        "⚠️ Pregnancy — Fosfomycin:\n"
        "✅ EMA / BNF 2025: acceptable as a single 3 g dose for uncomplicated UTI in pregnancy.\n"
        "Preferred over nitrofurantoin in the 3rd trimester; more reassuring data than the "
        "fluoroquinolones.\n"
        + _DECISION
    ),
    "Gentamicin": _AMINOGLYCOSIDE.format(name="Gentamicin"),
    "Amikacin": _AMINOGLYCOSIDE.format(name="Amikacin"),
    "Tobramycin": _AMINOGLYCOSIDE.format(name="Tobramycin"),
    "Trimethoprim/Sulfamethoxazole": (
        "⚠️ Pregnancy caution — TMP-SMX:\n"
        "1st trimester: folate antagonist — only when no suitable alternative exists "
        "(ACOG CO 717), with folic acid.\n"
        "✅ 2nd trimester: acceptable.\n"
        "⛔ Near term (≥ 32–36 weeks): avoid — risk of kernicterus.\n"
        + _DECISION_TRIM
    ),
    "Metronidazole": (
        "⚠️ Pregnancy caution — Metronidazole:\n"
        "ACOG 2021: recent evidence refuted the old malformation concerns.\n"
        "✅ Acceptable in every trimester when medically necessary.\n"
        "Prefer to avoid in the 1st trimester if a safe alternative exists.\n"
        + _DECISION
    ),
    "Imipenem/Cilastatin": (
        "⚠️ Pregnancy caution — Imipenem/Cilastatin:\n"
        "Limited human data.\n"
        "When a carbapenem is needed in pregnancy, Meropenem is preferred (more data); use "
        "imipenem only when meropenem is unavailable and the infection is severe.\n"
        + _DECISION
    ),
    "Vancomycin": (
        "⚠️ Pregnancy caution — Vancomycin:\n"
        "Use when needed (MRSA in pregnancy); it is the first-line anti-MRSA agent in "
        "pregnancy.\n"
        "Monitor maternal renal function and hearing.\n"
        + _DECISION
    ),
    "Linezolid": (
        "⚠️ Pregnancy caution — Linezolid:\n"
        "Limited human data (fetal toxicity in animals at high doses).\n"
        "Not an absolute contraindication: an option for a resistant Gram-positive infection "
        "(MRSA / VRE) with no safer alternative — Vancomycin is first line in pregnancy.\n"
        ">>> Final decision: treating physician — benefit against risk. <<<"
    ),
    "Colistin": (
        "⚠️ Pregnancy caution — Colistin:\n"
        "Very limited human data; marked nephrotoxicity — a risk to maternal and fetal "
        "renal function.\n"
        "Life-saving use only, for an XDR Gram-negative infection with no alternative.\n"
        "BNF 2025: avoid whenever possible — monitor renal function closely.\n"
        + _DECISION
    ),
    "Aztreonam": (
        "⚠️ Pregnancy caution — Aztreonam:\n"
        "Limited human data; crosses the placenta — use only when needed.\n"
        + _DECISION
    ),
    "Erythromycin": (
        "⚠️ Pregnancy — Erythromycin:\n"
        "✅ Base / stearate: acceptable (the macrolide with most pregnancy experience).\n"
        "⛔ Estolate: contraindicated — maternal hepatotoxicity.\n"
        "Azithromycin is a safer alternative with fewer interactions.\n"
        + _DECISION
    ),
    "Clindamycin": (
        "⚠️ Pregnancy — Clindamycin:\n"
        "✅ Acceptable when needed; used for bacterial vaginosis and for GBS prophylaxis in "
        "penicillin allergy.\n"
        "Avoid high doses in the 1st trimester where possible.\n"
        + _DECISION
    ),
    "Fusidic acid": (
        "⚠️ Pregnancy caution — Fusidic acid:\n"
        "Limited human data — use only when needed. Topical use is generally acceptable.\n"
        "Systemic: avoid in the 3rd trimester (theoretical kernicterus risk).\n"
        + _DECISION
    ),
    "Ceftazidime + Avibactam": _NOVEL_LIMITED.format(name="Ceftazidime-Avibactam"),
    "Ceftolozane + Tazobactam": _NOVEL_LIMITED.format(name="Ceftolozane-Tazobactam"),
    "Meropenem + Vaborbactam": _NOVEL_LIMITED.format(name="Meropenem-Vaborbactam"),
    "Imipenem + Relebactam": _NOVEL_LIMITED.format(name="Imipenem-Relebactam"),
    "Cefiderocol": _NOVEL_LIMITED.format(name="Cefiderocol"),
    "Aztreonam + Avibactam": _NOVEL_LIMITED.format(name="Aztreonam-Avibactam"),
    "Sulbactam + Durlobactam": _NOVEL_LIMITED.format(name="Sulbactam-Durlobactam"),
    # v6.9 (decision D5) -- from the product labels.
    "Pivmecillinam": (
        "✅ Pivmecillinam in pregnancy: two cohort studies (42,223 first-trimester exposures) "
        "showed no increase in major malformations (FDA label 2024); a first-line cystitis agent "
        "in the Nordic countries.\n"
        "Near delivery it can cause a false-positive isovaleric acidaemia newborn screen.\n"
        + _DECISION),
    "Sulopenem": (
        "⚠️ Pregnancy caution — Sulopenem: no human data; cleft palate in mice at ~23x the "
        "clinical exposure. Probenecid: no specific risk identified over decades of use.\n"
        "Use only when no better-established alternative exists.\n"
        + _DECISION),
    "Gepotidacin": (
        "⚠️ Pregnancy caution — Gepotidacin: no human data; decreased fetal weight and late "
        "resorptions in animals at exposures below the human dose (FDA label). A pregnancy "
        "registry exists.\n"
        + _DECISION),
    "Cefepime + Enmetazobactam": (
        "⚠️ Pregnancy caution — Cefepime-Enmetazobactam: no data for the combination; "
        "cephalosporin (including cefepime) data are reassuring.\n"
        + _DECISION),
    "Fosfomycin IV": (
        "⚠️ Pregnancy caution — Fosfomycin IV: crosses the placenta; no data for intravenous "
        "use in pregnancy (SmPC) — avoid unless the benefit clearly outweighs the risk.\n"
        + _DECISION),
    "Ceftaroline": (
        "⚠️ Pregnancy caution — Ceftaroline:\n"
        "Limited human data — use only when needed.\n"
        + _DECISION
    ),
    "Daptomycin": (
        "⚠️ Pregnancy caution — Daptomycin:\n"
        "Limited human data — use only when needed.\n"
        + _DECISION
    ),
    "Teicoplanin": (
        "⚠️ Pregnancy caution — Teicoplanin:\n"
        "Limited data — Vancomycin is preferred in pregnancy.\n"
        + _DECISION
    ),
}

# The pregnancy rule's own fall-backs, used when an agent has no formulary note.
FQ_DEFAULT_EN = _FQ
NITROFURANTOIN_DEFAULT_EN = PREG_NOTE_EN["Nitrofurantoin"]
METRONIDAZOLE_DEFAULT_EN = PREG_NOTE_EN["Metronidazole"]
GENERIC_WARN_EN = (
    "⚠️ Pregnancy caution — {name}:\n"
    "Limited or conflicting data in pregnancy — use only when no safer alternative exists.\n"
    + _DECISION
)


def preg_note_en(name: str) -> str:
    """The English pregnancy note for `name` (never empty)."""
    return PREG_NOTE_EN.get(name) or GENERIC_WARN_EN.format(name=name)
