# -*- coding: utf-8 -*-
# © Dr. Hussein Ali — Orange Lab, 6 October City, Egypt
# Microbiology CDSS — All Rights Reserved
"""English renderings for the English PDF.

Split out of report_service.py (v6.7, 2026-11-14). The English report must
never carry an Arabic word; report_service's last-resort net replaces any text
node that still holds Arabic with "A clinical note for this item is available
in the Arabic report." -- correct as a guarantee, useless as content. Everything
here exists so that net does not have to fire:

    PREG_NOTE_AR_EN   phrase table for Arabic pregnancy notes (was _AR_EN)
    PATHO_AR_EN       phrase table for Arabic pathogenicity text (was _PATHO_EN)
    alert_en()        the therapy engine's Arabic side alerts (co-medication
                      interactions, hepatic caution) rebuilt in English

The two tables moved byte-for-byte; their ORDER matters (longer phrases are
listed before the shorter ones they contain) and is preserved.
"""
import re
from typing import Dict

from cdss.formulary.interaction_effects import HEPATIC_CAUTION_EN
from cdss.formulary.interaction_effects import interaction_alert

PREG_NOTE_AR_EN: Dict[str, str] = {
    "ممنوع في الحمل":                   "Contraindicated in pregnancy",
    "تحذير حمل":                         "Pregnancy caution",
    "مقبول في الحمل":                    "Acceptable in pregnancy",
    "آمن في الـ":                        "Safe in",
    "تجنّب في الـ":                      "Avoid in",
    "تجنّب":                             "Avoid",
    "يترسّب في عظام وأسنان الجنين":      "chelates into fetal bone and teeth",
    "تصبغ دائم للأسنان":                "permanent tooth discoloration",
    "تثبيط نمو العظام":                 "inhibited bone growth",
    "محظورة في كل مراحل الحمل":          "contraindicated throughout all trimesters",
    "خاصة بعد الأسبوع":                 "especially after week",
    "البديل":                           "Alternative",
    "بيانات بشرية محدودة":              "limited human data",
    "يعبر المشيمة":                     "crosses placenta",
    "سُمية للأذن الجنينية":             "fetal ototoxicity",
    "فقدان سمع دائم":                   "permanent hearing loss",
    "مضاد حمض الفوليك":                 "folate antagonist",
    "عيوب أنبوب عصبي":                  "neural tube defects",
    "يُفضل تجنبه":                      "prefer to avoid",
    "إن وُجد بديل آمن":                 "if a safer alternative exists",
    "مقبول في كل":                      "acceptable throughout all",
    "عند الضرورة":                      "when medically necessary",
    "القرار النهائي للطبيب المعالج":     "Final decision: treating physician",
    "حصراً":                            "exclusively",
    "خطر":                              "risk of",
    "خطر hemolytic anemia في الجنين":   "risk of fetal hemolytic anemia (G6PD)",
    "نيونيتل hemolysis عند الوليد":     "neonatal hemolysis",
    "البديل في 3rd trim":               "Alternative in 3rd trim",
    "جرعة واحدة":                       "(single dose)",
    "الأدلة الحديثة":                   "Recent evidence",
    "دحضت مخاوف":                       "refuted concerns about",
    "التشوهات القديمة":                 "historical malformation risk",
    "يُفضل تجنبه في الـ 1st trimester": "prefer to avoid in 1st trimester",
    "ارتبط بتشوهات خلقية":              "associated with congenital malformations",
    "الدراسات الحيوانية والبشرية":       "in animal and human studies",
    "أثبت سُمية جنينية في الحيوانات":   "demonstrated fetal toxicity in animal studies",
    "يُستخدم فقط عند انعدام البدائل":    "use only when no alternatives available",
    "يُستخدم عند الضرورة القصوى":        "use only when critically necessary",
    "مراقبة وظائف الكلى":               "monitor renal function",
    "السمع للأم والجنين":                "and fetal/maternal hearing",
    "Category C":                        "Category C",
    "Category B":                        "Category B",
    "عند الحاجة لكاربابينيم":           "when a carbapenem is needed",
    "يُفضل Meropenem":                  "Meropenem preferred",
    "عند تعذّر Meropenem":              "if Meropenem is unavailable",
    "nephrotoxicity":                    "nephrotoxicity",
    "يُستخدم فقط لإنقاذ الحياة":        "life-saving use only",
    "في XDR gram-negatives":            "for XDR gram-negative infections",
    "غياب أي بديل":                     "when no alternative exists",
    "تجنّب ما أمكن":                    "avoid whenever possible",
    "تجنّب في الـ 3rd trimester":        "avoid in 3rd trimester",
    "≥36 أسبوع":                        "≥36 weeks gestation",
    "ممنوع في الـ 1st trimester":        "contraindicated in 1st trimester",
    "ممنوع في كل الحمل":                "contraindicated throughout pregnancy",
    "لا يُعتبر خطاً أول":               "not a first-line agent",
    "أبداً في الحمل":                    "at any point in pregnancy",
    "خطر التشوهات أقل مما كان يُعتقد":  "teratogenicity risk lower than previously thought",
    "لا يُستخدم كخط أول":               "do not use as first-line",
    "فقط عند غياب البديل الأكثر أمانًا": "only when no safer alternative exists",
    "مقبول بجرعة واحدة":                "acceptable as single dose",
    "لـ uncomplicated UTI في الحمل":    "for uncomplicated UTI in pregnancy",
    "خيار مفضل على Nitrofurantoin":     "preferred over Nitrofurantoin",
    "1st trim":                          "1st trimester",
    "2nd trim":                          "2nd trimester",
    "3rd trim":                          "3rd trimester",
    "trimester":                         "trimester",
}


PATHO_AR_EN: Dict[str, str] = {
    # Organism name carrying an Arabic parenthetical (EN report → Latin only)
    "Anaerobes (لاهوائيات)": "Anaerobes",
    "(لاهوائيات)": "",
    # Contaminant-tier interpretations / recommendations (were leaking Arabic)
    "يُنصح بإعادة أخذ العينة بتقنية صحيحة قبل البدء بالعلاج.":
        "Repeat specimen collection with proper technique before starting treatment.",
    "أعِد أخذ العينة مع تحسين التقنية.":
        "Repeat specimen collection with improved technique.",
    "لا تبدأ العلاج بناءً على هذه النتيجة وحدها.":
        "Do NOT start treatment based on this result alone.",
    "إذا تكرر العزل، فكّر في مصدر بديل (Hematogenous / Device).":
        "If the isolate recurs, consider an alternative source (Hematogenous / Device).",
    "المؤشرات تدعم التلوث أو الاستعمار بشكل كبير. العلاج غير مبرر في الغالب. تابع المريض كلينيكياً.":
        "Indicators strongly support contamination or colonization. Treatment is usually not justified. Follow up the patient clinically.",
    "لا تعطِ مضادات حيوية بناءً على هذه النتيجة.":
        "Do NOT give antibiotics based on this result.",
    "التزم بمبادئ Antibiotic Stewardship.":
        "Adhere to Antibiotic Stewardship principles.",
    "المؤشرات تدعم بقوة وجود عدوى حقيقية. يُنصح بالعلاج الموجَّه بنتيجة الحساسية مع مراعاة السياق الكلينيكي.":
        "Strong indicators of TRUE INFECTION. Culture-directed therapy is recommended, considering the clinical context.",
    "المؤشرات تدعم بقوة وجود عدوى حقيقية":
        "Strong indicators of true infection",
    "يُنصح بالعلاج الموجَّه بنتيجة الحساسية مع مراعاة السياق الكلينيكي":
        "Culture-directed therapy recommended based on clinical context",
    "ابدأ العلاج بناءً على نتيجة الـ AST.":
        "Initiate therapy based on AST results.",
    "ابدأ العلاج بناءً على نتيجة الـ AST":
        "Initiate therapy based on AST results",
    "راعِ شدة الأعراض وعوامل الخطر.":
        "Consider symptom severity and risk factors.",
    "راعِ شدة الأعراض وعوامل الخطر":
        "Consider severity and risk factors",
    "راجع الجرعة حسب الوظيفة الكلوية.":
        "Review dosing based on renal function.",
    "راجع الجرعة حسب الوظيفة الكلوية":
        "Review dosing based on renal function",
    "De-escalate بعد 48–72 ساعة إذا تحسّن المريض.":
        "De-escalate after 48–72 hours if patient improves.",
    "النتيجة حدودية. يُنصح بالتقييم الكلينيكي الكامل قبل البدء بالعلاج.":
        "Borderline result. Full clinical assessment recommended before initiating treatment.",
    "قد تحتاج فحوصات إضافية أو إعادة المزرعة.":
        "Additional workup or repeat culture may be needed.",
    "لا يُنصح بالعلاج إلا في الحامل أو قبل تدخل جراحي بولي.":
        "Treatment not recommended unless patient is pregnant or pre-urological procedure.",
    "المؤشرات تميل نحو التلوث أو الاستعمار.":
        "Indicators suggest contamination or colonization.",
    "ABU في سياق يستوجب العلاج (حمل / تدخل جراحي بولي).":
        "Asymptomatic Bacteriuria requiring treatment (pregnancy / pre-op).",
    "اختر مضاداً حيوياً مناسباً للحمل حسب نتيجة الحساسية.":
        "Select a pregnancy-appropriate antibiotic per sensitivity results.",
    "مدة العلاج 5–7 أيام عادةً.":
        "Treatment duration typically 5–7 days.",
    "أعِد المزرعة بعد الانتهاء من الدورة للتأكد من الشفاء.":
        "Repeat culture post-treatment to confirm clearance.",
    "العينة غير مناسبة":
        "Specimen inadequate",
    "ارفض العينة وأعِد طلب البلغم بتقنية صحيحة.":
        "Reject specimen and request repeat sputum with proper technique.",
    "قيّم المريض كلينيكياً قبل إعطاء المضادات الحيوية.":
        "Assess the patient clinically before giving antibiotics.",
    "فكّر في إعادة المزرعة إذا كان الوضع غير واضح.":
        "Consider repeating the culture if the situation is unclear.",
    "راجع نتيجة الـ Urinalysis / CRP / CBC إذا لم تكن متاحة.":
        "Review Urinalysis / CRP / CBC results if not available.",
    "النتيجة حدودية. يُنصح بالتقييم الكلينيكي الكامل قبل البدء بالعلاج. قد تحتاج فحوصات إضافية أو إعادة المزرعة.":
        "Borderline result. Full clinical assessment is recommended before starting treatment. Additional tests or repeat culture may be needed.",
    "أعِد تقييم المريض إذا استمرت الأعراض أو تطورت.":
        "Re-evaluate the patient if symptoms persist or progress.",
    "ابدأ العلاج التجريبي فوراً ريثما تظهر نتيجة الحساسية.":
        "Start empiric therapy immediately pending sensitivity results.",
    "احتجز المريض ومراقبته بشكل مكثف.":
        "Admit the patient for intensive monitoring.",
    "استثناءات: حمل -- قبيل جراحة بولية (Urology pre-op).":
        "Exceptions: pregnancy / pre-urological surgery.",
    "استشر طبيب الأمراض المعدية.":
        "Consult an infectious disease specialist.",
    "العينة من موقع معقم (CSF) -- أي نمو يُعدّ مرضياً بغض النظر عن العوامل الأخرى.":
        "Specimen from a sterile site (CSF) -- any growth is pathogenic regardless of other factors.",
    "تابع المريض وأعِد التقييم إذا ظهرت أعراض.":
        "Follow up and reassess if symptoms appear.",
    "تشير المعطيات إلى Asymptomatic Bacteriuria. وفقاً لـ IDSA 2019: لا يُنصح بالعلاج إلا في الحامل أو قبل تدخل جراحي بولي.":
        "Findings indicate Asymptomatic Bacteriuria. Per IDSA 2019: treatment not recommended except in pregnancy or before a urological procedure.",
    "لا تعطِ مضادات حيوية (Antibiotic Stewardship -- IDSA 2019).":
        "Do NOT give antibiotics (Antibiotic Stewardship -- IDSA 2019).",
}


_INTERACTION_AR = re.compile(r"^⚡ تعارض: (?P<drug>.+?) مع (?P<med>.+?)(?: — .*)?$", re.S)
_HEPATIC_AR = re.compile(r"^🏥 تحذير كبدي: (?P<drug>.+?) — ", re.S)


def alert_en(text: str) -> str:
    """One engine side alert in English.

    The alert list is a list of strings by the time it reaches the renderer
    (it travels through the UI state), so the English form is rebuilt from the
    two names the Arabic one carries -- the effect text then comes from the
    same table that wrote the Arabic, so the two cannot disagree. An alert this
    function does not recognise is returned unchanged.
    """
    s = str(text or "")
    m = _INTERACTION_AR.match(s)
    if m:
        return interaction_alert(m.group("drug").strip(), m.group("med").strip(), "en")
    m = _HEPATIC_AR.match(s)
    if m:
        return HEPATIC_CAUTION_EN.format(drug=m.group("drug").strip())
    return s
