# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Resistance-mechanism inference: ESBL / AmpC / carbapenemase."""
from typing import Any
from typing import Dict

from cdss.ocr.ocr_parsing import normalize_sir_map
from cdss.therapy.intrinsic import (
    _remove_intrinsic_resistance,
)


# ── Mechanism producer sets — CANONICAL (kept identical across modules) ──────
# Enterobacterales capable of ESBL production. "enterobacterales" (generic,
# unspeciated) is included so an ID without genus is still treated as ESBL-capable.
ESBL_PRODUCERS = frozenset([
    "escherichia coli", "e. coli", "e.coli",
    "klebsiella pneumoniae", "klebsiella spp.", "klebsiella oxytoca",
    "proteus mirabilis", "proteus spp.", "proteus vulgaris",
    "enterobacter cloacae", "enterobacter spp.", "enterobacter aerogenes",
    "citrobacter freundii", "citrobacter koseri", "citrobacter spp.",
    "serratia marcescens", "serratia spp.",
    "morganella morganii", "providencia spp.",
    "enterobacterales", "hafnia alvei",
    # 2026-11-11 (round 4): Salmonella and Shigella are Enterobacterales and
    # CTX-M ESBLs are well documented in both (Egypt included); the AmpC note
    # further down names Salmonella explicitly. Missing here, a Salmonella
    # bacteraemia with ceftriaxone AND cefotaxime R came back with no mechanism
    # at all -- piperacillin-tazobactam and cefepime RECOMMENDED -- while the
    # identical E. coli panel had both refused (IDSA AMR Guidance 2026).
    "salmonella spp.", "salmonella", "shigella spp.", "shigella",
])

def _re_ws_collapse(text) -> str:
    """lower + strip + collapse internal whitespace. Thin alias over
    clinical_utils.collapse_ws, defined as a real function rather than an
    import alias because the AST-extraction harnesses lift it out by name."""
    from cdss.common.clinical_utils import collapse_ws
    return collapse_ws(text)

def _org_matches(org_l, keys) -> bool:
    """Alias over clinical_utils.org_matches — see that module for the history.

    Kept as a module-level name because the AST-extraction test harnesses slice
    functions out of this file by name and exec them in a bare namespace. The
    import is INSIDE the function for the same reason: a module-level alias
    would resolve to nothing once the function is lifted out of the file, and
    the harnesses would fail with a NameError that says nothing about the real
    dependency. Importing here makes the extracted function self-sufficient.
    """
    from cdss.common.clinical_utils import org_matches as _m
    return _m(org_l, keys)

def is_esbl_producer(organism: str) -> bool:
    """True only for organisms KNOWN to produce ESBL (Enterobacterales).
    ESBL is a mechanism defined for Enterobacterales — this is the single gate
    that keeps the ESBL prediction/alert off non-Enterobacterales (P. aeruginosa,
    Acinetobacter, Stenotrophomonas, Gram-positives)."""
    return _org_matches((organism or "").lower().strip(), ESBL_PRODUCERS)

# Chromosomal inducible AmpC ("SPICE/SPACE") + P. aeruginosa + Hafnia.
AMPC_PRODUCERS = frozenset([
    "enterobacter cloacae", "enterobacter spp.", "enterobacter aerogenes",
    "citrobacter freundii", "citrobacter spp.",
    "serratia marcescens", "serratia spp.",
    "morganella morganii", "providencia spp.",
    "pseudomonas aeruginosa", "hafnia alvei",
    "pseudomonas spp.",          # unspeciated: treated as P. aeruginosa (2026-11-10)
])

ESBL_MARKERS = {
    # Primary 3rd-gen oxyimino-cephalosporins -- best ESBL indicators
    "primary":   ["Ceftriaxone", "Cefotaxime", "Ceftazidime", "Cefpodoxime"],
    # Cefepime is 4th-gen -- may stay S in ESBL -> secondary only
    "secondary": ["Cefepime"],
    # Lower-gen cephalosporins
    "medium":    ["Cefuroxime", "Cefixime", "Cefaclor", "Cephalexin"],
}

CARBAPENEMS = ["Imipenem/Cilastatin", "Meropenem", "Ertapenem"]

def predict_esbl(organism: str, sir_map: Dict[str, str]) -> Dict[str, Any]:
    """
    Predict ESBL / AmpC / Carbapenemase from the resistance phenotype.
    Returns probability + confidence (0-100) + mechanism + markers.

    Logic (EUCAST/CLSI):
    • ESBL  : R to ≥1 primary 3rd-gen cephalosporin (Ceftriaxone/Cefotaxime/Ceftazidime)
    • AmpC  : 3rd-gen R + Cefoxitin R (in AmpC-prone organism)
    • Carbapenemase tiers:
        - OXA-48 suspicion : Ertapenem R, Meropenem S/I
        - high             : ≥2 carbapenems R
        - moderate         : 1 carbapenem R (or Meropenem I)
    """
    sir_map = normalize_sir_map(sir_map)
    if not sir_map:
        return {"probability": None, "confidence": 0}

    # `(organism or "")`: every other entry point in this file coerces None, this
    # one did not and raised AttributeError instead of failing closed.
    org_l = (organism or "").lower().strip()
    is_producer = is_esbl_producer(organism)   # ESBL prediction/alert: producers only
    is_ampc_prone = _org_matches(org_l, AMPC_PRODUCERS)
    if not is_producer and not is_ampc_prone:
        return {"probability": None, "confidence": 0}

    # ── FIX: never infer a mechanism from INTRINSIC resistance ────────────────
    # A drug the organism is intrinsically resistant to carries ZERO information
    # about ESBL/AmpC/carbapenemase. P. aeruginosa is intrinsically R to
    # Ceftriaxone/Cefotaxime/Cephalexin/Cefuroxime/Cefoxitin, so leaving them in
    # made the panel below read those (expected) results as ESBL markers and
    # fire a false "ESBL — high" call. Strip intrinsic-R drugs first, then infer
    # only from ACQUIRED resistance. (Local reassignment; caller's map untouched.)
    sir_map = _remove_intrinsic_resistance(organism, sir_map)

    def _ns(drug):  # non-susceptible = R or I
        return sir_map.get(drug) in ("R", "I")
    def _r(drug):
        return sir_map.get(drug) == "R"

    primary_R = [d for d in ESBL_MARKERS["primary"] if _r(d)]
    second_R  = [d for d in ESBL_MARKERS["secondary"] if _r(d)]
    med_R     = [d for d in ESBL_MARKERS["medium"] if _r(d)]
    cefoxitin_R = _r("Cefoxitin")
    # كم marker أساسي (3rd-gen cephalosporin) تم اختباره فعلاً على اللوحة؟
    # الثقة في تفسير ESBL تعتمد على اتساع اللوحة: R لدواء واحد بينما البقية غير
    # مُختبَرة أضعف بكثير من R لدواء مع اختبار البقية.
    primary_tested = [d for d in ESBL_MARKERS["primary"] if d in sir_map]
    _thin_panel = len(primary_tested) < 2

    # FIX 2026-11-10: Proteeae imipenem R is expected, not a carbapenemase marker.
    from cdss.therapy.therapy_rules import is_proteeae
    _proteeae = is_proteeae(organism)
    carb_R_list = [d for d in CARBAPENEMS if _r(d)
                   and not (_proteeae and d == "Imipenem/Cilastatin")]
    erta_R   = _r("Ertapenem")
    mero_R   = _r("Meropenem")
    mero_I   = sir_map.get("Meropenem") == "I"

    # ── 0. P. aeruginosa carbapenem resistance is NOT a carbapenemase call ────
    #
    #  Evidence for splitting this out of the generic carbapenemase tiers below:
    #
    #  * MECHANISM. In P. aeruginosa carbapenem resistance is predominantly
    #    chromosomal -- loss/down-regulation of the OprD porin, MexAB-OprM efflux
    #    up-regulation, and derepressed AmpC (PDC) -- not an acquired
    #    carbapenemase. The PorinPredict validation set found OprD loss in 454 of
    #    522 (87%) meropenem-non-susceptible CARBAPENEMASE-NEGATIVE genomes, and
    #    US CDC Emerging Infections Program surveillance describes carbapenem
    #    resistance in this species as "due primarily to chromosomal mutations
    #    that alter porins, modify efflux pump activity, and derepress intrinsic
    #    beta-lactamases". Carbapenemase-producing CRPA exists and is rising
    #    (MBLs are common in the Middle East, so an Egyptian lab must not exclude
    #    it) -- but it is the minority mechanism, not the default one.
    #
    #  * NO VALIDATED PHENOTYPIC RULE. EUCAST publishes screening / confirmation
    #    algorithms for carbapenemases in Enterobacterales. It has published none
    #    for P. aeruginosa, because the classic beta-lactam pattern cannot
    #    separate carbapenemase-producing from porin/efflux/AmpC CRPA. A "92%
    #    confidence carbapenemase" call from a disk panel therefore has no
    #    standard behind it.
    #
    #  * THE PATIENT-SAFETY BUG. The generic branch returned
    #    probability="carbapenemase", which analyze_antibiotics turns into
    #    `_is_carbapenemase` -- and that BANS every penicillin and cephalosporin
    #    even when the AST reports them Susceptible. So a P. aeruginosa with
    #    Meropenem R but Ceftazidime S had ceftazidime removed from the report.
    #    IDSA AMR guidance (v4.0, Tamma et al., CID 2024;ciae403) says the
    #    opposite: when a carbapenem-resistant isolate remains susceptible to a
    #    traditional beta-lactam, treat with that agent at high dose by extended
    #    infusion. Returning "crpa" keeps `_is_esbl_like` and `_is_carbapenemase`
    #    both False, so each agent is judged on its own AST result.
    #
    #  DTR (difficult-to-treat resistance) per IDSA = non-susceptible to ALL of:
    #  piperacillin-tazobactam, ceftazidime, cefepime, aztreonam, meropenem,
    #  imipenem-cilastatin, ciprofloxacin, levofloxacin.
    _is_pseudomonas = "pseudomonas" in org_l
    if _is_pseudomonas and (len(carb_R_list) >= 1 or mero_I):
        _DTR_AGENTS = ["Piperacillin + Tazobactam", "Ceftazidime", "Cefepime",
                       "Aztreonam", "Meropenem", "Imipenem/Cilastatin",
                       "Ciprofloxacin", "Levofloxacin"]
        _dtr_tested = [d for d in _DTR_AGENTS if d in sir_map]
        _dtr_ns     = [d for d in _dtr_tested if sir_map.get(d) in ("R", "I")]
        # DTR requires the whole first-line set to be non-susceptible. A panel
        # that tested only two of them cannot establish it, so demand >=5.
        _is_dtr = bool(_dtr_tested) and len(_dtr_ns) == len(_dtr_tested) and len(_dtr_tested) >= 5
        # Traditional anti-pseudomonal beta-lactams still reported Susceptible.
        _active_bl = [d for d in ["Piperacillin + Tazobactam", "Ceftazidime",
                                  "Cefepime", "Cefoperazone", "Cefoperazone + Sulbactam",
                                  "Aztreonam"]
                      if sir_map.get(d) == "S"]
        if _is_dtr:
            return {
                "probability": "crpa", "dtr": True, "confidence": 80,
                "active_betalactams": [],
                "mechanism": "DTR P. aeruginosa — difficult-to-treat resistance (mechanism not determined)",
                "markers_R": _dtr_ns,
                "detail": (
                    "غير حسّاس لكل الخط الأول (بيتا-لاكتام + فلوروكينولون): "
                    f"{', '.join(_dtr_ns)} — تعريف DTR في إرشادات IDSA. "
                    "الآلية غير محددة من اللوحة: قد تكون فقد بورين OprD + مضخات "
                    "الطرد + AmpC مُحدَث، أو إنزيم كاربابينيميز مكتسب (MBL شائع في "
                    "الشرق الأوسط). الاثنان يبدوان متطابقين على أقراص البيتا-لاكتام."
                ),
                "detail_en": (
                    "Non-susceptible to the whole first line (beta-lactams + fluoroquinolones): "
                    f"{', '.join(_dtr_ns)} — the IDSA definition of DTR. The panel cannot tell the "
                    "mechanism: OprD porin loss + efflux + derepressed AmpC, or an acquired "
                    "carbapenemase (MBLs are common in the Middle East). Both look identical on "
                    "beta-lactam disks."
                ),
                "action": (
                    "الخيارات المفضّلة (IDSA AMR Guidance 2026): Ceftolozane-Tazobactam · "
                    "Ceftazidime-Avibactam · Imipenem-Relebactam · Cefiderocol — "
                    "اطلب حساسية لها تحديداً. لا تعتمد على Colistin كخط أول. "
                    "أكّد وجود كاربابينيميز (mCIM / PCR للـ MBL) فقط إذا كان "
                    "سيغيّر الاختيار — MBL يُفشل الثلاثة الأولى ويترك Cefiderocol "
                    "أو Aztreonam-Avibactam. عزل + إبلاغ مكافحة العدوى."
                ),
            }
        return {
            "probability": "crpa", "dtr": False,
            "confidence": 60 if len(carb_R_list) >= 2 else 45,
            "active_betalactams": _active_bl,
            "mechanism": "Carbapenem-resistant P. aeruginosa — mechanism not determined",
            "markers_R": carb_R_list or ["Meropenem (I)"],
            "detail": (
                f"مقاومة كاربابينيم ({', '.join(carb_R_list) or 'Meropenem I'}) في "
                "P. aeruginosa. الآلية الأشيع فقد/تقليل بورين OprD ± مضخات طرد "
                "± AmpC مُحدَث — وليست إنزيم كاربابينيميز. لا يوجد في EUCAST "
                "خوارزمية معتمدة تفرّق بينهما من أقراص البيتا-لاكتام."
                + (f"  \nلا يزال حسّاساً لـ: {', '.join(_active_bl)}."
                   if _active_bl else "")
            ),
            "detail_en": (
                f"Carbapenem resistance ({', '.join(carb_R_list) or 'Meropenem I'}) in "
                "P. aeruginosa. The commonest mechanism is OprD porin loss ± efflux ± derepressed "
                "AmpC — not a carbapenemase. EUCAST has no validated algorithm that separates "
                "them from beta-lactam disks."
                + (f" Still susceptible to: {', '.join(_active_bl)}." if _active_bl else "")
            ),
            "action": (
                (f"ابدأ بـ {_active_bl[0]} بجرعة عالية وتسريب ممتد (extended infusion) "
                 "— IDSA: العزلة المقاومة للكاربابينيم والحسّاسة لبيتا-لاكتام تقليدي "
                 "تُعالَج بذلك البيتا-لاكتام، لا بـ Colistin. "
                 if _active_bl else
                 "راجع Ceftazidime / Cefepime / Piperacillin-Tazobactam / Aztreonam "
                 "في نفس اللوحة قبل التصعيد. ")
                + "أكّد الكاربابينيميز (mCIM / PCR) فقط إذا كان سيغيّر العلاج."
            ),
        }

    # ── 1. Carbapenemase tiers (highest priority) ─────────────────────────
    if len(carb_R_list) >= 2:
        return {
            "probability": "carbapenemase",
            "confidence": 92,
            "mechanism": "Carbapenemase (KPC / MBL / OXA-48-like) — Predicted",
            "markers_R": carb_R_list + primary_R,
            "detail": f"مقاومة لـ ≥2 كاربابينيم ({', '.join(carb_R_list)}) -- نمط Carbapenemase صريح.",
            "detail_en": (f"Resistant to ≥2 carbapenems ({', '.join(carb_R_list)}) — an overt "
                          "carbapenemase pattern."),
            "action": ("أرسل للمختبر المرجعي فوراً وحدّد نوع الإنزيم (NG-Test CARBA-5 أو PCR). عزل صارم. "
                       "KPC: Ceftazidime-avibactam أو Meropenem-vaborbactam أو Imipenem-relebactam؛ "
                       "OXA-48: Ceftazidime-avibactam؛ NDM/VIM/IMP: Aztreonam-avibactam أو "
                       "Ceftazidime-avibactam + Aztreonam أو Cefiderocol (IDSA 2026). "
                       "Colistin ليس خياراً مفضّلاً."),
        }
    if erta_R and (sir_map.get("Meropenem") in ("S", "I")) and not mero_R:
        # Ertapenem-R with Meropenem-S/I. Suggestive of OXA-48 (common in Egypt /
        # Middle East, which lifts the prior) -- but the SAME pattern arises from
        # porin loss + ESBL/AmpC with no true carbapenemase, and Ertapenem is the
        # carbapenem most affected by non-carbapenemase mechanisms. Confirm-first
        # signal, not a high-confidence call: keep confidence moderate and name
        # the alternative mechanism in the read-out.
        return {
            "probability": "possible_carbapenemase",
            "confidence": 62,
            "mechanism": "Possible OXA-48-like carbapenemase OR porin loss + ESBL/AmpC — Predicted",
            "markers_R": ["Ertapenem"] + primary_R,
            "detail": ("Ertapenem R مع Meropenem S/I -- نمط قد يوحي بـ OXA-48 (شائع في "
                       "مصر/الشرق الأوسط) أو بفقدان بورين + ESBL/AmpC بدون إنزيم "
                       "كاربابينيميز حقيقي."),
            "detail_en": ("Ertapenem R with Meropenem S/I — may suggest OXA-48 (common in "
                          "Egypt / the Middle East) or porin loss + ESBL/AmpC without a true "
                          "carbapenemase."),
            "action": "أكد بـ mCIM / PCR (OXA-48) قبل اعتماد التشخيص. راقب بحذر؛ قد تكون الكاربابينيمات أقل فعالية.",
        }
    if len(carb_R_list) == 1 or mero_I:
        return {
            "probability": "possible_carbapenemase",
            "confidence": 55,
            "mechanism": "Possible carbapenemase (low-level) — Predicted",
            "markers_R": carb_R_list or ["Meropenem (I)"],
            "detail": "مقاومة/توسط لكاربابينيم واحد -- يستلزم اختبار تأكيدي.",
            "detail_en": "Resistant / intermediate to one carbapenem — needs a confirmatory test.",
            "action": "أجرِ mCIM/CarbaNP. قد يكون فقدان بورين + ESBL/AmpC وليس carbapenemase حقيقياً.",
        }

    # ── 2. AmpC — Enterobacterales AmpC organisms only ────────────────────
    # AmpC (SPICE/SPACE) attribution requires an ENTEROBACTERALE (is_producer);
    # this keeps AmpC/ESBL mechanism calls scoped to Enterobacterales and lets a
    # non-Enterobacterale (P. aeruginosa/Hafnia) fall through to the producer
    # gate below. Cefoxitin is NOT required: it is intrinsically resistant in
    # these organisms and is stripped before marker computation, so its absence
    # here is expected — 3rd-gen cephalosporin R in an AmpC-prone Enterobacterale
    # is itself the derepression signal.
    if is_ampc_prone and is_producer and primary_R:
        return {
            "probability": "ampc",
            "confidence": 75,
            "mechanism": "Possible AmpC β-lactamase (Predicted)",
            "markers_R": primary_R,
            "detail": "مقاومة لـ 3rd-gen cephalosporin في كائن Enterobacterale منتج لـ AmpC مزمن -- نمط AmpC وليس ESBL.",
            "detail_en": ("3rd-generation cephalosporin resistance in an Enterobacterale with a "
                          "chromosomal AmpC — an AmpC pattern, not ESBL."),
            "action": "تجنب 3rd-gen cephalosporins حتى لو S. استخدم Cefepime أو Carbapenem. لا يُكتشف بـ DDST.",
        }

    # ── 2b. Plasmid-mediated AmpC in a NON-AmpC-prone Enterobacterale ─────
    #  Cefoxitin is the classic phenotypic discriminator: ESBLs do not hydrolyse
    #  cephamycins, so a true ESBL is normally cefoxitin-SUSCEPTIBLE, whereas AmpC
    #  (chromosomal or plasmid-borne) IS cefoxitin-resistant. In organisms with no
    #  chromosomal AmpC (E. coli, Klebsiella, Proteus mirabilis, Salmonella) a
    #  cefoxitin-R + 3rd-gen-R phenotype therefore points at acquired pAmpC or at
    #  porin loss -- not at a plain ESBL.
    #
    #  This is a QUALIFIER, not a re-diagnosis: cefoxitin resistance can also arise
    #  from porin loss in a genuine ESBL producer, so the report names both
    #  possibilities and tells the lab what the confirmatory test will do.
    if (is_producer and not is_ampc_prone and primary_R and cefoxitin_R
            and not _thin_panel):
        return {
            "probability": "ampc_plasmid",
            "confidence": 70,
            "mechanism": "Possible plasmid-mediated AmpC (pAmpC) or porin loss — not a plain ESBL",
            "markers_R": primary_R + ["Cefoxitin"],
            "detail": (
                "مقاومة للجيل الثالث **مع** مقاومة للـ Cefoxitin في كائن لا يحمل "
                "AmpC كروموسومي. الـ ESBL الكلاسيكي لا يحلّل السيفاميسينات، فيكون "
                "عادةً حسّاساً للـ Cefoxitin — والنمط ده يرجّح AmpC مكتسب "
                "(CMY-2 وأشباهه) أو فقد بورين، وليس ESBL بسيط."
            ),
            "detail_en": (
                "3rd-generation resistance WITH cefoxitin resistance in an organism that has no "
                "chromosomal AmpC. A classic ESBL does not hydrolyse cephamycins and is usually "
                "cefoxitin-susceptible — this pattern points to an acquired AmpC (CMY-2-like) or "
                "porin loss, not a plain ESBL."
            ),
            "action": (
                "⚠️ اختبار التأكيد (DDST / combination disk) قد يخرج **سالباً** — "
                "الكلافولانيت لا يثبّط AmpC. لا تعتمد على Amoxicillin-Clavulanate. "
                "الـ Cefepime غالباً يظل فعّالاً في AmpC (راجع نتيجته على اللوحة)، "
                "والكاربابينيم هو الخيار الآمن في العدوى الشديدة. "
                "التمييز النهائي يحتاج PCR."
            ),
        }

    # ── 3. ESBL (Enterobacterales ONLY) ───────────────────────────────────
    # ESBL is a mechanism DEFINED for Enterobacterales. A non-Enterobacterale
    # that is AmpC-prone (e.g. P. aeruginosa) must NEVER be labelled "ESBL":
    # any 3rd-gen cephalosporin R that survives intrinsic-stripping (i.e. an
    # ACQUIRED Ceftazidime-R) reflects derepressed chromosomal AmpC / efflux
    # (MexAB-OprM) / porin loss — not an ESBL.
    # A non-Enterobacterale (e.g. P. aeruginosa) is NEVER an ESBL producer.
    # After intrinsic-stripping, any residual 3rd-gen cephalosporin R is judged
    # on the drug's own AST result (an R drug is banned as R regardless); we do
    # NOT emit an ESBL/AmpC mechanism call here, which prevents both the false
    # "ESBL ALERT" and any "(ESBL)" label bleed onto this organism's β-lactams.
    if not is_producer:
        return {"probability": "low", "confidence": 10}

    if len(primary_R) >= 2:
        return {
            "probability": "high",
            "confidence": 88,
            "mechanism": "ESBL (Extended-Spectrum β-Lactamase) — Predicted",
            "markers_R": primary_R + second_R,
            "detail": f"مقاومة لـ {', '.join(primary_R)} -- احتمال ESBL مرتفع.",
            "detail_en": f"Resistant to {', '.join(primary_R)} — high probability of ESBL.",
            "action": "استخدم Carbapenem للعدوى الشديدة (MERINO 2018). تجنب جميع cephalosporins.",
        }
    if len(primary_R) == 1:
        # Classic single-marker ESBL pattern (e.g., Ceftriaxone R, Meropenem S)
        carbS = any(sir_map.get(d) == "S" for d in CARBAPENEMS)
        _base_conf = 72 if carbS else 60
        # لوحة رفيعة (marker أساسي واحد مُختبَر فقط) -> خفّض الثقة، فلا يُبنى حكم
        # ESBL قوي على اختبار سيفالوسبورين واحد بينما لم تُختبر بقية الـ 3rd-gen.
        if _thin_panel:
            _base_conf = min(_base_conf, 45)
        _detail = f"مقاومة لـ {primary_R[0]}" + (
            " مع كاربابينيم حساس -- نمط ESBL كلاسيكي." if carbS else ".")
        _detail_en = f"Resistant to {primary_R[0]}" + (
            " with a susceptible carbapenem — a classic ESBL pattern." if carbS else ".")
        if _thin_panel:
            _detail += (" ⚠️ لوحة محدودة: تم اختبار سيفالوسبورين أساسي واحد فقط "
                        "-- التفسير أقل موثوقية؛ وسّع اللوحة (Ceftazidime/Cefotaxime).")
            _detail_en += (" ⚠️ Limited panel: only one key cephalosporin was tested — the "
                           "reading is less reliable; extend the panel (Ceftazidime/Cefotaxime).")
        return {
            # FIX 2026-11-10 (round 2): a thin panel forced "moderate", and at
            # "moderate" the engine applied NO ESBL handling at all -- E. coli in
            # blood with Ceftriaxone R as the only 3rd-gen tested had
            # piperacillin-tazobactam and cefepime recommended without a word.
            # IDSA AMR Guidance: ceftriaxone non-susceptibility is the accepted
            # proxy for ESBL production in E. coli / Klebsiella / P. mirabilis.
            "probability": ("high" if (primary_R[0] in ("Ceftriaxone", "Cefotaxime")
                                       or (carbS and not _thin_panel)) else "moderate"),
            "confidence": (max(_base_conf, 70)
                           if primary_R[0] in ("Ceftriaxone", "Cefotaxime") else _base_conf),
            "mechanism": "Probable ESBL — Predicted",
            "markers_R": primary_R + med_R,
            "detail": _detail,
            "detail_en": _detail_en,
            "action": "أكد بـ Double-Disk Synergy Test (DDST) أو PCR. عامل كـ ESBL حتى التأكيد.",
        }
    if len(med_R) >= 2:
        return {
            "probability": "moderate",
            "confidence": 50,
            "mechanism": "Possible ESBL (lower-gen cephalosporin resistance) — Predicted",
            "markers_R": med_R,
            "detail": "مقاومة لـ ≥2 من الجيل الأقل -- يستدعي تأكيد ESBL.",
            "detail_en": "Resistant to ≥2 lower-generation cephalosporins — ESBL confirmation is needed.",
            "action": "أجرِ DDST. قد يكون ESBL مبكر أو آلية أخرى.",
        }

    return {"probability": "low", "confidence": 10}
