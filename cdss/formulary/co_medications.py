# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Co-medication list and canonical names used by the interaction check."""
import re




COMMON_MEDS = [
    "Antacids (مضادات الحموضة)",
    "Warfarin (مضادات التخثر)",
    "NSAIDs (مسكنات الألم)",
    "SSRI (أدوية الاكتئاب)",
    "Valproic acid (مضادات الصرع)",
    # Added on re-review. abx_guidelines.py declares interactions against these
    # classes, but none of them could be SELECTED, so the entries were dead: the
    # rhabdomyolysis warning on fusidic acid + statin, the QT warning on
    # moxifloxacin, the ototoxicity warning on tobramycin + loop diuretic and the
    # methotrexate warning on penicillin could never once have fired in the app.
    "Statins (أدوية الكوليسترول)",
    "QT-prolonging drugs (أدوية تطيل QT)",
    "Methotrexate (ميثوتريكسات)",
    "Iron supplements (مكملات الحديد)",
    "Loop diuretics (Furosemide)",
    "Theophylline (ثيوفيلين)",
    "Neuromuscular blocking agents (مرخيات العضلات)",
    # Added 2026-11-10 (round 2). The same defect as above, found again: these
    # classes are declared in abx_guidelines.py but could not be selected, so
    # TMP-SMX + ACE inhibitor (hyperkalaemia), clarithromycin + colchicine
    # (fatal toxicity), linezolid + MAOI / tramadol (serotonin syndrome) and
    # ciprofloxacin + tizanidine (contraindicated) could never fire.
    "ACE inhibitors (مثبطات ACE)",
    "ARBs (حاصرات الأنجيوتنسين)",
    "Spironolactone (مدر حافظ للبوتاسيوم)",
    "Phenytoin (فينيتوين)",
    "Sulfonylureas (خافضات السكر)",
    "Azathioprine (آزاثيوبرين)",
    "Colchicine (كولشيسين)",
    "Digoxin (ديجوكسين)",
    "Calcium channel blockers (حاصرات الكالسيوم)",
    "Ergot alkaloids (إرجوتامين)",
    "MAOI (مثبطات MAO)",
    "Tramadol / Pethidine (أفيونات سيروتونينية)",
    "Sympathomimetics (سودوإيفيدرين / دوبامين)",
    "Tizanidine (تيزانيدين)",
    "Nephrotoxic drugs (Amphotericin / Cyclosporine / Tacrolimus)",
]

# ── Interaction matching ────────────────────────────────────────────────────
# Matching was exact string equality, and the formulary spells the same class
# two ways -- "Warfarin" on gatifloxacin/moxifloxacin but
# "Warfarin (مضادات التخثر)" on TMP-SMX, metronidazole and ciprofloxacin. Only
# one spelling could ever match the dropdown, so selecting warfarin silently
# missed whichever half of the formulary used the other form. Eleven declared
# interactions were unreachable in total. Compare on a canonical key instead.
_MED_CANON = {
    "antacid": "antacids", "antacids": "antacids",
    "warfarin": "warfarin", "anticoagulant": "warfarin",
    "nsaid": "nsaids", "nsaids": "nsaids",
    "ssri": "ssri", "snri": "ssri", "antidepressant": "ssri",
    "valproic acid": "valproate", "valproate": "valproate",
    "statin": "statins", "statins": "statins",
    "qt-prolonging drugs": "qt", "qt prolonging drugs": "qt",
    "methotrexate": "methotrexate",
    "iron supplements": "iron", "iron": "iron",
    "loop diuretics": "loop_diuretic", "furosemide": "loop_diuretic",
    "theophylline": "theophylline",
    "neuromuscular blocking agents": "nmba",
    "vancomycin": "vancomycin",
    # ── Added 2026-08-01 with the interaction-table fix ───────────────────────
    # A class label in interacts_with only ever fires if the medication the
    # clinician actually typed canonicalises to the same key. "ACE inhibitors"
    # was declared on TMP-SMX and matched nothing, because nobody types "ACE
    # inhibitors" -- they type Lisinopril. The individual generics are what
    # reaches this function, so the class has to be reachable from them.
    "ace inhibitor": "acei", "ace inhibitors": "acei",
    "lisinopril": "acei", "enalapril": "acei", "ramipril": "acei",
    "captopril": "acei", "perindopril": "acei", "quinapril": "acei",
    "arb": "arb", "arbs": "arb",
    "losartan": "arb", "valsartan": "arb", "candesartan": "arb",
    "irbesartan": "arb", "telmisartan": "arb", "olmesartan": "arb",
    "spironolactone": "k_sparing", "eplerenone": "k_sparing",
    "amiloride": "k_sparing", "potassium": "k_sparing",
    "colchicine": "colchicine",
    "digoxin": "digoxin",
    "phenytoin": "phenytoin",
    "azathioprine": "azathioprine", "6-mercaptopurine": "azathioprine",
    "sulfonylurea": "sulfonylurea", "sulfonylureas": "sulfonylurea",
    "glibenclamide": "sulfonylurea", "gliclazide": "sulfonylurea",
    "glimepiride": "sulfonylurea", "glipizide": "sulfonylurea",
    "maoi": "maoi", "monoamine oxidase": "maoi",
    "selegiline": "maoi", "rasagiline": "maoi", "linezolid": "maoi",
    "pethidine": "serotonergic_opioid", "meperidine": "serotonergic_opioid",
    "tramadol": "serotonergic_opioid", "fentanyl": "serotonergic_opioid",
    "sympathomimetics": "sympathomimetic", "pseudoephedrine": "sympathomimetic",
    "dopamine": "sympathomimetic", "adrenaline": "sympathomimetic",
    "epinephrine": "sympathomimetic",
    "tyramine-rich foods": "tyramine", "tyramine": "tyramine",
    "ergot alkaloids": "ergot", "ergotamine": "ergot",
    "calcium channel blockers": "ccb", "amlodipine": "ccb",
    "verapamil": "ccb", "diltiazem": "ccb", "nifedipine": "ccb",
    "atorvastatin": "statins", "simvastatin": "statins",
    "rosuvastatin": "statins", "lovastatin": "statins",
    # ── Added 2026-11-10 (round 2) ────────────────────────────────────────────
    "tizanidine": "tizanidine",
    "nephrotoxic drugs": "nephrotoxic", "nephrotoxic": "nephrotoxic",
    "amphotericin": "nephrotoxic", "cyclosporine": "nephrotoxic",
    "ciclosporin": "nephrotoxic", "tacrolimus": "nephrotoxic",
    "cisplatin": "nephrotoxic",
}

def _canon_med(name: str) -> str:
    """Canonical key for one medication / drug-class label.

    Strips any parenthetical gloss (Arabic or English) and matches the leading
    class name, so "Warfarin" and "Warfarin (مضادات التخثر)" collapse together.
    """
    base = re.split(r"[(\uFF08]", str(name or ""), maxsplit=1)[0].strip().lower()
    if base in _MED_CANON:
        return _MED_CANON[base]
    # FIX 2026-11-10 (round 2): this was a bare substring test in dict order, so
    # "iron" fired inside "spIRONolactone" and "arb" inside "cARBamazepine" --
    # a potassium-sparing diuretic was matched as an iron supplement. Whole
    # words only, longest key first (an optional plural "s" is tolerated).
    for key in sorted(_MED_CANON, key=len, reverse=True):
        if re.search(r"(?<![a-z0-9])" + re.escape(key) + r"s?(?![a-z0-9])", base):
            return _MED_CANON[key]
    return base
