# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Host-safety tables: renal/child ban reasons, neonatal restrictions, hepatic dosing, pregnancy status."""
from typing import Any
from typing import Dict




RENAL_BAN_REASONS = {
    # The threshold in this text said 30 while the engine enforced 45 (EMA/BNF
    # 2025), so the explanation shown to the clinician contradicted the ban that
    # had just fired. Corrected 2026-07-30.
    "nitrofurantoin": (
        "Nitrofurantoin يحتاج وظيفة كلى سليمة ليتركز في البول.\n"
        "عند CrCl < 45 مل/د (EMA/BNF 2025):\n"
        "- لا يصل لتركيز علاجي في البول -> لا يقتل الجرثومة.\n"
        "- يتراكم في الدم -> خطر سُمية رئوية وعصبية.\n"
        "السبب: الدواء يُطرح كلياً عبر الترشيح الكبيبي."
    ),
}

CHILD_BAN_REASONS = {
    "fluoroquinolone": (
        "الفلوروكينولونات قد تؤثر على غضاريف النمو في الأطفال < 18 سنة.\n"
        "تُستخدم فقط عند انعدام البدائل وبقرار متخصص."
    ),
    "tetracycline": (
        "Doxycycline والتتراسيكلينات قد تترسب في العظام والأسنان النامية.\n"
        "قد تسبب تلوينًا دائمًا للأسنان وتأثيرًا على نمو العظام.\n"
        "ممنوعة غالباً تحت 8 سنوات."
    ),
}

ORGANISM_AVOID_CLASS_MAP = {
    "cephalosporins (كل الجيل)": ["cephalosporin"],
    "cephalosporins":            ["cephalosporin"],
    "tetracyclines":             ["tetracycline"],
    "aminoglycosides":           ["aminoglycoside"],
    "carbapenems":               ["carbapenem"],
    "beta-lactams (alone)":      ["penicillin", "cephalosporin", "carbapenem"],
    "beta-lactams":              ["penicillin", "cephalosporin", "carbapenem"],
}

# ═══════════════════════════════════════════════════════════════════════
# HEPATIC DOSING TABLE — defined here (not further down the file) because
# analyze_antibiotics() now ENFORCES it rather than merely annotating it.
# Keeping a table below its only consumer works by accident of module
# execution order; declaring it first makes the dependency explicit.
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# NEONATAL / YOUNG-INFANT CONTRAINDICATIONS
# ----------------------------------------------------------------------
# `child_safe` in abx_guidelines.py is a single boolean covering the whole
# 0-17 range, so three agents with hard NEONATAL contraindications were
# returned as ALLOWED, with no flag at all, for a patient entered as age 0:
#
#   Ceftriaxone   -> bilirubin displacement (kernicterus) and fatal
#                    ceftriaxone-calcium precipitates in neonates
#   TMP-SMX       -> sulfonamide bilirubin displacement, <2 months
#   Nitrofurantoin-> haemolytic anaemia, immature erythrocyte enzymes
#
# The dashboard ALREADY collects `age_months` for under-1s and then throws it
# away (it only seeded the weight default). Threading it through makes the
# thresholds exact instead of banning the whole first year.
#
# Each entry: drug -> (limit_in_months, ban_or_warn, alternative, reason)
# ═══════════════════════════════════════════════════════════════════════
NEONATAL_RESTRICTIONS: Dict[str, Dict[str, Any]] = {
    # Added v6.6 (2026-11-13): the guideline order now puts daptomycin second for
    # MRSA bacteraemia, and nothing stopped it in an infant.
    "Daptomycin": {
        "months": 12, "action": "ban", "alt": "Vancomycin",
        "reason": ("🚫 غير موصى به تحت 12 شهر (Cubicin label: تأثيرات على العضلات والأعصاب "
                   "ظهرت في حديثي الولادة في الدراسات الحيوانية). البديل: Vancomycin."),
    },
    "Ceftriaxone": {
        # WEB-VERIFIED 2026-08-03. The contraindication is TWO-PART, not one
        # age cutoff:
        #   (a) PREMATURE infants — contraindicated up to 41 weeks POSTMENSTRUAL
        #       age (gestational + chronological), which for a 28-week baby runs
        #       to roughly THREE months of chronological age;
        #   (b) TERM neonates (<= 28 days) who are hyperbilirubinaemic or who
        #       receive / are expected to receive IV calcium-containing fluids.
        # Mechanism: bilirubin displacement from albumin (kernicterus) and fatal
        # ceftriaxone-calcium precipitation.
        #
        # This engine holds chronological age only — there is no gestational-age
        # field — so a single postnatal rule cannot express (a). The month ban
        # covers the term neonate exactly; the preterm case is surfaced as a
        # caution through 3 months rather than silently missed, because a
        # 6-week-old ex-28-weeker is still within the contraindication and the
        # engine has no way to know it. Adding a gestational-age input would let
        # this become a hard rule.
        "months": 1, "action": "ban", "alt": "Cefotaxime",
        "preterm_caution_months": 3,
        "reason": ("🚫 يُمنع في حديثي الولادة (≤ 28 يوم): يزيح البيليروبين عن "
                   "الألبومين → خطر kernicterus، ويكوّن راسب قاتل مع محاليل "
                   "الكالسيوم الوريدية. البديل المباشر: Cefotaxime بنفس الطيف. "
                   "(FDA label / BNFc / AAP Red Book 33rd ed.)"),
        "preterm_reason": ("⚠️ **إن كان الرضيع خديجاً**: المنع يمتد حتى عمر ما بعد "
                           "الطمث 41 أسبوعاً (الحملي + الزمني) — أي قد يصل إلى ~3 "
                           "شهور زمنية لمولود 28 أسبوعاً. البرنامج لا يعرف عمر "
                           "الحمل، فتحقّق يدوياً قبل الوصف. وتجنّبه مطلقاً مع أي "
                           "محلول كالسيوم وريدي أو فرط بيليروبين. "
                           "(FDA label / AAP Red Book 33rd ed.)"),
    },
    "Trimethoprim/Sulfamethoxazole": {
        "months": 2, "action": "ban", "alt": "بيتا-لاكتام حسب الحساسية",
        "reason": ("🚫 يُمنع تحت شهرين: السلفوناميد يزيح البيليروبين عن "
                   "الألبومين → kernicterus. (BNFc / AAP Red Book)"),
    },
    "Nitrofurantoin": {
        "months": 3, "action": "ban", "alt": "Cephalexin أو Amoxicillin",
        "reason": ("🚫 يُمنع تحت 3 شهور: أنظمة إنزيمات كرات الدم الحمراء غير "
                   "ناضجة → أنيميا انحلالية. (BNFc / EMA)"),
    },
    "Ciprofloxacin": {
        "months": 1, "action": "warn", "alt": "",
        "reason": ("⚠️ في حديثي الولادة يُستخدم فقط لدواعٍ مهدِّدة للحياة "
                   "وبقرار استشاري."),
    },
}

# ═══════════════════════════════════════════════════════════════════════
# ENGINE 3 -- Hepatic Dosing (Child-Pugh A/B/C)
# BNF 2025 | Lexicomp 2025 | UpToDate 2025
# ═══════════════════════════════════════════════════════════════════════
HEPATIC_DOSING: Dict[str, Dict] = {
    # ── Keys match abx_guidelines.py drug names exactly for lookup to work ──
    # Drugs marked [MDR/REF only] not in active formulary -- kept for reference display.
    "Metronidazole":                 {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment (label) -- monitor for adverse effects"), "C": ("Reduce 50%","Child-Pugh C: reduce the dose by 50% (label)"), "note": "Extensive hepatic metabolism. FIX 2026-11-10: the level string 'Avoid/Reduce' contained 'avoid' and BANNED metronidazole in Child-Pugh C; the label halves the dose"},
    "Clindamycin":                   {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Caution","No fixed reduction -- half-life is prolonged in severe liver disease; monitor liver enzymes (label)"), "note": "Primary hepatic metabolism. FIX 2026-11-10: was 'Avoid' in Child-Pugh C; the label asks for monitoring, not avoidance"},
    "Rifampicin":                    {"A": ("Normal (no jaundice)","Normal if no jaundice"), "B": ("Max 8mg/kg/d","Max 8mg/kg/day; weekly LFTs"), "C": ("Avoid","Avoid -- hepatotoxic + CYP inducer"), "note": "Hepatotoxic + strong CYP inducer [MDR/REF only]"},
    "Erythromycin":                  {"A": ("Normal","No adjustment"), "B": ("Reduce 25%","Reduce dose by 25%"), "C": ("Reduce 50%","Reduce 50% or avoid"), "note": "Cholestatic hepatitis risk [MDR/REF only]"},
    "Ceftriaxone":                   {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment; max 2g/day"), "C": ("Max 2g/day","2g/day maximum -- biliary sludge risk"), "note": "Dual hepatic/renal elimination"},
    "Linezolid":                     {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal","No adjustment -- primarily renal"), "note": "No hepatic dose adjustment required"},
    "Vancomycin":                    {"A": ("Renal-based","AUC/MIC monitoring"), "B": ("Renal-based","AUC/MIC monitoring"), "C": ("Renal-based","AUC/MIC monitoring"), "note": "Primarily renal -- no hepatic adjustment"},
    "Ciprofloxacin":                 {"A": ("Normal","No adjustment"), "B": ("Caution","Use with caution"), "C": ("Caution","No dose adjustment established -- use with caution in severe impairment (label)"), "note": "Partial hepatic metabolism"},
    "Doxycycline":                   {"A": ("Normal","No adjustment"), "B": ("Caution","Use with caution"), "C": ("Avoid","Avoid in severe hepatic failure"), "note": "Biliary excretion pathway"},
    "Amoxicillin + Clavulanic acid": {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Avoid","Avoid -- Clavulanate-associated DILI risk"), "note": "Clavulanate linked to drug-induced liver injury"},
    "Piperacillin + Tazobactam":     {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal (renal)","No hepatic adjustment -- monitor renal"), "note": "Primarily renal elimination"},
    "Tigecycline":                   {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Reduce","100mg loading then 25mg q12h in Child-Pugh C (label; FIX 2026-11-10 — was 12.5mg)"), "note": "Biliary excretion -- adjust in severe impairment [MDR/REF only]"},
    "Colistin":                      {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Renal-based","Based on CrCl -- primarily renal"), "note": "Primarily renal elimination"},
    "Nitrofurantoin":                {"A": ("Normal","No adjustment"), "B": ("Caution","Use with caution"), "C": ("Avoid","Avoid in hepatic failure"), "note": "Cholestatic hepatitis risk"},
    "Chloramphenicol":               {"A": ("Caution","Use with caution"), "B": ("Avoid","Avoid"), "C": ("Avoid","Avoid -- gray syndrome risk"), "note": "Hepatic glucuronidation -- accumulates [MDR/REF only]"},
    "Trimethoprim/Sulfamethoxazole": {"A": ("Normal","No adjustment"), "B": ("Caution","Use with caution"), "C": ("Avoid","Avoid in severe hepatic failure"), "note": "Hepatic acetylation -- accumulates"},
    "Azithromycin":                  {"A": ("Normal","No adjustment"), "B": ("Caution","Monitor LFTs"), "C": ("Avoid","Avoid in severe hepatic failure"), "note": "Biliary excretion -- hepatic impairment increases exposure"},
    "Clarithromycin":                {"A": ("Normal","No adjustment"), "B": ("Caution","Use with caution"), "C": ("Avoid","Avoid -- accumulation + QT risk"), "note": "Hepatic CYP3A4 metabolism"},
    "Meropenem":                     {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Caution","No formal adjustment -- monitor clinically"), "note": "Minimal hepatic metabolism"},
    "Imipenem/Cilastatin":           {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Caution","No formal adjustment -- monitor seizure risk"), "note": "Minimal hepatic metabolism"},
    "Levofloxacin":                  {"A": ("Normal","No adjustment"), "B": ("Caution","Monitor LFTs"), "C": ("Caution","No formal adjustment -- primarily renal; monitor"), "note": "Partial hepatic metabolism -- primarily renal"},
    "Ofloxacin":                     {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal","No hepatic adjustment -- primarily renal"), "note": "Primarily renal elimination"},
    "Norfloxacin":                   {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal","No hepatic adjustment -- primarily renal"), "note": "Primarily renal elimination"},
    "Ertapenem":                     {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal","No hepatic adjustment required"), "note": "Primarily renal elimination"},
    "Ampicillin/Sulbactam":          {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal","No hepatic adjustment -- primarily renal"), "note": "Primarily renal elimination"},
    "Fosfomycin":                    {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal","No hepatic adjustment"), "note": "Primarily renal elimination"},
    "Cephalexin":                    {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal","No hepatic adjustment"), "note": "Primarily renal elimination"},
    "Gentamicin":                    {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal (renal)","Primarily renal -- no hepatic adjustment; monitor nephrotoxicity"), "note": "Primarily renal -- ototoxic + nephrotoxic"},
    "Amikacin":                      {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal (renal)","Primarily renal -- no hepatic adjustment; monitor nephrotoxicity"), "note": "Primarily renal -- ototoxic + nephrotoxic"},
    # ── COVERAGE GAP CLOSED ────────────────────────────────────────────────
    # These nine agents all carry hepatic_caution=True in abx_guidelines.py yet
    # had NO row here, so get_hepatic_recommendations() returned nothing for
    # them and a cirrhotic patient received no hepatic guidance at all on the
    # very drugs the formulary had already flagged as hepatically risky.
    "Tobramycin":                    {"A": ("Normal","No adjustment"), "B": ("Normal","No adjustment"), "C": ("Normal (renal)","Primarily renal -- no hepatic adjustment; monitor nephrotoxicity"), "note": "Primarily renal -- ototoxic + nephrotoxic"},
    "Moxifloxacin":                  {"A": ("Normal","No adjustment"), "B": ("Caution","Monitor LFTs; withdraw if transaminases rise"), "C": ("Avoid","CONTRAINDICATED in Child-Pugh C (EMA/FDA label) and if ALT/AST >5x ULN"), "note": "Hepatic metabolism with no renal escape route; highest fulminant-hepatitis signal of the fluoroquinolones"},
    "Gatifloxacin":                  {"A": ("Normal","No adjustment"), "B": ("Caution","Monitor LFTs and glucose"), "C": ("Avoid","Avoid -- hepatic metabolism plus dysglycaemia risk"), "note": "Hepatic metabolism; withdrawn in several markets for dysglycaemia"},
    "Tetracycline":                  {"A": ("Caution","Use with caution"), "B": ("Avoid","Avoid"), "C": ("Avoid","Avoid -- dose-related hepatotoxicity, microvesicular steatosis"), "note": "Fatal fatty liver reported with high/IV doses; the most hepatotoxic tetracycline"},
    "Minocycline":                   {"A": ("Normal","No adjustment"), "B": ("Caution","Monitor LFTs"), "C": ("Avoid","Avoid -- autoimmune hepatitis and DRESS reported"), "note": "Hepatic metabolism; idiosyncratic autoimmune hepatitis on prolonged use"},
    "Tinidazole":                    {"A": ("Normal","No adjustment"), "B": ("Reduce 50%","Reduce dose by 50%"), "C": ("Avoid","Avoid -- extensive CYP3A4 metabolism, accumulation"), "note": "Extensive hepatic metabolism (mirrors Metronidazole but longer half-life)"},
    "Oxacillin":                     {"A": ("Normal","No adjustment"), "B": ("Caution","Monitor LFTs; consider Cefazolin instead"), "C": ("Avoid","Avoid -- prefer Cefazolin (less hepatotoxic, equal MSSA efficacy)"), "note": "Dose-related cholestatic hepatitis, especially >8 g/day"},
    "Fusidic acid":                  {"A": ("Caution","Monitor LFTs"), "B": ("Avoid","Avoid"), "C": ("Avoid","Avoid -- biliary excretion, dose-dependent jaundice"), "note": "Biliary excretion; hyperbilirubinaemia and cholestasis are common, worse with statin co-administration"},
    "Cefoperazone":                  {"A": ("Normal","No adjustment"), "B": ("Caution","Max 4 g/day; monitor INR, give vitamin K"), "C": ("Avoid","Avoid -- max 2 g/day if unavoidable; biliary obstruction abolishes the main clearance route"), "note": "~70% biliary excretion; NMTT side chain causes hypoprothrombinaemia and bleeding"},
    "Cefoperazone + Sulbactam":      {"A": ("Normal","No adjustment"), "B": ("Caution","Max 4 g/day cefoperazone component; monitor INR, give vitamin K"), "C": ("Avoid","Avoid -- max 2 g/day if unavoidable"), "note": "~70% biliary excretion; NMTT side chain causes hypoprothrombinaemia and bleeding"},
}

# ═══════════════════════════════════════════════════════════════════════
# SIR NORMALISATION — the single entry point for every S/I/R value
# ----------------------------------------------------------------------
# Every engine in this file compares with `== "R"` / `in ("R","I")`. Nothing
# validated the values, and the interactive editor coerced anything it did not
# recognise straight to "S":
#
#     if cur not in sir_options: cur = "S"        <-- fail-OPEN
#
# so a lowercase "r", a trailing space, or the word "Resistant" arriving from
# OCR, a pasted table or a future JSON import made a RESISTANT drug come back
# ALLOWED. The Streamlit selectbox happens to constrain the values today, which
# is the only reason this has not fired in production; it is one import feature
# away from doing so.
#
# SDD (Susceptible-Dose Dependent) is a real CLSI M100 category -- cefepime vs
# Enterobacterales is the everyday example -- and was silently read as plain S,
# i.e. standard dosing for a result that explicitly requires a high-dose
# regimen. It maps to "I" so the existing increased-exposure warning fires.
#
# NS (non-susceptible) maps to R: it is the conservative direction and the only
# one that cannot cost a patient a failed therapy.
# ═══════════════════════════════════════════════════════════════════════






# ── Pregnancy status: canonicalise the enum ─────────────────────────────────
# abx_guidelines.py declares four distinct values -- Safe / Warn / Banned and,
# on Aztreonam alone, "Caution". Every consumer tested only for "Banned" and
# "Warn", so "Caution" fell through every branch and the drug reached a pregnant
# patient with no flag at all -- indistinguishable from Safe. An undocumented
# fourth value silently meaning "Safe" is exactly the drift a clinical table
# must not tolerate.
_PREG_ALIASES = {
    "SAFE": "Safe", "": "Safe", "NONE": "Safe",
    "WARN": "Warn", "CAUTION": "Warn", "WARNING": "Warn", "MONITOR": "Warn",
    "BANNED": "Banned", "CONTRAINDICATED": "Banned", "AVOID": "Banned",
}

def preg_status_of(info: Dict[str, Any]) -> str:
    """Canonical Safe | Warn | Banned for one formulary entry.

    Unknown values fail CLOSED to "Warn": an unrecognised label must raise a
    flag, never suppress one.
    """
    raw = str(info.get("preg_status") or "").strip().upper()
    return _PREG_ALIASES.get(raw, "Warn")
