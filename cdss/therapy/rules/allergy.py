# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Drug-allergy rule.

Every rule has the same shape:  rule(cx, dg, out) -> None
    cx   TherapyContext  the case: organism, specimen, host, mechanism (read-only)
    dg   DrugUnderTest   one agent of the panel and its S/I/R result (read-only)
    out  Outcome         where the rule records a ban / caution / note
"""
from cdss.therapy.drug_classes import _cls_and_name
from cdss.therapy.intrinsic import build_banned_item


def rule_allergy(cx, dg, out):
    """Documented drug allergy: same class is a hard stop, cross-reactive classes are cautions."""
    # ── Drug allergy (2026-11-10). Patient.allergies existed and nothing
    # read it. A documented allergy is a hard stop for the class itself;
    # cross-reactive classes are cautions with the real numbers.
    _cn = _cls_and_name(dg.info, dg.name)
    # Sulbactam-durlobactam is a beta-lactam but not an aminopenicillin:
    # it gets the cross-reactivity caution, not the class ban.
    _is_pen = (any(k in _cn for k in ("penicillin", "cillin")) or "sulbactam" in _cn) \
        and "cephalosporin" not in _cn and "cef" not in dg.low \
        and "durlobactam" not in dg.low
    _is_ceph = "cephalosporin" in _cn or dg.low.startswith("cef") or dg.low.startswith("ceph")
    _is_carb = "carbapenem" in _cn or "penem" in dg.low
    _allergy_ban = None
    if cx.allergy["penicillin"] and _is_pen:
        _allergy_ban = "حساسية مسجّلة للبنسلين."
    elif cx.allergy["cephalosporin"] and _is_ceph:
        _allergy_ban = "حساسية مسجّلة للسيفالوسبورينات."
    elif cx.allergy["ceftazidime"] and "ceftazidime" in dg.low:
        # FIX v6.7: a recorded Ceftazidime allergy only ever produced the
        # aztreonam side-chain note -- Ceftazidime itself, and
        # Ceftazidime-Avibactam, stayed in the recommended list.
        _allergy_ban = "حساسية مسجّلة للـ Ceftazidime."
    elif cx.allergy["sulfa"] and ("sulfamethox" in dg.low or "sulfonamide" in dg.cls):
        _allergy_ban = "حساسية مسجّلة للسلفوناميد."
    elif cx.allergy["fluoroquinolone"] and "fluoroquinolone" in dg.cls:
        _allergy_ban = "حساسية مسجّلة للفلوروكينولونات."
    elif cx.allergy["macrolide"] and "macrolide" in dg.cls:
        _allergy_ban = "حساسية مسجّلة للماكروليدات."
    if _allergy_ban:
        out.ban(build_banned_item(
            dg.name, "allergy", _allergy_ban,
            f"{dg.name}: {_allergy_ban} لا يُعطى نفس الصنف. راجع نوع التفاعل السابق "
            "(تأقي فوري أم طفح متأخر) قبل اختيار البديل."))
        return
    if cx.allergy["penicillin"] and (_is_ceph or _is_carb or "durlobactam" in dg.low):
        out.note(dg.name, "warn", (
            "حساسية بنسلين: التفاعل المتصالب مع الكاربابينيم < 1%، ومع "
            "السيفالوسبورينات ذات السلاسل الجانبية المختلفة منخفض. "
            + ("الحساسية مسجّلة كشديدة/فورية — يُعطى تحت مراقبة أو بعد استشارة حساسية."
               if cx.allergy["penicillin_severe"] else
               "مع تاريخ طفح خفيف غير فوري يُعطى عادة بأمان.")), "allergy")
    elif cx.allergy["cephalosporin"] and (_is_pen or _is_carb):
        out.note(dg.name, "warn", "حساسية سيفالوسبورين: تفاعل متصالب منخفض — راجع السلسلة الجانبية للدواء المسبب.", "allergy")
    elif cx.allergy["ceftazidime"] and "aztreonam" in dg.low:
        out.note(dg.name, "warn", "Aztreonam يشارك Ceftazidime نفس السلسلة الجانبية — تفاعل متصالب ممكن.", "allergy")
    elif cx.allergy["ceftazidime"] and "cefiderocol" in dg.low:
        out.note(dg.name, "warn", "Cefiderocol سلسلته الجانبية شبيهة بالـ Ceftazidime والـ Aztreonam — تفاعل متصالب ممكن.", "allergy")
