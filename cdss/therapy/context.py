# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""TherapyContext: everything about ONE case the per-drug rules read.

Built once per analysis by build_context(); frozen, so no rule can alter the
case another rule is about to judge.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cdss.common.aux_tests import is_aux_key, read_aux_tests
from cdss.common.renal import resolve_crcl
from cdss.common.specimen import classify_specimen
from cdss.ocr.ocr_parsing import normalize_sir_map, normalize_sir_value
from cdss.resistance.mechanism import predict_esbl
from cdss.therapy.clsi_categories import sdd_drugs
from cdss.therapy.therapy_rules import allergy_profile as _allergy_profile
from cdss.therapy.therapy_rules import normalize_carbapenemase_type


@dataclass(frozen=True)
class DrugUnderTest:
    """One agent of the panel."""
    name: str                 # formulary key
    info: Dict[str, Any]      # its ABX_GUIDELINES row
    low: str                  # name, lower-cased
    cls: str                  # class text, lower-cased
    result: Optional[str]     # "S" | "I" | "R" | None (not on the panel)


@dataclass(frozen=True)
class TherapyContext:
    age: Any
    age_months: Any
    allergy: Any
    carb_type: Any
    child_pugh: Any
    crcl: Any
    crcl_measured: Any
    crcl_src: Any
    d_test: Any
    current_meds: Any
    invasive_tx: Any
    invasive_why: Any
    is_carbapenemase: Any
    is_entero_r2: Any
    is_esbl_like: Any
    is_hepatic: Any
    is_mrsa: Any
    is_pneumo_r2: Any
    is_possible_carb: Any
    is_preg: Any
    is_renal: Any
    is_staph: Any
    is_staph_r2: Any
    is_strep_r2: Any
    mech: Any
    mech_label: Any
    mech_prob: Any
    org_l: Any
    penicillinase: Any
    organism: Any
    possible_mrsa: Any
    sex: Any
    sir: Any
    sdd: Any                  # drugs the panel reports as CLSI SDD (read as I in `sir`)
    spec_cat: Any
    specimen: Any
    unreadable: Any
    urine_lower: Any
    uti_upper: Any
    weight_kg: Any = None      # v7.1: label weight floors (gepotidacin >= 40 kg)
    alerts: List[str] = field(default_factory=list)      # interaction / side alerts (appended by rules)


def build_context(
    final_drugs: List[str],
    organism_type: str,
    culture_type: str,
    age: int,
    sex: str,
    is_renal: bool,
    cl_cr: Optional[float],
    is_preg: bool,
    is_hepatic: bool,
    current_meds: List[str],
    sir_map: Dict[str, str],
    child_pugh: str = "C",
    age_months: Optional[int] = None,
    *,
    carbapenemase_type: Optional[str] = None,
    uti_syndrome: Optional[str] = None,
    allergies: Optional[List[str]] = None,
    weight_kg: Optional[float] = None,
) -> Tuple[TherapyContext, List[str]]:
    """Normalise the inputs and derive every case-level fact once.

    Returns (context, drugs): `drugs` is the de-duplicated, trimmed panel order.
    """
    # child_pugh defaults to the WORST grade on purpose (fail-closed), and
    # cl_cr=None means "no creatinine was measured", NOT "normal": resolve_crcl()
    # substitutes ASSUMED_CRCL_UNKNOWN when the renal flag is set.
    _crcl, _crcl_measured = resolve_crcl(cl_cr, is_renal)
    _crcl_src = ("" if _crcl_measured else
                 " (CrCl مفترضة — لم يُقَس الكرياتينين؛ أدخِله لضبط الجرعة)")
    # Drugs that WERE on the panel but whose result could not be read. They must
    # not fall through to the untested-drug path, which would present them as
    # ordinary options.
    _unreadable = {str(d or "").strip() for d, v in (sir_map or {}).items()
                   if normalize_sir_value(v) is None and str(d or "").strip()
                   and not is_aux_key(d)}
    # D-test / penicillinase are Positive/Negative, not S/I/R: read them from the
    # RAW panel -- normalize_sir_map() below drops them.
    _aux = read_aux_tests(sir_map)
    # CLSI SDD (decision D4, v6.9): normalised to I like every other consumer
    # expects, and remembered here so the note can name the SDD regimen.
    _sdd = frozenset(sdd_drugs({d: v for d, v in (sir_map or {}).items() if not is_aux_key(d)},
                               organism_type))
    sir_map = normalize_sir_map({d: v for d, v in (sir_map or {}).items() if not is_aux_key(d)})
    # final_drugs is built from the RAW panel keys upstream, so it carries the
    # same OCR padding the map does. Trim here as well, or a drug whose name
    # arrived as " Ciprofloxacin " matches no formulary entry and disappears from
    # the report entirely -- neither recommended nor banned.
    current_meds = list(current_meds or [])
    _seen = set()
    final_drugs = [d for d in (str(x or "").strip() for x in (final_drugs or []))
                   if d and not (d in _seen or _seen.add(d))]

    # ── Detect resistance mechanism ONCE (drives beta-lactam suppression) ──────
    # ESBL -> resistant to ALL penicillins + cephalosporins (+ aztreonam),
    #        even if AST reports S (inoculum effect; EUCAST/CLSI report-as-tested
    #        but clinically carbapenem is required for serious infection).
    # Carbapenemase -> also resistant to carbapenems.
    _mech = predict_esbl(organism_type, sir_map) if sir_map else {}
    _mech = _mech or {}
    _mech_prob = _mech.get("probability")
    _is_esbl_like   = _mech_prob in ("high", "ampc", "ampc_plasmid")
    # CONFIRMED only (>=2 carbapenems R). A single carbapenem R or Meropenem I is
    # "possible_carbapenemase": it still raises the alert and asks for mCIM/PCR,
    # but it must NOT ban agents the AST reports as active -- that turned a 55%
    # suspicion into a full beta-lactam lockdown.
    _is_carbapenemase = _mech_prob == "carbapenemase"
    _is_possible_carb = _mech_prob == "possible_carbapenemase"
    _carb_type = normalize_carbapenemase_type(carbapenemase_type)
    # v7.1 (external review 2026-11-19): a carbapenemase CONFIRMED by the
    # laboratory (PCR / immunochromatography, entered as its type) outranks the
    # phenotype prediction. It used to be stored beside it and ignored by the
    # rules that read `is_carbapenemase`, so a KPC with a carbapenem-susceptible
    # panel left sulopenem, cefepime-enmetazobactam and pivmecillinam allowed.
    # Enterobacterales only: the IDSA CRE algorithms are by enzyme; for P.
    # aeruginosa each agent stays judged on its AST (the CRPA design above, with
    # the enzyme still read by novel_agent_verdict), and a type entered for a
    # Gram-positive or Acinetobacter is not a carbapenemase this rule knows.
    from cdss.astqc.ast_reportability import ENTEROBACTERALES as _ENTB
    _ol = (organism_type or "").lower()
    _carb_confirmed = bool(_carb_type) and ("enterobacterales" in _ol
                                            or any(t in _ol for t in _ENTB))
    if _carb_confirmed:
        _is_carbapenemase = True
        _is_possible_carb = False
    _mech_label = ("Carbapenemase" if _is_carbapenemase
                   else "AmpC" if _mech_prob in ("ampc", "ampc_plasmid") else "ESBL")
    _allergy = _allergy_profile(allergies)
    _spec_cat_aa = classify_specimen(culture_type)
    _uti_upper = (_spec_cat_aa == "urine" and str(uti_syndrome or "").lower()
                  in ("upper", "pyelonephritis", "urosepsis"))

    # ── Detect MRSA from AST markers (Oxacillin/Cefoxitin R), not just name ────
    # A S. aureus with Oxacillin-R or Cefoxitin-R IS MRSA -> ALL beta-lactams fail
    # (except anti-MRSA cephalosporins like Ceftaroline, not in this formulary).
    _org_l_aa = (organism_type or "").lower()
    _is_staph = ("staphylococcus" in _org_l_aa or "staph" in _org_l_aa
                 or _org_l_aa == "mrsa" or _org_l_aa == "mssa")
    # MRSA detection: AST markers + organism name + free-text report markers
    _mrsa_text_markers = (
        "mrsa screen positive" in _org_l_aa
        or "pbp2a positive" in _org_l_aa
        or "pbp2a" in _org_l_aa
        or "methicillin resistant" in _org_l_aa
        or "methicillin-resistant" in _org_l_aa
    )
    _mrsa_marker_R = (sir_map.get("Oxacillin") == "R"
                      or sir_map.get("Cefoxitin") == "R"
                      or _org_l_aa == "mrsa"
                      or _mrsa_text_markers)
    _is_mrsa = _is_staph and _mrsa_marker_R

    # ── "Possible MRSA": the panel carries no oxacillin and no cefoxitin ──────
    # DEFECT 2026-08-03. detect_resistance_phenotypes() already raised
    # "Possible MRSA -- تأكيد مطلوب" for exactly this pattern (S. aureus, a
    # beta-lactam R, vancomycin or linezolid S) — and this engine knew nothing
    # about it, because _is_mrsa requires an oxacillin or cefoxitin R that the
    # panel never carried. So on a S. aureus BACTERAEMIA the phenotype panel
    # said "possible MRSA, confirm with cefoxitin/mecA" while the column beside
    # it recommended Ceftriaxone and Meropenem.
    #
    # The response is deliberately CAUTION, not a ban. "Possible" is not
    # "confirmed": a heuristic inference must not fabricate a diagnosis and
    # strip every beta-lactam from a patient who may have plain MSSA. But a
    # beta-lactam must not sit in the green column either while the screen
    # says the isolate may be methicillin-resistant. Demote and say why.
    _possible_mrsa = False
    if _is_staph and not _is_mrsa:
        _vanco_s = sir_map.get("Vancomycin") == "S"
        _linez_s = sir_map.get("Linezolid") == "S"
        _bl_r = any(sir_map.get(d) == "R" for d in
                    ("Amoxicillin + Clavulanic acid", "Cephalexin", "Cefuroxime"))
        _possible_mrsa = _bl_r and (_vanco_s or _linez_s)
        # Oxacillin / cefoxitin have NO intermediate category for staphylococci
        # (EUCAST v16 / CLSI M100): an "I" there is not a susceptible screen. It
        # is not proof of mecA either, so it raises the same caution -- never a
        # silent pass of every beta-lactam.
        if any(sir_map.get(d) == "I" for d in ("Oxacillin", "Cefoxitin")):
            _possible_mrsa = True

    _is_staph_r2 = any(k in _org_l_aa for k in ("staph", "mrsa", "mssa"))
    _is_strep_r2 = "strep" in _org_l_aa or "pneumoc" in _org_l_aa
    _is_entero_r2 = "enterococc" in _org_l_aa or _org_l_aa.strip() == "vre"
    _is_pneumo_r2 = "pneumoniae" in _org_l_aa and "strep" in _org_l_aa
    _urine_lower = (_spec_cat_aa == "urine" and not _uti_upper)
    if _mech_prob in ("ampc", "ampc_plasmid"):
        _invasive_tx = ("Cefepime إذا MIC ≤ 8 (S، أو SDD بجرعة 2 g q8h)، وإلا Carbapenem "
                        "(IDSA 2026 — AmpC)")
        _invasive_why = ("AmpC: الـ 3rd-gen cephalosporins و Pip-Tazo غير مقترحة للعدوى الغازية "
                         "لخطر انتقاء طفرات مُفرِطة الإنتاج أثناء العلاج")
    else:
        _invasive_tx = "Carbapenem (Meropenem / Ertapenem)"
        _invasive_why = ("ESBL: البيتا-لاكتام الحساس معملياً أقل موثوقية في العدوى الغازية "
                         "(inoculum effect؛ MERINO 2018 لتجرثم الدم)")

    return TherapyContext(
        age=age,
        age_months=age_months,
        allergy=_allergy,
        carb_type=_carb_type,
        child_pugh=child_pugh,
        crcl=_crcl,
        crcl_measured=_crcl_measured,
        crcl_src=_crcl_src,
        d_test=_aux["d_test"],
        current_meds=current_meds,
        invasive_tx=_invasive_tx,
        invasive_why=_invasive_why,
        is_carbapenemase=_is_carbapenemase,
        is_entero_r2=_is_entero_r2,
        is_esbl_like=_is_esbl_like,
        is_hepatic=is_hepatic,
        is_mrsa=_is_mrsa,
        is_pneumo_r2=_is_pneumo_r2,
        is_possible_carb=_is_possible_carb,
        is_preg=is_preg,
        is_renal=is_renal,
        is_staph=_is_staph,
        is_staph_r2=_is_staph_r2,
        is_strep_r2=_is_strep_r2,
        mech=_mech,
        mech_label=_mech_label,
        mech_prob=_mech_prob,
        org_l=_org_l_aa,
        penicillinase=_aux["penicillinase"],
        organism=organism_type,
        possible_mrsa=_possible_mrsa,
        sex=sex,
        sir=sir_map,
        sdd=_sdd,
        spec_cat=_spec_cat_aa,
        specimen=culture_type,
        unreadable=_unreadable,
        urine_lower=_urine_lower,
        uti_upper=_uti_upper,
        weight_kg=weight_kg,
    ), final_drugs
