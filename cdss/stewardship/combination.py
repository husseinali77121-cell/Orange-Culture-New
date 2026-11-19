# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Combination-therapy recommendations per resistance phenotype."""
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from cdss.formulary.abx_guidelines import ABX_GUIDELINES


# ═══════════════════════════════════════════════════════════════════════
# ENGINE 4 -- Combination Therapy Suggester
# IDSA AMR Guidance 2026 | WHO Priority Pathogens | ESCAPE organisms
# ═══════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════
# COMBINATION / DEFINITIVE-THERAPY PANELS — rewritten 2026-11-10
# ----------------------------------------------------------------------
# Re-read against IDSA AMR Guidance 2026 (Gram-negatives) and the primary
# trials. Defects in the previous table:
#   * CRAB led with "Ampicillin-Sulbactam + Colistin" citing ATTACK. ATTACK
#     (Kaye, Lancet Infect Dis 2023) tested SULBACTAM-DURLOBACTAM vs colistin;
#     sulbactam-durlobactam + a carbapenem is now IDSA's priority regimen and
#     was absent. "Colistin + Rifampicin + Meropenem" cited AIDA, which tested
#     colistin +/- meropenem and found no benefit (as did OVERCOME 2023);
#     rifampicin added nothing in Durante-Mangoni (CID 2013). Both are now
#     listed as AVOID with their real evidence.
#   * CRE listed agents without the enzyme class that decides between them
#     (KPC / OXA-48 / MBL), cited RECAPTURE (a cUTI trial, not CRE) and had no
#     aztreonam-avibactam. Options now carry `for_types`.
#   * CRPA led with "Ceftolozane-Tazobactam + Amikacin". IDSA: a carbapenem-R
#     isolate still S to a traditional beta-lactam is treated with that agent
#     (high dose, extended infusion); routine aminoglycoside combination is not
#     suggested once susceptibility is known.
#   * ESBL called ertapenem "carbapenem-sparing" (it is a carbapenem) and had
#     no urinary pathway (TMP-SMX / FQ preferred for pyelonephritis/cUTI).
#   * MRSA / VRE options cited "IDSA AMR Guidance 2026", which covers
#     Gram-negatives only; "AVOID: Vancomycin + Pip-Tazo" cited a "NINJA trial"
#     -- the evidence is observational, and the ACORN RCT (JAMA 2023) found no
#     AKI difference between pip-tazo and cefepime. Now a monitoring note.
#   * No AmpC or S. maltophilia panel existed.
# ═══════════════════════════════════════════════════════════════════════
COMBINATION_THERAPY: Dict[str, Dict] = {
    "CRAB": {
        "title": "Carbapenem-Resistant A. baumannii (CRAB)",
        "urgency": "CRITICAL",
        "options": [
            {"combo": "Sulbactam-Durlobactam + Meropenem or Imipenem", "evidence": "★★★",
             "indication": "Preferred regimen for CRAB (durlobactam protects sulbactam from OXA-23/24/58)",
             "caution": "Not active against MBL-producing Acinetobacter. If resistant: two "
                        "non-sulbactam agents, or sulbactam-durlobactam + cefiderocol (IDSA 2026)",
             "ref": "ATTACK (Kaye, Lancet Infect Dis 2023) | IDSA AMR Guidance 2026"},
            {"combo": "High-dose Ampicillin-Sulbactam (9 g sulbactam/day) + second active agent "
                      "(Polymyxin B, Minocycline, Tigecycline or Cefiderocol)", "evidence": "★★",
             "indication": "When sulbactam-durlobactam is unavailable -- at least two active agents",
             "caution": "Polymyxin B preferred over colistin outside the urinary tract",
             "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Cefiderocol as part of a combination", "evidence": "★",
             "indication": "Intolerance or resistance to the regimens above",
             "caution": "CREDIBLE-CR: excess mortality in the Acinetobacter subgroup -- never as monotherapy",
             "ref": "CREDIBLE-CR (Bassetti, Lancet Infect Dis 2021) | IDSA AMR Guidance 2026"},
            {"combo": "AVOID: Colistin + Meropenem as the backbone", "evidence": "AVOID",
             "indication": "",
             "caution": "AIDA (Paul, Lancet Infect Dis 2018) and OVERCOME (Kaye, NEJM Evid 2023): "
                        "adding meropenem to colistin did not improve outcome",
             "ref": "AIDA 2018 | OVERCOME 2023"},
            {"combo": "AVOID: Rifampicin added to a polymyxin", "evidence": "AVOID",
             "indication": "",
             "caution": "No mortality benefit (Durante-Mangoni, Clin Infect Dis 2013)",
             "ref": "Durante-Mangoni 2013"},
        ]
    },
    "CRPA": {
        "title": "Carbapenem-Resistant Pseudomonas aeruginosa (CRPA, not DTR)",
        "urgency": "HIGH",
        "options": [
            {"combo": "Traditional beta-lactam that tests S (Pip-Tazo, Ceftazidime, Cefepime or "
                      "Aztreonam) -- high dose, extended infusion", "evidence": "★★★",
             "indication": "Carbapenem-R but still S to a traditional agent -- treat with that agent",
             "caution": "Repeat AST if the isolate is from a relapse",
             "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Ceftolozane-Tazobactam / Ceftazidime-Avibactam / Imipenem-Relebactam",
             "evidence": "★★",
             "indication": "Only if no traditional beta-lactam tests S (then the isolate is usually DTR)",
             "caution": "Reserve agents -- see the DTR-PA panel",
             "ref": "IDSA AMR Guidance 2026"},
        ]
    },
    "DTR_PA": {
        "title": "Difficult-to-Treat Resistance -- P. aeruginosa (DTR-PA)",
        "urgency": "CRITICAL",
        "options": [
            {"combo": "Ceftolozane-Tazobactam", "evidence": "★★★",
             "indication": "Preferred; favoured over ceftazidime-avibactam for pneumonia",
             "caution": "", "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Ceftazidime-Avibactam", "evidence": "★★★",
             "indication": "Preferred alternative (not active if the isolate produces an MBL)",
             "caution": "", "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Imipenem-Relebactam", "evidence": "★★★",
             "indication": "Preferred alternative (not active against MBL producers)",
             "caution": "High risk of resistance emerging on therapy, as with ceftazidime-avibactam (IDSA 2026)",
             "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Cefiderocol", "evidence": "★★",
             "indication": "Preferred when an MBL (VIM/NDM) is detected; otherwise when the above are inactive",
             "caution": "", "ref": "IDSA AMR Guidance 2026"},
            {"combo": "AVOID: Colistin-based combination as first choice",
             "evidence": "AVOID",
             "indication": "",
             "caution": "IDSA prefers the novel beta-lactams over polymyxins for DTR-PA -- lower "
                        "nephrotoxicity and better outcomes. Reserve polymyxins for when none is active.",
             "ref": "IDSA AMR Guidance 2026"},
        ]
    },
    "CRE": {
        "title": "Carbapenem-Resistant Enterobacterales (CRE)",
        "urgency": "CRITICAL",
        "options": [
            {"combo": "Identify the carbapenemase class (NG-Test CARBA-5 / PCR)", "evidence": "★★★",
             "indication": "The enzyme class decides the agent -- NDM and OXA-48 are the commonest in Egypt",
             "caution": "", "ref": "IDSA AMR Guidance 2026", "for_types": ["UNKNOWN"]},
            {"combo": "Ceftazidime-Avibactam", "evidence": "★★★",
             "indication": "KPC or OXA-48 producers -- preferred",
             "caution": "Inactive alone against MBL (NDM/VIM/IMP)", "ref": "IDSA AMR Guidance 2026",
             "for_types": ["KPC", "OXA-48", "UNKNOWN"]},
            {"combo": "Meropenem-Vaborbactam", "evidence": "★★★",
             "indication": ("KPC producers -- preferred, slightly favoured: resistance emerged in "
                            "<3% vs ~10% with ceftazidime-avibactam (IDSA 2026)"),
             "caution": "Inactive against OXA-48 and MBL", "ref": "TANGO-II 2018 | IDSA AMR Guidance 2026",
             "for_types": ["KPC", "UNKNOWN"]},
            {"combo": "Imipenem-Relebactam", "evidence": "★★★",
             "indication": "KPC producers -- preferred",
             "caution": "Inactive against OXA-48 and MBL", "ref": "RESTORE-IMI 1 2020 | IDSA AMR Guidance 2026",
             "for_types": ["KPC", "UNKNOWN"]},
            {"combo": "Aztreonam-Avibactam", "evidence": "★★★",
             "indication": "NDM / VIM / IMP (MBL) producers -- preferred",
             "caution": "Breakpoints for Enterobacterales (CLSI M100 Ed36)",
             "ref": "ASSEMBLE / REVISIT | IDSA AMR Guidance 2026", "for_types": ["MBL", "UNKNOWN"]},
            {"combo": "Ceftazidime-Avibactam + Aztreonam (given together)", "evidence": "★★★",
             "indication": "MBL producers -- preferred alternative where aztreonam-avibactam is unavailable",
             "caution": "Synergy test (e.g. disk-stacking) advisable",
             "ref": "Falcone, Clin Infect Dis 2021 | IDSA AMR Guidance 2026", "for_types": ["MBL", "UNKNOWN"]},
            {"combo": "Cefiderocol", "evidence": "★★",
             "indication": "MBL producers (alternative); KPC / OXA-48 when the preferred agents are inactive",
             "caution": "", "ref": "IDSA AMR Guidance 2026", "for_types": ["MBL", "KPC", "OXA-48", "UNKNOWN"]},
            {"combo": "Polymyxin B or Colistin-based combination", "evidence": "★",
             "indication": "Only when no novel agent is active",
             "caution": "Nephrotoxicity; not for intrinsically polymyxin-R genera (Proteeae, Serratia)",
             "ref": "IDSA AMR Guidance 2026"},
        ]
    },
    "ESBL": {
        "title": "ESBL-Producing Enterobacterales",
        "urgency": "MODERATE",
        "options": [
            {"combo": "Cystitis: Nitrofurantoin, TMP-SMX or a single dose of an aminoglycoside",
             "evidence": "★★★",
             "indication": ("Preferred for uncomplicated cystitis if S (IDSA 2026; pivmecillinam, oral "
                            "sulopenem and gepotidacin where available). Oral fosfomycin: E. coli "
                            "only, alternative"),
             "caution": "Not for pyelonephritis or bacteraemia", "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Pyelonephritis / cUTI: TMP-SMX, Ciprofloxacin or Levofloxacin", "evidence": "★★★",
             "indication": ("Preferred if S; ertapenem / meropenem / imipenem if resistant. "
                            "Pip-Tazo an alternative only when not critically ill and not "
                            "bacteraemic (IDSA 2026)"),
             "caution": "", "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Outside the urinary tract: Meropenem, Imipenem or Ertapenem", "evidence": "★★★",
             "indication": "Preferred for bacteraemia and serious infection; oral TMP-SMX/FQ step-down once stable",
             "caution": "Ertapenem: avoid in hypoalbuminaemia (<2.5 g/dL) and critical illness",
             "ref": "MERINO 2018 | IDSA AMR Guidance 2026"},
            {"combo": "AVOID: Piperacillin-Tazobactam for bacteremia", "evidence": "AVOID",
             "indication": "Inferior to meropenem for ESBL bloodstream infection",
             "caution": "MERINO (Harris, JAMA 2018): 30-day mortality 12.3% vs 3.7%", "ref": "MERINO 2018"},
            {"combo": "AVOID: Cefepime for pyelonephritis, cUTI or bacteraemia", "evidence": "AVOID",
             "indication": "Even when cefepime tests S", "caution": "", "ref": "IDSA AMR Guidance 2026"},
        ]
    },
    "AMPC": {
        "title": "AmpC-producing Enterobacterales (derepressed / plasmid)",
        "urgency": "MODERATE",
        "options": [
            {"combo": "Cefepime (MIC <= 8: S or SDD)", "evidence": "★★★",
             "indication": "Preferred for invasive infection -- stable to AmpC",
             "caution": ("SDD (MIC 4-8): use the high-exposure regimen, 2 g q8h (CLSI). IDSA 2026: "
                         "SDD is not associated with ESBL -- a carbapenem only if an ESBL gene is found"),
             "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Carbapenem (Meropenem / Ertapenem)", "evidence": "★★★",
             "indication": "Cefepime R, a confirmed ESBL gene, or critical illness", "caution": "",
             "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Oral step-down: TMP-SMX or a fluoroquinolone", "evidence": "★★",
             "indication": "After clinical response, if S", "caution": "", "ref": "IDSA AMR Guidance 2026"},
            {"combo": "AVOID: Ceftriaxone or Pip-Tazo to START invasive therapy (E. cloacae, "
                      "K. aerogenes, C. freundii)", "evidence": "AVOID",
             "indication": "Selection of derepressed mutants on therapy",
             "caution": "Acceptable for cystitis; continuing ceftriaxone is reasonable in a non-severe "
                        "infection that is already responding (IDSA 2026)",
             "ref": "IDSA AMR Guidance 2026"},
        ]
    },
    "STENO": {
        "title": "Stenotrophomonas maltophilia (invasive)",
        "urgency": "HIGH",
        "options": [
            {"combo": "Cefiderocol monotherapy", "evidence": "★★★",
             "indication": "Preferred for invasive infection", "caution": "",
             "ref": "IDSA AMR Guidance 2026"},
            {"combo": "Aztreonam-Avibactam (or Ceftazidime-Avibactam + Aztreonam) + second agent",
             "evidence": "★★",
             "indication": "Alternative -- no CLSI breakpoint for this organism",
             "caution": "", "ref": "IDSA AMR Guidance 2026"},
            {"combo": "TMP-SMX + Minocycline or Levofloxacin", "evidence": "★★",
             "indication": "When cefiderocol is unavailable; monotherapy acceptable only for mild infection or step-down",
             "caution": "TMP-SMX: high dose (8-12 mg/kg/day TMP); monitor potassium",
             "ref": "IDSA AMR Guidance 2026"},
            {"combo": "AVOID: Ceftazidime", "evidence": "AVOID",
             "indication": "CLSI removed the ceftazidime breakpoints for S. maltophilia (2024)",
             "caution": "L1/L2 beta-lactamases", "ref": "CLSI M100 Ed34"},
        ]
    },
    "MRSA": {
        "title": "Methicillin-Resistant S. aureus (MRSA)",
        "urgency": "HIGH",
        "options": [
            {"combo": "Vancomycin -- AUC/MIC target 400-600", "evidence": "★★★",
             "indication": "MRSA bacteremia | endocarditis | pneumonia -- first-line",
             "caution": "AUC-guided TDM (not trough-only)",
             "ref": "IDSA MRSA 2011 | ASHP/IDSA/PIDS/SIDP vancomycin TDM 2020"},
            {"combo": "Daptomycin (8-10 mg/kg)", "evidence": "★★★",
             "indication": "MRSA bacteremia / right-sided endocarditis -- alternative to vancomycin",
             "caution": "Daptomycin INEFFECTIVE for pneumonia (inactivated by surfactant); weekly CK",
             "ref": "Fowler, NEJM 2006 | IDSA MRSA 2011"},
            {"combo": "Linezolid 600mg q12h", "evidence": "★★★",
             "indication": "MRSA pneumonia -- equivalent alternative to vancomycin",
             "caution": "ZEPHyR showed higher clinical cure but no mortality difference; avoid >2 weeks, "
                        "weekly CBC, serotonin syndrome risk",
             "ref": "ZEPHyR (Wunderink, CID 2012) | IDSA MRSA 2011"},
            {"combo": "Daptomycin + Ceftaroline", "evidence": "★★",
             "indication": "Persistent MRSA bacteremia (salvage)",
             "caution": "Small RCT / observational evidence", "ref": "Geriak, AAC 2019 | expert consensus"},
            {"combo": "Vancomycin + Rifampicin", "evidence": "★★",
             "indication": "Retained prosthetic material only (prosthetic joint, valve, CIED) -- after bacteraemia clears",
             "caution": "Not for uncomplicated S. aureus bacteraemia (ARREST, Lancet 2018: no benefit); "
                        "never rifampicin monotherapy",
             "ref": "IDSA PJI 2013 | ARREST 2018"},
            {"combo": "Vancomycin + Piperacillin-Tazobactam -- monitor creatinine", "evidence": "★",
             "indication": "Not contraindicated",
             "caution": "Observational AKI signal; the ACORN RCT (JAMA 2023) found no AKI difference "
                        "between pip-tazo and cefepime. Daily creatinine; use AUC dosing",
             "ref": "ACORN (Qian, JAMA 2023)"},
        ]
    },
    "VRE": {
        "title": "Vancomycin-Resistant Enterococcus (VRE)",
        "urgency": "HIGH",
        "options": [
            {"combo": "Ampicillin (if the isolate tests S -- usually E. faecalis)", "evidence": "★★★",
             "indication": "Drug of choice whenever ampicillin is S", "caution": "",
             "ref": "AHA 2015 / ESC 2023 endocarditis guidance"},
            {"combo": "Linezolid 600mg q12h", "evidence": "★★★",
             "indication": "VRE -- serious infections when ampicillin is R",
             "caution": "Weekly CBC monitoring; myelosuppression risk",
             "ref": "Expert consensus (no IDSA guideline)"},
            {"combo": "Daptomycin high-dose (>=10 mg/kg)", "evidence": "★★",
             "indication": "VRE bacteremia", "caution": "Monitor CK weekly",
             "ref": "Britt, Clin Infect Dis 2017 (cohort)"},
            {"combo": "Daptomycin + Ampicillin (or Ceftaroline)", "evidence": "★",
             "indication": "Persistent VRE bacteremia / endocarditis -- beta-lactam potentiates daptomycin",
             "caution": "In-vitro / observational evidence", "ref": "Synergy studies"},
        ]
    },
}

# Agents inside COMBINATION_THERAPY option strings that carry a host-state
# contraindication. Matched as case-insensitive substrings of the combo text,
# because the strings are prose ("Ampicillin-Sulbactam (high-dose 9g q8h) +
# Colistin"), not formulary keys.
_COMBO_HOST_FLAGS: List[Tuple[str, List[str], str, str]] = [
    ("pregnancy", ["amikacin", "gentamicin", "tobramycin", "plazomicin"],
     "⚠️ حمل: أمينوجليكوزيد — سمية أذنية جنينية نظرية (موثّقة مع Streptomycin). "
     "يُستخدم عند الحاجة بجرعة يومية واحدة ومراقبة المستوى ولأقصر مدة (ACOG).",
     "PREGNANCY: aminoglycoside — theoretical fetal ototoxicity (documented with "
     "streptomycin). Use when needed: once-daily dosing, levels, shortest course (ACOG)."),
    ("pregnancy", ["tigecycline", "minocycline", "doxycycline", "eravacycline"],
     "⛔ حمل: تتراسيكلين — مضاد استطباب مطلق (تلوّن الأسنان، تثبيط نمو العظم).",
     "PREGNANCY: tetracycline — absolute contraindication."),
    ("pregnancy", ["ciprofloxacin", "levofloxacin", "moxifloxacin",
                   "fluoroquinolone"],
     "⚠️ حمل: فلوروكينولون — يُتجنّب (سمّية غضروفية في الدراسات الحيوانية).",
     "PREGNANCY: fluoroquinolone — avoid (animal arthropathy)."),
    ("pregnancy", ["rifampicin", "rifampin"],
     "⚠️ حمل: ريفامبيسين — خطر نزف وليدي، أعطِ فيتامين K للأم والوليد.",
     "PREGNANCY: rifampicin — neonatal haemorrhage risk; give vitamin K."),
    ("neonate", ["ceftriaxone"],
     "⛔ وليد: سيفترياكسون — يزيح البيليروبين ويترسّب مع الكالسيوم. استخدم "
     "cefotaxime بدلاً منه.",
     "NEONATE: ceftriaxone — bilirubin displacement / calcium precipitation. "
     "Use cefotaxime."),
    ("neonate", ["tigecycline", "minocycline", "doxycycline",
                 "ciprofloxacin", "levofloxacin", "moxifloxacin"],
     "⛔ وليد/طفل: غير مناسب لهذه الفئة العمرية إلا باستثناء مبرَّر.",
     "NEONATE/CHILD: not appropriate for this age band without justification."),
    # Added 2026-08-03. A mutation that widened this panel's neonate window to
    # every infant survived every suite — and writing the test that kills it
    # showed the window was not the only gap: NONE of the salvage agents this
    # panel actually recommends was in the neonate list. A neonate with XDR
    # Pseudomonas got Cefiderocol and Imipenem-Relebactam with no age caution
    # at all, because the list named only ceftriaxone and the tetracyclines.
    #
    # Amikacin and colistin are deliberately NOT here: amikacin is standard
    # neonatal sepsis therapy and colistin has real neonatal experience. Adding
    # them would flag the two agents a neonatologist is most likely to need.
    ("neonate", ["cefiderocol", "relebactam", "vaborbactam", "avibactam",
                 "ceftolozane", "ceftaroline", "daptomycin", "durlobactam"],
     "⚠️ وليد: بيانات السلامة والجرعة في حديثي الولادة محدودة أو غير متوفرة "
     "لهذا الدواء. لا يُستخدم إلا بعد استشارة حديثي الولادة والأمراض المعدية، "
     "وبتوثيق سبب غياب البديل.",
     "NEONATE: neonatal safety and dosing data for this agent are limited or "
     "absent. Use only after neonatology and infectious-diseases consultation, "
     "documenting why no alternative exists."),
    # v6.6: daptomycin is not recommended under 12 months (Cubicin label) --
    # the engine now bans it below that age; the card must say so too.
    ("infant", ["daptomycin"],
     "⛔ رضيع أقل من 12 شهر: Daptomycin غير موصى به (Cubicin label — تأثيرات عضلية وعصبية "
     "في الدراسات الحيوانية على حديثي الولادة). البديل: Vancomycin.",
     "INFANT under 12 months: daptomycin is not recommended (Cubicin label — muscular "
     "and nervous-system effects in neonatal animal studies). Use vancomycin."),
    ("renal", ["colistin", "polymyxin", "amikacin", "gentamicin", "tobramycin",
               "vancomycin"],
     "⚠️ قصور كلوي: يحتاج تعديل جرعة ومتابعة CrCl/TDM — الجرعات المكتوبة هنا "
     "للوظيفة الكلوية الطبيعية.",
     "RENAL IMPAIRMENT: dose adjustment plus CrCl/TDM monitoring required — the "
     "doses quoted here assume normal renal function."),
    ("hepatic", ["tigecycline", "rifampicin", "rifampin"],
     "⚠️ قصور كبدي: يحتاج تعديل جرعة ومتابعة إنزيمات الكبد.",
     "HEPATIC IMPAIRMENT: dose adjustment and LFT monitoring required."),
]

def get_combination_therapy(
    phenotypes: List[Dict],
    *,
    is_pregnant: bool = False,
    age_years: Optional[float] = None,
    age_months: Optional[float] = None,
    is_renal: bool = False,
    cl_cr: Optional[float] = None,
    is_hepatic: bool = False,
    organism: str = "",
    carbapenemase_type: Optional[str] = None,
) -> List[Dict]:
    """Combination therapy suggestions -- IDSA AMR Guidance 2026.

    FIX 2026-08-01 (second pass): this took `phenotypes` and nothing else. It
    was the ONLY panel in the app that proposed agents without passing through
    analyze_antibiotics() or apply_safety_gate(), and it renders in an expander
    that is open by default under a CRITICAL header. A pregnant patient with
    CRPA was shown "Ceftolozane-Tazobactam + Amikacin" with an empty caution
    field, while the main engine was refusing amikacin for that same patient
    three panels above.

    These are XDR salvage regimens from the literature, so they are NOT removed
    -- withholding the only option for a pan-resistant isolate is its own harm.
    The host contraindication is attached to the option instead, in the
    `caution` slot the renderer already displays.
    """
    results: List[Dict] = []
    ph_names = [p.get("phenotype", "") for p in phenotypes]

    states = set()
    if is_pregnant:
        states.add("pregnancy")
    # Months win over years. `age_years` is the UI's INTEGER field, which reads
    # 0 for every infant from birth to eleven months — the same trap that made
    # apply_safety_gate() treat a six-month-old as a neonate (fixed 2026-08-03).
    # Resolve here too rather than inheriting it.
    from cdss.common.clinical_utils import resolve_age_years as _ray, NEONATE_MAX_YEARS as _NMY
    _eff_age = _ray(age_years, age_months)
    if _eff_age is not None and _eff_age <= _NMY:
        states.add("neonate")
    if _eff_age is not None and _eff_age < 1:
        states.add("infant")
    if is_renal or (cl_cr is not None and cl_cr < 60):
        states.add("renal")
    if is_hepatic:
        states.add("hepatic")

    # DTR_PA before CRPA: when both fire, the narrower finding carries the
    # more specific therapeutic instruction and should read first. (The CRPA
    # panel now says "use the traditional beta-lactam that tests S", which is
    # moot for a DTR isolate, so it is not shown alongside DTR_PA.)
    if "DTR_PA" in ph_names:
        ph_names = [p for p in ph_names if p != "CRPA"]
    # CRE options are filtered by enzyme class when it is known (2026-11-10):
    # showing meropenem-vaborbactam for an NDM producer is a wrong answer, not
    # a neutral one.
    from cdss.therapy.therapy_rules import normalize_carbapenemase_type as _nct
    _ctype = _nct(carbapenemase_type) or "UNKNOWN"
    for ph in ["CRAB", "DTR_PA", "CRPA", "CRE", "STENO", "AMPC", "ESBL", "MRSA", "VRE", "MDR"]:
        if ph not in ph_names or ph not in COMBINATION_THERAPY:
            continue
        data = COMBINATION_THERAPY[ph]
        if ph == "CRE":
            _kept = [o for o in data["options"]
                     if not o.get("for_types") or _ctype in o["for_types"]]
            if _ctype == "KPC":   # IDSA 2026 order for KPC: MEV, then CAZ-AVI, then IMI-REL
                _kept.sort(key=lambda o: 0 if o["combo"].startswith("Meropenem-Vaborbactam") else 1)
            _title = data["title"] + ("" if _ctype == "UNKNOWN" else f" — {_ctype}")
            data = {**data, "title": _title, "options": _kept}
        if not states:
            results.append({"phenotype": ph, "data": data})
            continue
        # Copy before annotating: COMBINATION_THERAPY is module-level and
        # Streamlit reruns this on every interaction, so mutating it in place
        # would accumulate host warnings from previous patients.
        opts = []
        for opt in data["options"]:
            combo_low = opt["combo"].lower()
            extra = [ar for state, drugs, ar, _en in _COMBO_HOST_FLAGS
                     if state in states and any(d in combo_low for d in drugs)]
            if extra:
                new_opt = dict(opt)
                new_opt["caution"] = "  ".join(
                    x for x in [opt.get("caution", ""), *extra] if x)
                new_opt["host_flagged"] = True
                opts.append(new_opt)
            else:
                opts.append(opt)
        results.append({"phenotype": ph, "data": {**data, "options": opts}})
    # ── The organism's OWN intrinsic resistance ─────────────────────────────
    # DEFECT 2026-08-06, raised by a third-party review and confirmed over 1,500
    # randomised cases: the CRE panel offered "Colistin + Meropenem high-dose"
    # for Proteus, Providencia, Morganella and Serratia — all four INTRINSICALLY
    # colistin-resistant. They are Enterobacterales, so CRE fires correctly; the
    # panel then recommended a polymyxin that cannot work against them, 50 times
    # in 1,500 cases.
    #
    # This is NOT the same as offering an agent the AST reported R. A salvage
    # regimen naming an AST-resistant drug is the POINT of high-dose extended
    # infusion — the strategy exists for isolates where the standard dose
    # failed. An INTRINSIC mechanism is different in kind: no dose, no infusion
    # time and no partner overcomes a missing target or a constitutive efflux
    # pump. It is a dead option printed in the panel a clinician reaches for
    # when nothing else is left.
    #
    # Options are ANNOTATED, not deleted: the reader should see that the
    # regimen exists and why it does not apply here, rather than wonder whether
    # the panel simply forgot it.
    #
    # Matching claims whole agent names longest-first — the same span-claiming
    # the OCR scanner uses. Without it "Ampicillin-Sulbactam", a genuine and
    # recommended CRAB agent, would match Acinetobacter's intrinsic "Ampicillin"
    # and be wrongly condemned.
    if organism and results:
        try:
            from cdss.organisms.clinical_data import INTRINSIC_RESISTANCE as _IR_C
            from cdss.common.clinical_utils import org_matches as _om_c
        except Exception:
            _IR_C, _om_c = {}, None
        _intr = set()
        if _om_c:
            for _k, _v in _IR_C.items():
                if _om_c(organism, [_k]):
                    _intr |= set(_v)
        if _intr:
            _agents = sorted(ABX_GUIDELINES, key=len, reverse=True)
            for _panel in results:
                _opts = []
                for _opt in _panel["data"]["options"]:
                    _txt = str(_opt.get("combo", ""))
                    if _txt.upper().startswith("AVOID"):
                        _opts.append(_opt)
                        continue
                    _norm = _txt.lower().replace("+", "-").replace("/", "-").replace(" ", "")
                    _claimed = []
                    for _ag in _agents:
                        _a = _ag.lower().replace("+", "-").replace("/", "-").replace(" ", "")
                        if _a and _a in _norm:
                            _claimed.append(_ag)
                            _norm = _norm.replace(_a, "\x00" * len(_a))
                    _dead = [d for d in _claimed if d in _intr]
                    if _dead:
                        _opt = dict(_opt)
                        _opt["host_flagged"] = True
                        _opt["intrinsically_inactive"] = _dead
                        _opt["caution"] = (
                            f"⛔ **{organism} مقاوم جوهرياً لـ "
                            f"{'، '.join(_dead)}** — لا جرعة ولا تسريب ممتد ولا "
                            f"شريك دوائي يتغلب على مقاومة جوهرية. هذا الخيار غير "
                            f"صالح لهذه العزلة. " + str(_opt.get("caution", ""))
                        ).strip()
                    _opts.append(_opt)
                _panel["data"] = dict(_panel["data"])
                _panel["data"]["options"] = _opts

    return results
