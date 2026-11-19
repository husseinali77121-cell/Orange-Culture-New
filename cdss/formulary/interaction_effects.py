# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""What a declared co-medication interaction DOES, and what to do about it.

Added v6.7 (2026-11-14). Until now the interaction alert was the bare pair --
"⚡ تعارض: Ciprofloxacin مع Warfarin" -- which tells the prescriber that
something is wrong but not what (a higher INR? a lower one? a seizure?) or
what to do. The effect is the clinical content; the pair is only the trigger.

Keyed on the canonical co-medication (co_medications._canon_med), because the
formulary declares the interaction by co-medication class. Where the same
co-medication behaves differently with different antibiotics (a statin with
fusidic acid vs with daptomycin; methotrexate with TMP-SMX vs a penicillin)
the antibiotic-specific text wins.

Sources: BNF 2025 Appendix 1 (interactions), Stockley's Drug Interactions,
product labels (FDA / EMA SmPC), MHRA Drug Safety Update (fusidic acid +
statins, 2012).

Each value is (Arabic, English). Both are complete sentences: the English one
is what the English PDF prints, so it must never be a fragment.
"""
from typing import Dict, Optional, Tuple

from cdss.formulary.co_medications import _canon_med

# canonical co-medication -> (ar, en)
INTERACTION_EFFECTS: Dict[str, Tuple[str, str]] = {
    "warfarin": (
        "يزيد مفعول الوارفارين (↑ INR وخطر نزيف) — قِس INR خلال 3-5 أيام من البدء وبعد الإيقاف.",
        "Increases the anticoagulant effect (↑ INR, bleeding risk) — check the INR within 3–5 days "
        "of starting and again after stopping."),
    "qt": (
        "إطالة QT إضافية → خطر Torsades — ECG قبل البدء، صحّح K/Mg، وتجنّب لو QTc > 500 ms.",
        "Additive QT prolongation (torsades risk) — baseline ECG, correct K⁺/Mg²⁺, avoid if "
        "QTc > 500 ms."),
    "antacids": (
        "يقلّل الامتصاص (ارتباط بالمعادن) — أعطِ المضاد الحيوي قبل مضاد الحموضة بساعتين على الأقل "
        "أو بعده بـ 4-6 ساعات.",
        "Reduced absorption (chelation by Al/Mg/Ca) — give the antibiotic at least 2 h before or "
        "4–6 h after the antacid."),
    "iron": (
        "يقلّل الامتصاص (ارتباط بالحديد) — أعطِ المضاد الحيوي قبل الحديد بساعتين على الأقل أو بعده "
        "بـ 4-6 ساعات.",
        "Reduced absorption (chelation by iron) — give the antibiotic at least 2 h before or "
        "4–6 h after the iron."),
    "methotrexate": (
        "يقلّل إخراج الميثوتريكسات → سمية (تثبيط نخاع، التهاب أغشية) — راقب CBC ووظائف الكلى "
        "ومستوى MTX، خاصة مع الجرعات العالية.",
        "Reduces methotrexate clearance (marrow suppression, mucositis) — monitor CBC, renal "
        "function and MTX levels, especially with high-dose MTX."),
    "loop_diuretic": (
        "سمية سمعية وكلوية إضافية — راقب المستوى والكرياتينين والسمع، وتجنّب الجرعات العالية من "
        "الـ Furosemide.",
        "Additive oto- and nephrotoxicity — monitor drug levels, creatinine and hearing; avoid "
        "high-dose furosemide."),
    "nephrotoxic": (
        "سمية كلوية إضافية — راقب المستوى والكرياتينين يومياً، وأوقف أحد الدواءين إن أمكن.",
        "Additive nephrotoxicity — monitor drug levels and creatinine daily; stop one of the "
        "two if possible."),
    "nsaids": (
        "سمية كلوية إضافية — تجنّب الـ NSAIDs أثناء العلاج إن أمكن وراقب الكرياتينين.",
        "Additive nephrotoxicity — avoid NSAIDs during treatment if possible and monitor "
        "creatinine."),
    "nmba": (
        "يطيل الإحصار العصبي العضلي → توقف تنفس مطوّل — راقب الوظيفة العصبية العضلية حول العملية.",
        "Potentiates neuromuscular blockade (prolonged apnoea) — monitor neuromuscular function "
        "peri-operatively."),
    "theophylline": (
        "يقلّل تصفية الثيوفيلين → سمية (تشنجات، اضطراب نظم) — راقب المستوى أو خفّض جرعة الثيوفيلين.",
        "Reduces theophylline clearance (seizures, arrhythmia) — monitor theophylline levels or "
        "reduce its dose."),
    "valproate": (
        "الكاربابينيم يخفض مستوى الـ Valproate بنسبة 60-100% خلال 24 ساعة → تشنجات، ولا يُعوَّض "
        "برفع جرعة الـ Valproate — تجنّب الجمع: اختر مضاداً غير كاربابينيم أو مضاد صرع آخر.",
        "Carbapenems lower valproate levels by 60–100 % within 24 h (breakthrough seizures), and "
        "raising the valproate dose does not overcome it — avoid the combination: use a "
        "non-carbapenem or a different anticonvulsant."),
    "acei": (
        "Trimethoprim يرفع البوتاسيوم (يثبط ENaC) → فرط بوتاسيوم — قِس K خلال 3-5 أيام، خاصة "
        "لكبار السن والقصور الكلوي.",
        "Trimethoprim raises potassium (ENaC blockade) — check K⁺ within 3–5 days, especially in "
        "the elderly or in CKD."),
    "arb": (
        "Trimethoprim يرفع البوتاسيوم (يثبط ENaC) → فرط بوتاسيوم — قِس K خلال 3-5 أيام، خاصة "
        "لكبار السن والقصور الكلوي.",
        "Trimethoprim raises potassium (ENaC blockade) — check K⁺ within 3–5 days, especially in "
        "the elderly or in CKD."),
    "k_sparing": (
        "Trimethoprim يرفع البوتاسيوم (يثبط ENaC) → فرط بوتاسيوم خطير — قِس K خلال 3-5 أيام.",
        "Trimethoprim raises potassium (ENaC blockade) — serious hyperkalaemia; check K⁺ within "
        "3–5 days."),
    "phenytoin": (
        "يرفع مستوى الـ Phenytoin (تثبيط CYP2C9) — راقب المستوى وعلامات السمية.",
        "Raises phenytoin levels (CYP2C9 inhibition) — monitor levels and signs of toxicity."),
    "sulfonylurea": (
        "خطر هبوط سكر — راقب السكر عن قرب أثناء العلاج.",
        "Risk of hypoglycaemia — monitor blood glucose closely during treatment."),
    "azathioprine": (
        "تثبيط نخاع إضافي — راقب CBC، وتجنّب الجمع إن أمكن.",
        "Additive bone-marrow suppression — monitor CBC; avoid the combination if possible."),
    "colchicine": (
        "تثبيط CYP3A4/P-gp → سمية الكولشيسين (حالات وفاة) — ممنوع مع قصور كلوي أو كبدي؛ "
        "غير ذلك خفّض جرعة الكولشيسين أو استخدم Azithromycin.",
        "CYP3A4/P-gp inhibition causes colchicine toxicity (fatal cases) — contraindicated in "
        "renal or hepatic impairment; otherwise reduce the colchicine dose or use azithromycin."),
    "digoxin": (
        "تثبيط P-gp يرفع مستوى الديجوكسين → سمية — راقب المستوى.",
        "P-gp inhibition raises digoxin levels (toxicity) — monitor digoxin levels."),
    "ccb": (
        "تثبيط CYP3A4 يرفع مستوى حاصر الكالسيوم → هبوط ضغط وقصور كلوي حاد (كبار السن) — "
        "يُفضّل Azithromycin.",
        "CYP3A4 inhibition raises the calcium-channel blocker (hypotension, acute kidney injury "
        "in the elderly) — prefer azithromycin."),
    "ergot": (
        "تسمم إرجوتي (تقلّص وعائي حاد وإقفار) — ممنوع الجمع.",
        "Ergotism (acute vasospasm and ischaemia) — contraindicated."),
    "maoi": (
        "Linezolid نفسه مثبط MAO — ممنوع مع مثبط MAO أو خلال أسبوعين من إيقافه (متلازمة سيروتونين "
        "/ أزمة ضغط).",
        "Linezolid is itself a reversible MAO inhibitor — contraindicated with an MAOI or within "
        "2 weeks of stopping one (serotonin syndrome, hypertensive crisis)."),
    "ssri": (
        "خطر متلازمة السيروتونين — تجنّب أو راقب عن قرب (هياج، حرارة، رعشة عضلية)، وأوقف الدواء "
        "السيروتونيني إن أمكن.",
        "Risk of serotonin syndrome — avoid, or monitor closely (agitation, hyperthermia, "
        "clonus); stop the serotonergic drug if possible."),
    "serotonergic_opioid": (
        "خطر متلازمة السيروتونين — تجنّب أو راقب عن قرب، واختر مسكناً غير سيروتونيني.",
        "Risk of serotonin syndrome — avoid, or monitor closely; choose a non-serotonergic "
        "analgesic."),
    "sympathomimetic": (
        "يزيد الاستجابة الضاغطة (ارتفاع ضغط) — تجنّب، أو ابدأ الضاغط بجرعة منخفضة مع مراقبة الضغط.",
        "Enhanced pressor response (hypertensive reaction) — avoid, or start the pressor at a "
        "low dose with blood-pressure monitoring."),
    "tyramine": (
        "أزمة ارتفاع ضغط — تجنّب الأطعمة الغنية بالتيرامين (الأجبان المعتّقة، اللحوم المصنّعة، "
        "المخللات) أثناء العلاج.",
        "Hypertensive reaction — avoid tyramine-rich foods (aged cheese, cured meats, fermented "
        "products) during treatment."),
    "tizanidine": (
        "تثبيط CYP1A2 يرفع الـ Tizanidine ~10 أضعاف → هبوط ضغط شديد ونعاس — ممنوع الجمع.",
        "CYP1A2 inhibition raises tizanidine about ten-fold (severe hypotension, sedation) — "
        "contraindicated."),
    "statins": (
        "تثبيط CYP3A4 يرفع الـ statin → اعتلال عضلي/انحلال عضلات — أوقف Simvastatin/Lovastatin/"
        "Atorvastatin أثناء الكورس أو استخدم Azithromycin.",
        "CYP3A4 inhibition raises the statin (myopathy, rhabdomyolysis) — hold simvastatin / "
        "lovastatin / atorvastatin during the course, or use azithromycin."),
}

# (canonical co-medication, substring of the antibiotic name in lower case) -> (ar, en)
# Checked before INTERACTION_EFFECTS: the same co-medication, a different effect.
DRUG_SPECIFIC_EFFECTS: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("statins", "fusidic"): (
        "Fusidic acid + statin: انحلال عضلات (حالات وفاة) — أوقف الـ statin طول العلاج وارجع له "
        "بعد 7 أيام من آخر جرعة Fusidic acid (MHRA).",
        "Fusidic acid with a statin causes rhabdomyolysis (fatal cases) — stop the statin for the "
        "whole course and restart 7 days after the last fusidic acid dose (MHRA)."),
    ("statins", "daptomycin"): (
        "اعتلال عضلي إضافي — فكّر في إيقاف الـ statin مؤقتاً وقِس CPK أسبوعياً (label).",
        "Additive myopathy — consider pausing the statin and check CPK weekly (label)."),
    ("methotrexate", "trimethoprim"): (
        "TMP-SMX مضاد فولات إضافي ويقلّل إخراج الـ MTX → تثبيط نخاع شامل (حالات وفاة) — تجنّب الجمع.",
        "TMP-SMX is an additive antifolate and reduces MTX clearance (pancytopenia, fatal cases) — "
        "avoid the combination."),
    ("sulfonylurea", "gatifloxacin"): (
        "اضطراب سكر (هبوط أو ارتفاع) — راقب السكر عن قرب أو تجنّب.",
        "Dysglycaemia (hypo- or hyperglycaemia) — monitor blood glucose closely or avoid."),
    ("antacids", "nitrofurantoin"): (
        "Magnesium trisilicate يقلّل امتصاص الـ Nitrofurantoin — افصل بينهما ساعتين على الأقل.",
        "Magnesium trisilicate reduces nitrofurantoin absorption — separate the doses by at "
        "least 2 h."),
    ("antacids", "cefuroxime"): (
        "مضادات الحموضة تقلّل امتصاص الـ Cefuroxime axetil — يؤخذ مع الأكل، وافصل ساعتين.",
        "Antacids reduce cefuroxime axetil absorption — take with food and separate by 2 h."),
    # v6.9 (decision D5) -- from the product labels.
    ("valproate", "pivmecillinam"): (
        "الـ pivalate يستنزف الكارنيتين، والـ Valproate كذلك → نقص كارنيتين (هبوط سكر، ضعف عضلات، "
        "تشوش) — تجنّب الجمع، وإن لزم راقب أعراض نقص الكارنيتين (Pivya label).",
        "Pivalate and valproate both deplete carnitine (hypoglycaemia, myopathy, confusion) — "
        "avoid the combination; if unavoidable, monitor for carnitine depletion (Pivya label)."),
    ("methotrexate", "pivmecillinam"): (
        "البنسلينات تقلّل إخراج الميثوتريكسات → سمية — فضّل بديلاً، وإلا راقب CBC والكلى ومستوى MTX.",
        "Penicillins reduce methotrexate clearance (toxicity) — prefer an alternative; otherwise "
        "monitor CBC, renal function and MTX levels."),
    ("nsaids", "sulopenem"): (
        "الـ Probenecid في Orlynvah: ممنوع مع Ketorolac، ولا يُنصح مع Ketoprofen، ويرفع مستوى "
        "Indomethacin و Naproxen — اختر مسكناً آخر (Paracetamol).",
        "The probenecid in Orlynvah: ketorolac is contraindicated, ketoprofen not recommended, "
        "and indomethacin / naproxen levels rise — use another analgesic (paracetamol)."),
    ("methotrexate", "sulopenem"): (
        "الـ Probenecid يثبط OAT1/3 فيرفع الميثوتريكسات — راقب السمية عن قرب (Orlynvah label).",
        "Probenecid inhibits OAT1/3 and raises methotrexate levels — monitor closely for "
        "toxicity (Orlynvah label)."),
    ("sulfonylurea", "sulopenem"): (
        "الـ Probenecid يرفع مستوى السلفونيل يوريا → هبوط سكر — راقب السكر (Orlynvah label).",
        "Probenecid raises sulfonylurea levels (hypoglycaemia) — monitor blood glucose "
        "(Orlynvah label)."),
    ("qt", "gepotidacin"): (
        "إطالة QTc إضافية (Gepotidacin يطيل QTc بشكل معتمد على التركيز) — تجنّب الجمع (Blujepa "
        "label)؛ إن تعذّر: صحّح K/Mg وراقب ECG.",
        "Additive QTc prolongation (gepotidacin prolongs QTc in a concentration-dependent way) — "
        "avoid the combination (Blujepa label); if unavoidable, correct K⁺/Mg²⁺ and monitor the ECG."),
    ("digoxin", "gepotidacin"): (
        "يرفع تعرّض الـ Digoxin — قِس مستوى الديجوكسين (Blujepa label).",
        "Increases digoxin exposure — monitor serum digoxin (Blujepa label)."),
    ("nmba", "gepotidacin"): (
        "Gepotidacin يثبط acetylcholinesterase: يطيل مفعول الـ succinylcholine ويعاكس المرخيات غير "
        "المزيلة للاستقطاب — راقب الوظيفة العصبية العضلية (Blujepa label).",
        "Gepotidacin inhibits acetylcholinesterase: it prolongs succinylcholine and antagonises "
        "non-depolarising blockers — monitor neuromuscular function (Blujepa label)."),
    ("antacids", "cefaclor"): (
        "مضادات الحموضة تقلّل امتصاص الـ Cefaclor — افصل ساعتين على الأقل.",
        "Antacids reduce cefaclor absorption — separate the doses by at least 2 h."),
}

_GENERIC = (
    "تداخل دوائي مسجّل — راجع الجرعة والمتابعة مع الصيدلي.",
    "Documented drug interaction — review the dose and monitoring with the pharmacist.")


def interaction_effect(drug: str, med: str, lang: str = "ar") -> str:
    """The effect sentence for antibiotic `drug` given with co-medication `med`."""
    canon = _canon_med(med)
    low = (drug or "").lower()
    pair: Optional[Tuple[str, str]] = None
    for (c, token), text in DRUG_SPECIFIC_EFFECTS.items():
        if c == canon and token in low:
            pair = text
            break
    if pair is None:
        pair = INTERACTION_EFFECTS.get(canon, _GENERIC)
    return pair[1] if (lang or "ar").lower().startswith("en") else pair[0]


def med_label_en(med: str) -> str:
    """The Latin part of a co-medication label: "Warfarin (مضادات التخثر)" -> "Warfarin"."""
    s = str(med or "")
    head = s.split("(", 1)[0].strip()
    return head or s.strip()


def interaction_alert(drug: str, med: str, lang: str = "ar") -> str:
    """One alert line: the pair AND what it does."""
    if (lang or "ar").lower().startswith("en"):
        # "with", not "+": drug names carry "+" themselves (Amoxicillin + Clavulanic acid).
        return f"⚡ Interaction: {drug} with {med_label_en(med)} — {interaction_effect(drug, med, 'en')}"
    return f"⚡ تعارض: {drug} مع {med} — {interaction_effect(drug, med, 'ar')}"


HEPATIC_CAUTION_AR = "🏥 تحذير كبدي: {drug} — يحتاج متابعة أو تعديل حسب الحالة."
HEPATIC_CAUTION_EN = ("🏥 Hepatic caution: {drug} — needs monitoring or dose adjustment for the "
                      "degree of liver impairment.")
