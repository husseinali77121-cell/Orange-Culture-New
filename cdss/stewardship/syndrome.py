# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Infection-syndrome inference from specimen and host."""
from typing import Any
from typing import Dict
from typing import Optional

from cdss.common.specimen import (
    classify_specimen,
)


# =========================================================
# MODULE 4 -- Infection Syndrome Module
# يربط Specimen + Organism + Phenotype بـ clinical syndrome
# =========================================================
INFECTION_SYNDROMES = {
    ("Urine", None): {
        "syndrome":  "Urinary Tract Infection (UTI)",
        # v7.1 (review 2026-11-19): "age > 65 -> Complicated UTI" removed. IDSA
        # cUTI 2025: age, diabetes, male sex and urologic abnormalities do not
        # by themselves make a UTI complicated; a catheter does.
        "classify":  lambda age, is_preg, is_cath: (
            "Catheter-associated UTI (CA-UTI)" if is_cath else
            "Pregnancy-associated UTI" if is_preg else
            "Uncomplicated UTI"
        ),
        "first_choice": ["Nitrofurantoin","Fosfomycin","Trimethoprim/Sulfamethoxazole"],
        # v7.0 (review 2026-11-19): a febrile CA-UTI was shown the CYSTITIS
        # first-line list. Bladder-only agents do not reach the kidney or the
        # bloodstream (IDSA cUTI 2025 · IDSA AMR Guidance 2026).
        "first_choice_by_sub": {
            # v7.1: TMP-SMX was listed for pregnancy without its timing limits,
            # and a pregnant pyelonephritis was given the fluoroquinolone list.
            "Pregnancy-associated UTI": ["Nitrofurantoin (avoid 1st trimester if an alternative "
                                         "exists, and at term)", "Cephalexin",
                                         "Amoxicillin-Clavulanate / Amoxicillin (if S)",
                                         "Fosfomycin"],
            "Pyelonephritis in pregnancy": ["Ceftriaxone", "Cefepime",
                                            "Ampicillin + Gentamicin",
                                            "ESBL: Meropenem / Ertapenem"],
            "Catheter-associated UTI in pregnancy": ["Ceftriaxone", "Cefepime",
                                                     "Ampicillin + Gentamicin",
                                                     "ESBL: Meropenem / Ertapenem"],
            "UTI in men": ["Trimethoprim/Sulfamethoxazole", "Ciprofloxacin / Levofloxacin",
                           "Nitrofurantoin (cystitis without prostatic involvement)"],
            "Complicated UTI": ["Ceftriaxone", "Ciprofloxacin / Levofloxacin",
                                "Trimethoprim/Sulfamethoxazole (if S)",
                                "ESBL: Ertapenem / Meropenem"],
            "Catheter-associated UTI (CA-UTI)": ["Ceftriaxone", "Ciprofloxacin / Levofloxacin",
                                                 "Trimethoprim/Sulfamethoxazole (if S)",
                                                 "ESBL: Ertapenem / Meropenem"],
        },
        # 2026-11-10: cUTI 7 days (IDSA cUTI 2025); the culture threshold read
        # "10^3 symptomatic / 10^5 asymptomatic" for every patient -- the
        # 10^3 figure applies to symptomatic women and men specifically.
        "duration": {"Uncomplicated UTI": "1-7 أيام حسب الدواء (Nitrofurantoin 5 · TMP-SMX 3 · Fosfomycin جرعة)",
                     "Complicated UTI": "7 أيام عند الاستجابة السريعة (FQ 5-7) — 10-14 للاستجابة البطيئة",
                     "Catheter-associated UTI (CA-UTI)": (
                         "7 أيام عند الاستجابة السريعة — 10-14 للاستجابة البطيئة؛ غيّر القسطرة إن "
                         "مرّ عليها ≥ 2 أسبوع وخذ العينة من القسطرة الجديدة (IDSA CA-UTI)"),
                     "Pregnancy-associated UTI": "5-7 أيام (ACOG 2023) ثم مزرعة متابعة",
                     "Pyelonephritis in pregnancy": ("وريدي حتى التحسن ثم فموي — إجمالي 14 يوم "
                                                     "(ACOG 2023)"),
                     "Catheter-associated UTI in pregnancy": (
                         "7 أيام عند الاستجابة السريعة — 10-14 للبطيئة (IDSA CA-UTI)؛ 14 يوم لو "
                         "التهاب حويضة (ACOG 2023). غيّر القسطرة إن مرّ عليها ≥ 2 أسبوع"),
                     "UTI in men": ("7 أيام (Drekonja 2021) — 10-14 لو اشتباه بروستاتا "
                                    "(حمى، ألم بالحوض أو العجان، تكرار)")},
        "escalation": "لو فشل الخط الأول أو CrCl < 45 (Nitrofurantoin) -> حسب الحساسية: Cefixime / Ciprofloxacin",
        # v7.0: the cystitis escalation line was printed for a febrile CA-UTI too
        "escalation_by_sub": {
            "Catheter-associated UTI in pregnancy": (
                "غيّر/انزع القسطرة أولاً؛ لا Fluoroquinolones ولا Tetracyclines في الحمل؛ ESBL -> "
                "Meropenem / Ertapenem."),
            "Pyelonephritis in pregnancy": ("لا Fluoroquinolones ولا Tetracyclines في الحمل؛ ESBL -> "
                                            "Meropenem / Ertapenem؛ اعمل سونار لو مفيش تحسن خلال "
                                            "48-72 ساعة (ACOG 2023)."),
            "UTI in men": ("حمى / ألم بالحوض أو العجان -> فكّر في prostatitis: FQ أو TMP-SMX "
                           "10-14 يوم؛ تدهور -> وريدي حسب الحساسية."),
            "Pregnancy-associated UTI": ("حسب الحساسية: Cephalexin / Amoxicillin-Clavulanate؛ "
                                         "حمى أو ألم الخاصرة -> التهاب حويضة: Ceftriaxone وريدي "
                                         "(ACOG 2023)."),
            "Complicated UTI": ("تدهور / sepsis -> وريدي حسب الحساسية؛ ESBL -> Ertapenem / Meropenem؛ "
                                "CRE -> حسب نوع الكاربابينيميز (IDSA 2026). اعمل تصوير لو مفيش تحسن "
                                "خلال 48-72 ساعة."),
            "Catheter-associated UTI (CA-UTI)": (
                "غيّر/انزع القسطرة أولاً؛ تدهور / sepsis -> وريدي حسب الحساسية؛ ESBL -> Ertapenem / "
                "Meropenem؛ CRE -> حسب نوع الكاربابينيميز (IDSA 2026)."),
        },
        "culture_threshold": ("≥ 10³ CFU/mL مع أعراض (نساء ورجال)؛ ≥ 10⁵ للبيلة اللاعرضية "
                              "(تُعالج فقط في الحمل وقبل إجراء بولي جراحي)"),
    },
    ("Blood", None): {
        "syndrome":  "Bloodstream Infection (BSI) / Bacteremia",
        "classify":  lambda age, is_preg, is_cath: (
            "Catheter-Related BSI (CRBSI)" if is_cath else "Community/Hospital BSI"
        ),
        "first_choice": ["Ceftriaxone","Piperacillin-Tazobactam","Meropenem (MDR/severe)"],
        "duration": {"Community/Hospital BSI": ("GNB: 7 أيام مع السيطرة على المصدر (BALANCE 2025) · "
                                                 "S. aureus: ≥14 يوم · حسب الكائن والمصدر"),
                     "Catheter-Related BSI (CRBSI)": ("إزالة الكاتيتر + GNB 7-14 · CoNS 5-7 · "
                                                      "S. aureus ≥14 يوم")},
        "escalation": "MDR/XDR -> Meropenem ± Amikacin. Endocarditis اشتباه -> اتشاور",
        "culture_threshold": "2 sets blood cultures قبل المضاد",
    },
    ("Sputum", None): {
        "syndrome":  "Respiratory Tract Infection",
        # FIX 2026-11-11 (round 4): age > 65 alone was labelled "Severe CAP".
        # Age is ONE CURB-65 point; severity needs the score (or ATS/IDSA
        # major/minor criteria), and suggest_severity() already rates an
        # otherwise-well 70-year-old as moderate. The label now says what is
        # actually known.
        "classify":  lambda age, is_preg, is_cath: (
            "HAP/VAP" if is_cath else ("CAP (age > 65 — assess CURB-65 / PSI)" if age > 65 else "CAP")
        ),
        "first_choice": ["Amoxicillin + Clavulanic acid","Levofloxacin","Azithromycin"],
        "duration": {"CAP": "5 أيام كحد أدنى حتى الاستقرار",
                     "CAP (age > 65 — assess CURB-65 / PSI)": (
                         "5 أيام كحد أدنى حتى الاستقرار — 7 أيام للحالات الشديدة أو MRSA/Pseudomonas"),
                     "Severe CAP": "5-7 أيام (أطول لـ MRSA/Pseudomonas)",
                     "HAP/VAP": "7 أيام (ATS/IDSA 2016)"},
        "escalation": "Pseudomonas/Acinetobacter -> anti-pseudomonal mandatory",
        # FIX 2026-11-10: BAL threshold is 10^4 CFU/mL (10^3 for PSB, 10^5-10^6
        # for endotracheal aspirate) -- the line read BAL 10^5.
        "culture_threshold": "BAL ≥ 10⁴ CFU/mL · PSB ≥ 10³ · شفط رغامي ≥ 10⁵–10⁶ (ATS/IDSA 2016)",
    },
    ("Wound Swab", None): {
        "syndrome":  "Skin & Soft Tissue Infection (SSTI)",
        "classify":  lambda age, is_preg, is_cath: "SSTI",
        "first_choice": ["Cephalexin","Amoxicillin + Clavulanic acid"],
        "duration": {"SSTI": "5-10 أيام حسب الشدة"},
        "escalation": "MRSA اشتباه -> TMP/SMX أو Doxycycline. Diabetic foot -> broader coverage",
        "culture_threshold": "أخذ عينة من العمق -- لا من السطح",
    },
    ("Pus", None): {
        "syndrome":  "Abscess / Deep Infection",
        "classify":  lambda age, is_preg, is_cath: "Abscess",
        "first_choice": ["Amoxicillin + Clavulanic acid","Metronidazole"],
        "duration": {"Abscess": "Drainage + 5-7 أيام"},
        "escalation": "Intra-abdominal -> Metronidazole إلزامي. Carbapenem لو ESBL",
        "culture_threshold": "Drainage culture -- أدق من swab",
    },
    ("Stool", None): {
        "syndrome":  "Gastrointestinal Infection",
        "classify":  lambda age, is_preg, is_cath: (
            "Severe GI / Immunocompromised" if (age < 2 or age > 65 or is_preg) else "Mild-Moderate GI Infection"
        ),
        "first_choice": ["Azithromycin", "Ciprofloxacin (if susceptible)"],
        "duration": {
            "Mild-Moderate GI Infection": "Supportive care -- antibiotics usually NOT needed",
            "Severe GI / Immunocompromised": "3-5 days (Azithromycin/Cipro)",
        },
        "escalation": "C. diff -> Vancomycin PO / Fidaxomicin. Salmonella typhi -> 7-14d Ceftriaxone.",
        "culture_threshold": "Stool culture for severe/immunocompromised cases only",
    },
    ("Stool Culture", None): {
        "syndrome":  "Gastrointestinal Infection",
        "classify":  lambda age, is_preg, is_cath: (
            "Severe GI / Immunocompromised" if (age < 2 or age > 65 or is_preg) else "Mild-Moderate GI Infection"
        ),
        "first_choice": ["Azithromycin", "Ciprofloxacin (if susceptible)"],
        "duration": {"GI Infection": "Supportive care preferred -- antibiotics for severe cases only"},
        "escalation": "C. diff -> Vancomycin/Fidaxomicin | Salmonella typhi -> 7-14d",
        "culture_threshold": "Culture for severe/immunocompromised only",
    },
    ("CSF", None): {
        "syndrome":  "Central Nervous System Infection (Meningitis)",
        "classify":  lambda age, is_preg, is_cath: "Bacterial Meningitis",
        "first_choice": ["Ceftriaxone","Meropenem"],
        "duration": {"Bacterial Meningitis": ("N. meningitidis 7 · H. influenzae 7 · S. pneumoniae 10-14 · "
                                              "GBS 14-21 · Listeria ≥21 · GNB 21 يوم")},
        "escalation": "ابدأ تجريبياً فوراً ولا تنتظر culture. Dexamethasone قبل المضاد أو معه",
        "culture_threshold": "CSF culture + Gram stain + Ag testing",
    },
}

def get_infection_syndrome(
    specimen:  str,
    organism:  str,
    age:       int,
    is_preg:   bool,
    is_cath:   bool = False,
    sex:       str = "",
    uti_upper: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    يعيد السياق السريري للعدوى -- يدعم مطابقة مرنة لأسماء العينات.

    `sex` added 2026-11-11 (round 4) so the card agrees with the duration
    engine for a man. v7.1: IDSA cUTI 2025 says male sex does not by itself make
    a UTI complicated, so a man's afebrile UTI is "UTI in men" (7 days, consider
    the prostate) -- not "Complicated UTI", not the 1-7 day cystitis course.
    """
    # Try exact match first
    syndrome_data = INFECTION_SYNDROMES.get((specimen, None))
    # Fuzzy fallback: match substring
    if not syndrome_data:
        spec_l = specimen.lower()
        for (key_spec, _), data in INFECTION_SYNDROMES.items():
            kl = key_spec.lower()
            if kl in spec_l or spec_l in kl:
                syndrome_data = data
                break
    # Canonical-category fallback (single source of truth -- classify_specimen)
    if not syndrome_data:
        _cat_to_key = {
            "urine": "Urine", "blood": "Blood", "sputum": "Sputum",
            "csf":   "CSF",   "stool": "Stool", "wound":  "Wound Swab",
            "pus":   "Pus",   "abdomen": "Pus",
        }
        _target = _cat_to_key.get(classify_specimen(specimen))
        if _target:
            syndrome_data = INFECTION_SYNDROMES.get((_target, None))

    if not syndrome_data:
        return None

    sub_type = syndrome_data["classify"](age, is_preg, is_cath)
    # v7.0: the RESOLVED syndrome (fever / flank pain -> upper UTI) decides too;
    # this card said "Uncomplicated UTI" while the engine treated pyelonephritis.
    # v7.1: a pregnant pyelonephritis keeps its own card (no fluoroquinolones).
    if is_preg and sub_type == "Catheter-associated UTI (CA-UTI)":
        sub_type = "Catheter-associated UTI in pregnancy"     # no fluoroquinolone list
    if uti_upper and sub_type == "Pregnancy-associated UTI":
        sub_type = "Pyelonephritis in pregnancy"
    elif uti_upper and sub_type == "Uncomplicated UTI":
        sub_type = "Complicated UTI"
    # v7.1 (IDSA cUTI 2025): male sex alone no longer makes it "complicated";
    # a UTI in a man has its own card (7 days, think of the prostate).
    if (sub_type == "Uncomplicated UTI"
            and str(sex or "").strip().lower() in ("male", "m", "ذكر")):
        sub_type = "UTI in men"
    duration  = syndrome_data["duration"].get(sub_type, "حسب الاستجابة السريرية")
    first = (syndrome_data.get("first_choice_by_sub") or {}).get(
        sub_type, syndrome_data["first_choice"])

    return {
        "syndrome":       syndrome_data["syndrome"],
        "sub_type":       sub_type,
        "first_choice":   first,
        "duration":       duration,
        "escalation":     (syndrome_data.get("escalation_by_sub") or {}).get(
            sub_type, syndrome_data["escalation"]),
        "threshold":      syndrome_data["culture_threshold"],
    }
