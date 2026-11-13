# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Ranking of the susceptible agents."""
from typing import Dict
from typing import List




# =========================================================
# MODULE 3 -- Smart Antibiotic Ranking
# يرتب الأدوية الـ Sensitive حسب الأولوية السريرية
# =========================================================
RANKING_WEIGHTS = {
    "aware_score":     {"Access": 3, "Watch": 2, "Reserve": 1, None: 0},
    "route_score":     {"oral": 2, "iv": 1},
    "specimen_match":  2,   # bonus لو الدواء له specimen_note للعينة دي
    "priority_bonus":  lambda p: max(0, 6 - p),  # priority 1 -> +5, priority 5 -> +1
}

def rank_sensitive_antibiotics(
    allowed:      List[Dict],
    culture_type: str,
    organism:     str,
    sir_map:      Dict[str, str],
    phenotypes:   List[Dict],
) -> List[Dict]:
    """
    يرتب الأدوية المسموحة بترتيب هرمي صارم (lexicographic) — كل معيار يكسر
    التعادل في المعيار الأهم منه فقط، فلا يتغلب معيار أدنى على أعلى:

      1. نتيجة المزرعة   : S قبل I  (بوابة صارمة — لا يتخطى I دواءً S أبداً)
      2. ملاءمة العينة   : دواء له specimen_note للعينة الحالية أولاً
      3. WHO AWaRe       : Access > Watch > Reserve
      4. طريق الإعطاء     : Oral قبل IV/IM (لو المريض مؤهل)
      5. Priority        : أولوية الـ guidelines (أقل = أفضل)
      6. الاسم           : لضمان ترتيب ثابت (deterministic)

    ملاحظة تصميمية: السبب في استخدام الترتيب الهرمي بدل جمع النقاط أن جمع
    النقاط كان يسمح لدواء Intermediate ذي AWaRe/route جيد أن يتفوق على دواء
    Sensitive — وهذا خطأ إكلينيكي (الفعالية المخبرية تسبق كل شيء).
    يُحتفظ بـ _score كقيمة عرض تقريبية فقط، لا للترتيب.
    """
    ph_names = [p.get("phenotype", "") for p in phenotypes]
    _sir_rank   = {"S": 0, "I": 1}          # الأصغر = أفضل
    _aware_rank = {"Access": 0, "Watch": 1, "Reserve": 2}

    def sort_key(item):
        name = item.get("name", "")
        sir  = sir_map.get(name)
        # 1) Susceptibility gate (S=0, I=1, unknown=2 -> آخر القائمة)
        k_sir = _sir_rank.get(sir, 2)
        # 2) Specimen appropriateness (match=0 يسبق no-match=1)
        k_spec = 0 if (item.get("specimen_notes") or {}).get(culture_type) else 1
        # 3) AWaRe (Access first). لكن CRE/CRAB/CRPA تُنزّل السيفالوسبورين غير الـ S
        aware = item.get("aware")
        k_aware = _aware_rank.get(aware, 3)
        if any(ph in ph_names for ph in ["CRE", "CRAB", "CRPA"]):
            cls = item.get("class", "").lower()
            if "cephalosporin" in cls and sir != "S":
                k_aware += 5          # ادفعه لأسفل ضمن نفس مستوى الحساسية
        # 4) Route (oral first)
        k_route = 0 if item.get("high_po") else 1
        # 5) Priority (أقل أفضل)
        k_priority = item.get("priority", 99)
        return (k_sir, k_spec, k_aware, k_route, k_priority, name)

    # _score للعرض فقط (تقريبي) — لا يُستخدم في الترتيب
    def _display_score(item):
        name = item.get("name", "")
        sir  = sir_map.get(name)
        s = 0
        if sir == "S": s += 4
        elif sir == "I": s += 1
        s += RANKING_WEIGHTS["aware_score"].get(item.get("aware"), 0)
        s += RANKING_WEIGHTS["route_score"]["oral" if item.get("high_po") else "iv"]
        if (item.get("specimen_notes") or {}).get(culture_type):
            s += RANKING_WEIGHTS["specimen_match"]
        s += RANKING_WEIGHTS["priority_bonus"](item.get("priority", 5))
        return s

    scored = [
        {**item, "_score": _display_score(item), "_sir": (sir_map.get(item.get("name", "")) or "--")}
        for item in allowed
    ]
    return sorted(scored, key=sort_key)
