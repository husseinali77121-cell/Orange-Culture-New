# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Ranking of the susceptible agents."""
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from cdss.common.specimen import classify_specimen




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

# ── Guideline order for a resistance mechanism at a site (v6.6, 2026-11-13) ──
# The final review found the ranked ("preferred") list contradicting the
# guideline cards printed next to it, because nothing in the ranking knew what a
# guideline prefers for a mechanism at a site:
#   * MRSA pneumonia      -> Doxycycline > TMP-SMX > Vancomycin > Linezolid
#   * ESBL bacteraemia    -> Ciprofloxacin > Levofloxacin > carbapenems
#   * AmpC E. cloacae BSI -> Ciprofloxacin > Cefepime
#   * KPC / DTR-P. aeruginosa / CRAB -> alphabetical among the novel agents
#     (Minocycline above Sulbactam-durlobactam for CRAB)
# Each tier below is the guideline's PREFERRED agents as a list of GROUPS: the
# groups come in the guideline's order, and the agents inside one group are of
# equal standing, so the stewardship order (AWaRe, route, priority) decides
# among them. A listed agent that is on the allowed list goes first; everything
# else follows in the stewardship order. An agent is never added here -- only
# reordered: the susceptibility gate and every safety layer have already
# decided what is allowed.
#   IDSA AMR Guidance 2026 (Tamma et al., Clin Infect Dis 2026): ESBL-E, AmpC-E,
#   CRE by carbapenemase class, DTR-P. aeruginosa, CRAB, S. maltophilia.
#   IDSA MRSA guideline 2011 / ATS-IDSA HAP-VAP 2016: MRSA bacteraemia, pneumonia, CNS.
#   IDSA bacterial meningitis guideline (Tunkel 2004): pathogen-directed therapy.
Tier = List[Tuple[str, ...]]
_TMP_FQ = ("Trimethoprim/Sulfamethoxazole", "Ciprofloxacin", "Levofloxacin")
_CARBAPENEMS = ("Meropenem", "Imipenem/Cilastatin", "Ertapenem")
_AMINOGLYCOSIDES = ("Gentamicin", "Amikacin", "Tobramycin")        # cystitis: one dose

_ESBL_CYSTITIS: Tier = [("Nitrofurantoin", "Trimethoprim/Sulfamethoxazole") + _AMINOGLYCOSIDES]
_ESBL_UPPER_UTI: Tier = [_TMP_FQ, _CARBAPENEMS]
_ESBL_INVASIVE: Tier = [("Meropenem",), ("Imipenem/Cilastatin",), ("Ertapenem",)]
_AMPC_UPPER_UTI: Tier = [_TMP_FQ, ("Cefepime",), _CARBAPENEMS]
_AMPC_INVASIVE: Tier = [("Cefepime",), _CARBAPENEMS]
_CRE_CYSTITIS: Tier = [("Trimethoprim/Sulfamethoxazole", "Nitrofurantoin", "Ciprofloxacin",
                        "Levofloxacin") + _AMINOGLYCOSIDES]
_CRE_BY_CLASS: Dict[str, Tier] = {
    "KPC":    [("Meropenem + Vaborbactam",), ("Ceftazidime + Avibactam",), ("Imipenem + Relebactam",)],
    "OXA-48": [("Ceftazidime + Avibactam",)],
    "MBL":    [("Aztreonam + Avibactam", "Cefiderocol")],
}
_DTR_PA_NOVEL = ("Ceftolozane + Tazobactam", "Ceftazidime + Avibactam", "Imipenem + Relebactam")
_DTR_PA_CYSTITIS: Tier = [_DTR_PA_NOVEL + ("Cefiderocol", "Tobramycin", "Amikacin")]
_DTR_PA_UPPER_UTI: Tier = [_DTR_PA_NOVEL + ("Cefiderocol",)]
_DTR_PA_PNEUMONIA: Tier = [("Ceftolozane + Tazobactam",),
                           ("Ceftazidime + Avibactam", "Imipenem + Relebactam")]
_DTR_PA_INVASIVE: Tier = [_DTR_PA_NOVEL]
_CRAB: Tier = [("Sulbactam + Durlobactam",)]
_STENO: Tier = [("Cefiderocol",)]
_MRSA_BY_SITE: Dict[str, Tier] = {
    "blood":  [("Vancomycin", "Daptomycin")],
    "sputum": [("Vancomycin", "Linezolid")],
    "csf":    [("Vancomycin",), ("Linezolid",)],
}
# Meningitis: pathogen-directed therapy (IDSA 2004), used when no resistance
# mechanism above applies. Without it TMP-SMX (an alternative) led the list for a
# Klebsiella or pneumococcal meningitis, ahead of the third-generation cephalosporin.
_CEPH3 = ("Ceftriaxone", "Cefotaxime")
_CSF_BY_ORGANISM: Tuple[Tuple[Tuple[str, ...], Tier], ...] = (
    (("listeria",), [("Ampicillin", "Penicillin")]),
    (("agalactiae", "group b"), [("Ampicillin", "Penicillin")]),
    (("streptococcus pneumoniae", "pneumococc"),
     [("Penicillin", "Ampicillin"), _CEPH3]),
    (("enterococc", "vre"), [("Ampicillin", "Penicillin")]),
    (("staphylococc", "staph", "mssa"), [("Oxacillin",)]),
    (("influenzae",), [("Ampicillin",), _CEPH3]),
    (("pseudomonas",), [("Cefepime", "Ceftazidime"), ("Meropenem",)]),
    (("acinetobacter",), [("Meropenem",)]),
    (("e. coli", "escherichia", "klebsiella", "proteus", "serratia", "citrobacter",
      "morganella", "providencia", "salmonella", "enterobacter", "hafnia", "enterobacterales"),
     [_CEPH3]),
)
_STREP_PNEUMO_BLOOD: Tier = [("Penicillin", "Ampicillin", "Amoxicillin"), _CEPH3]

# Where a mechanism-directed order applies. A superficial wound swab, a stool
# isolate or an upper-airway swab keeps the stewardship order, so an oral agent
# that tests S stays first (one policy for every mechanism).
_INVASIVE_SITES = ("blood", "csf", "sputum", "pus", "abdomen")
_UPPER_AIRWAY = ("throat", "pharyn", "nasopharyn", "tonsil", "nasal", "nose", "حلق")
# Initial therapy of a bloodstream or CNS infection is intravenous: "oral first"
# is a step-down rule and does not apply to these sites.
_IV_FIRST_SITES = ("blood", "csf")


def _is_moderate_risk_ampc(organism: str) -> bool:
    """IDSA 2026 moderate-risk inducible AmpC species, read from the organism
    profile's own AmpC caution so there is one list, not two."""
    from cdss.organisms.organism_profile import ORGANISM_PROFILE
    _c = (ORGANISM_PROFILE.get(organism) or {}).get("caution") or {}
    return "AmpC" in str(_c.get("Ceftriaxone", ""))


def _site_kind(culture_type: str, uti_syndrome: Optional[str]) -> Tuple[str, str]:
    """(site, kind): kind is 'cystitis', 'upper_uti', 'invasive' or 'other'."""
    site = classify_specimen(culture_type)
    if site == "urine":
        upper = str(uti_syndrome or "").lower() in ("upper", "pyelonephritis", "urosepsis", "cuti")
        return site, ("upper_uti" if upper else "cystitis")
    if site == "sputum" and any(t in (culture_type or "").lower() for t in _UPPER_AIRWAY):
        return site, "other"           # throat / nasal swab: colonisation more likely than pneumonia
    return site, ("invasive" if site in _INVASIVE_SITES else "other")


def guideline_tiers(organism: str, culture_type: str, phenotypes: List[Dict],
                    carbapenemase_type: Optional[str] = None,
                    uti_syndrome: Optional[str] = None) -> Tier:
    """The guideline's preferred agents for this mechanism and site, as ordered
    groups of equal standing. Empty when no guideline order applies."""
    ph = {p.get("phenotype", "") for p in (phenotypes or [])}
    site, kind = _site_kind(culture_type, uti_syndrome)
    org_l = (organism or "").lower()

    if "CRE" in ph:
        if kind == "cystitis":
            return list(_CRE_CYSTITIS)
        from cdss.therapy.therapy_rules import normalize_carbapenemase_type
        by_class = list(_CRE_BY_CLASS.get(normalize_carbapenemase_type(carbapenemase_type), []))
        if kind == "upper_uti":         # IDSA: TMP-SMX / FQ preferred if S; novel agents also preferred
            return [_TMP_FQ] + by_class
        return by_class if kind == "invasive" else []
    if "DTR_PA" in ph:
        return {"cystitis": _DTR_PA_CYSTITIS, "upper_uti": _DTR_PA_UPPER_UTI,
                "invasive": _DTR_PA_PNEUMONIA if site == "sputum" else _DTR_PA_INVASIVE,
                }.get(kind, [])
    if "CRAB" in ph:
        return list(_CRAB) if kind in ("invasive", "upper_uti") else []
    if "STENO" in ph:
        return list(_STENO) if kind in ("invasive", "upper_uti") else []
    if "ESBL" in ph:
        return {"cystitis": _ESBL_CYSTITIS, "upper_uti": _ESBL_UPPER_UTI,
                "invasive": _ESBL_INVASIVE}.get(kind, [])
    if "AMPC" in ph or _is_moderate_risk_ampc(organism):
        return {"upper_uti": _AMPC_UPPER_UTI, "invasive": _AMPC_INVASIVE}.get(kind, [])
    if "MRSA" in ph:
        return list(_MRSA_BY_SITE.get(site, [])) if kind == "invasive" else []
    if site == "csf":
        for keys, tier in _CSF_BY_ORGANISM:
            if any(k in org_l for k in keys):
                return list(tier)
    if site == "blood" and ("pneumoniae" in org_l and "strep" in org_l or "pneumococc" in org_l):
        return list(_STREP_PNEUMO_BLOOD)
    return []


def guideline_preferred(organism: str, culture_type: str, phenotypes: List[Dict],
                        carbapenemase_type: Optional[str] = None,
                        uti_syndrome: Optional[str] = None) -> List[str]:
    """Flat list of the guideline-preferred agents (membership and display)."""
    return [d for g in guideline_tiers(organism, culture_type, phenotypes,
                                       carbapenemase_type, uti_syndrome) for d in g]


def route_label(item: Dict, culture_type: str) -> str:
    """'PO' or 'IV' as the route this agent would be given for THIS site. Penicillin
    is flagged oral-capable, but for blood or CSF it is benzylpenicillin IV."""
    if classify_specimen(culture_type) in _IV_FIRST_SITES and "IV" in str(item.get("class", "")):
        return "IV"
    return "PO" if item.get("high_po") else "IV"


def rank_sensitive_antibiotics(
    allowed:      List[Dict],
    culture_type: str,
    organism:     str,
    sir_map:      Dict[str, str],
    phenotypes:   List[Dict],
    carbapenemase_type: Optional[str] = None,
    uti_syndrome: Optional[str] = None,
) -> List[Dict]:
    """
    يرتب الأدوية المسموحة بترتيب هرمي صارم (lexicographic) — كل معيار يكسر
    التعادل في المعيار الأهم منه فقط، فلا يتغلب معيار أدنى على أعلى:

      1. نتيجة المزرعة   : S قبل I  (بوابة صارمة — لا يتخطى I دواءً S أبداً)
      2. الإرشادات       : الأدوية المفضّلة للآلية والموقع، بترتيب الإرشاد (IDSA 2026)؛
                           داخل المجموعة الواحدة المتساوية تقرر المعايير التالية
      3. WHO AWaRe       : Access > Watch > Reserve
      4. طريق الإعطاء     : Oral قبل IV/IM — إلا في الدم والسائل النخاعي (العلاج يبدأ وريدياً)
      5. Priority        : أولوية الـ formulary (أقل = أفضل)
      6. ملاءمة العينة   : دواء له specimen_note للعينة الحالية (فاصل تعادل فقط)
      7. الاسم           : لضمان ترتيب ثابت (deterministic)

    ملاحظة تصميمية: السبب في استخدام الترتيب الهرمي بدل جمع النقاط أن جمع
    النقاط كان يسمح لدواء Intermediate ذي AWaRe/route جيد أن يتفوق على دواء
    Sensitive — وهذا خطأ إكلينيكي (الفعالية المخبرية تسبق كل شيء).
    يُحتفظ بـ _score كقيمة عرض تقريبية فقط، لا للترتيب.

    CHANGED v6.6 (2026-11-13): "ملاءمة العينة" كانت المعيار الثاني، قبل AWaRe. هي
    تعني فقط "هل للدواء ملاحظة مكتوبة لهذه العينة"، والملاحظات غير مكتملة — فكان
    Vancomycin قبل Amoxicillin لمزرعة جرح بـ Strep. pyogenes، و Daptomycin
    (Reserve) قبل Doxycycline و TMP-SMX لخراج MRSA، و TMP-SMX في آخر القائمة لكل
    مزرعة دم. ملاءمة الموقع الحقيقية تحسمها طبقة الأمان (حظر/تحذير) قبل الترتيب.
    """
    ph_names = [p.get("phenotype", "") for p in phenotypes]
    _sir_rank   = {"S": 0, "I": 1}          # الأصغر = أفضل
    _aware_rank = {"Access": 0, "Watch": 1, "Reserve": 2}
    _tiers = guideline_tiers(organism, culture_type, phenotypes, carbapenemase_type, uti_syndrome)
    _group_of = {}
    for _i, _g in enumerate(_tiers):
        for _d in _g:
            _group_of.setdefault(_d, _i)
    _preferred = list(_group_of)
    _iv_first = classify_specimen(culture_type) in _IV_FIRST_SITES

    def sort_key(item):
        name = item.get("name", "")
        sir  = sir_map.get(name)
        # 1) Susceptibility gate (S=0, I=1, unknown=2 -> آخر القائمة)
        k_sir = _sir_rank.get(sir, 2)
        # 2) Guideline order for this mechanism and site
        k_guide = _group_of.get(name, len(_tiers))
        # 3) AWaRe (Access first). لكن CRE/CRAB/CRPA تُنزّل السيفالوسبورين غير الـ S
        aware = item.get("aware")
        k_aware = _aware_rank.get(aware, 3)
        if any(ph in ph_names for ph in ["CRE", "CRAB", "CRPA"]):
            cls = item.get("class", "").lower()
            if "cephalosporin" in cls and sir != "S":
                k_aware += 5          # ادفعه لأسفل ضمن نفس مستوى الحساسية
        # 4) Route (oral first) -- not for bloodstream / CNS infection
        k_route = 0 if (_iv_first or item.get("high_po")) else 1
        # 5) Priority (أقل أفضل)
        k_priority = item.get("priority", 99)
        # 6) Specimen note present (tie-breaker only)
        k_spec = 0 if (item.get("specimen_notes") or {}).get(culture_type) else 1
        return (k_sir, k_guide, k_aware, k_route, k_priority, k_spec, name)

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
        {**item, "_score": _display_score(item), "_sir": (sir_map.get(item.get("name", "")) or "--"),
         "_guideline_preferred": item.get("name", "") in _preferred}
        for item in allowed
    ]
    return sorted(scored, key=sort_key)
