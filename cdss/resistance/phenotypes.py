# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Resistance-phenotype detection (MRSA, VRE, CRE, DTR, ...)."""
from typing import Any
from typing import Dict
from typing import List

import re
from cdss.resistance.mechanism import (
    _org_matches,
    _re_ws_collapse,
    predict_esbl,
)


# =========================================================
# MODULE 1 -- Resistance Phenotype Engine
# يحدد: ESBL / CRE / MRSA / VRE / MDR / XDR / PDR
# المرجع: EUCAST Breakpoint Tables v16.1, CLSI M100 Ed36, CDC/ECDC 2017
# =========================================================
PHENOTYPE_RULES = {
    # ── DERIVED phenotypes (2026-11-10) ──────────────────────────────────────
    # Not marker rules: emitted from predict_esbl() / the organism itself at
    # the end of detect_resistance_phenotypes(). Registered here so every
    # name a detector emits is a real key (and the marker loop skips them).
    "ESBL": {
        "derived": True, "organisms": [], "markers": [],
        "icon": "🟠", "label": "ESBL -- Extended-Spectrum β-Lactamase (predicted)",
        "detail": "مقاومة للجيل الثالث في Enterobacterale — نمط ESBL متوقع.",
        "action": ("المثانة: Nitrofurantoin/TMP-SMX؛ الحويضة: TMP-SMX/FQ؛ تجرثم الدم: "
                   "Carbapenem (IDSA 2026). أكّد بـ DDST حسب سياسة المعمل."),
        "isolation": False,
    },
    "AMPC": {
        "derived": True, "organisms": [], "markers": [],
        "icon": "🟠", "label": "AmpC β-lactamase (predicted)",
        "detail": "مقاومة للجيل الثالث مع نمط AmpC (كروموسومي مُفرط أو بلازميدي).",
        "action": ("Cefepime إذا S (MIC ≤ 2)؛ Carbapenem إذا SDD/I أو حالة حرجة "
                   "(IDSA 2026). لا Ceftriaxone ولا Pip-Tazo للعدوى الغازية."),
        "isolation": False,
    },
    "STENO": {
        "derived": True, "organisms": ["Stenotrophomonas maltophilia"], "markers": [],
        "icon": "🟠", "label": "S. maltophilia -- intrinsically carbapenem-resistant",
        "detail": "L1 metallo-β-lactamase + L2 — مقاومة جوهرية لكل الكاربابينيمات.",
        "action": "العدوى الغازية: Cefiderocol منفرداً (IDSA 2026) — راجع لوحة العلاج.",
        "isolation": False,
    },
    "MRSA": {
        "organisms": ["Staphylococcus aureus","MRSA","Staphylococcus spp."],
        "markers":   [("Oxacillin","R"), ("Cefoxitin","R")],
        "require_any": 1,  # CLSI M100: أي surrogate لوحده (Oxacillin أو Cefoxitin) R يؤكد MRSA
        "fallback":  [("Vancomycin","S"), ("Linezolid","S")],  # حساس لهم -> likely MRSA
        "icon":  "🔴",
        "label": "MRSA -- Methicillin-Resistant S. aureus",
        "detail": "مقاوم للـ Methicillin (mecA gene). جميع البيتا-لاكتام غير فعالة.",
        "action": "Vancomycin أو Linezolid حسب الشدة. بروتوكول عزل إلزامي.",
        "isolation": True,
    },
    "VRE": {
        "organisms": ["Enterococcus faecalis","Enterococcus faecium","VRE","Enterococcus spp."],
        "markers":   [("Vancomycin","R")],
        "icon":  "🔴",
        "label": "VRE -- Vancomycin-Resistant Enterococcus",
        "detail": "مقاوم للـ Vancomycin (vanA/vanB gene). خطر انتشار في المستشفى.",
        "action": "Linezolid أو Daptomycin. عزل فوري. إبلاغ مكافحة العدوى.",
        "isolation": True,
    },
    "CRE": {
        # FIX 2026-08-01 (second pass). This list is a FOURTH organism table,
        # independent of clinical_data.INTRINSIC_RESISTANCE, ORGANISM_PROFILE
        # and clinical_matrix._ORG_CANON — and it was not updated when the
        # AmpC genera were added, nor did it ever cover Salmonella, Shigella or
        # the unspeciated fallback.
        #
        # The failure was silent and severe: predict_esbl() returned
        # "carbapenemase" and the red banner appeared, but because no phenotype
        # was detected the isolate got NO "🚨 عزل فوري مطلوب" isolation alert,
        # NO combination-therapy panel (so Ceftazidime-Avibactam and
        # Meropenem-Vaborbactam were never suggested), and evaluate_deescalation
        # did not treat it as a Reserve organism. A carbapenem-resistant isolate
        # that nobody is told to isolate is the one that spreads through a ward.
        #
        # "Citrobacter freundii" is spelled out because the entry here was
        # "Citrobacter spp." and neither string is a substring of the other, so
        # the species profile added earlier that day matched nothing.
        "organisms": ["Klebsiella spp.", "E. coli", "Escherichia coli",
                      "Enterobacter cloacae", "Enterobacter spp.",
                      "Proteus mirabilis", "Proteus vulgaris", "Proteus spp.",
                      "Klebsiella pneumoniae", "Klebsiella oxytoca",
                      "Serratia marcescens", "Serratia spp.", "Citrobacter spp.",
                      "Citrobacter freundii", "Citrobacter koseri",
                      "Morganella morganii", "Providencia spp.",
                      "Hafnia alvei", "Salmonella spp.", "Shigella spp.",
                      "Enterobacterales (unspeciated)", "Enterobacterales"],
        "markers":   [("Imipenem/Cilastatin","R"),("Meropenem","R"),("Ertapenem","R")],
        "require_any": 1,  # واحد كافٍ
        "icon":  "🚨",
        # Proteeae: imipenem R alone does not qualify (CDC CRE definition).
        "exclude_markers_for": {("proteus", "morganella", "providencia"): ["Imipenem/Cilastatin"]},
        "label": "CRE -- Carbapenem-Resistant Enterobacterales",
        "detail": "مقاوم للكاربابينيم -- أخطر أنماط المقاومة في العالم.",
        # FIX 2026-11-10: was "Colistin + Fosfomycin أو Ceftazidime-Avibactam"
        # for every CRE. The choice depends on the enzyme class (IDSA 2026),
        # and polymyxin combinations are not preferred.
        "action": ("حدّد نوع الكاربابينيميز (NG-Test CARBA-5 أو PCR) — العلاج يتوقف عليه: "
                   "KPC ← Ceftazidime-avibactam / Meropenem-vaborbactam / Imipenem-relebactam؛ "
                   "OXA-48 ← Ceftazidime-avibactam؛ NDM/VIM/IMP ← Aztreonam-avibactam أو "
                   "Ceftazidime-avibactam + Aztreonam أو Cefiderocol (IDSA 2026). "
                   "Colistin ليس خياراً مفضّلاً. أرسل للمختبر المرجعي."),
        "isolation": True,
    },
    "CRAB": {
        "organisms": ["Acinetobacter baumannii", "Acinetobacter spp."],
        "markers":   [("Imipenem/Cilastatin","R"),("Meropenem","R")],
        "require_any": 1,
        "icon":  "🚨",
        "label": "CRAB -- Carbapenem-Resistant Acinetobacter baumannii",
        "detail": "XDR/PDR Acinetobacter -- أصعب الكائنات علاجاً في ICU.",
        # FIX 2026-11-10: was "Colistin ± Rifampicin". IDSA 2026 prioritises
        # sulbactam-durlobactam + a carbapenem; rifampicin adds nothing (AIDA).
        "action": ("IDSA 2026: Sulbactam-durlobactam + Meropenem أو Imipenem هو المفضّل. "
                   "إن لم يتوفر: Ampicillin-sulbactam جرعة عالية (9 g sulbactam يومياً) + دواء "
                   "ثانٍ فعّال (Polymyxin B أو Minocycline أو Tigecycline أو Cefiderocol). "
                   "لا Rifampicin. استشارة الأمراض المعدية."),
        "isolation": True,
    },
    "CRPA": {
        # FIX 2026-08-03. The rule was:
        #     markers = Imipenem R, Meropenem R, Pip-Tazo R, Ceftazidime R
        #     require_any = 2
        # Pip-Tazo and Ceftazidime are NOT carbapenems, and putting them in a
        # definition literally named "Carbapenem-Resistant" broke it BOTH ways:
        #
        #   MISSED   Meropenem R alone  -> no CRPA, no isolation alert, no
        #            combination panel. Egyptian panels routinely carry
        #            meropenem as the only carbapenem, so a genuine CRPA
        #            bacteraemia produced no alert at all.
        #   OVER-CALLED  Ceftazidime R + Pip-Tazo R with BOTH carbapenems S
        #            -> "CRPA", 🚨 immediate isolation and an XDR salvage panel,
        #            for a carbapenem-SUSCEPTIBLE isolate. predict_esbl() said
        #            "low" for the same isolate on the same screen.
        #
        # CDC / IDSA / EUCAST all define CRPA as resistance to AT LEAST ONE
        # carbapenem. Ceftazidime and Pip-Tazo belong to DTR (difficult-to-treat
        # resistance), a separate concept with its own therapeutic implication —
        # see the DTR_PA rule below. Note the sibling rules were already correct:
        # CRAB requires 1 of 2 carbapenems, CRE requires 1 of 3. CRPA was the
        # only outlier, with no comment explaining why.
        #
        # Ertapenem is deliberately absent: P. aeruginosa is INTRINSICALLY
        # resistant to it, so an ertapenem-R result carries no information here.
        "organisms": ["Pseudomonas aeruginosa", "Pseudomonas spp."],
        # Doripenem belongs in this definition clinically but is NOT in this
        # formulary's 51 agents, so a marker naming it can never match and is
        # exactly the dead-rule pattern this audit keeps removing. Add it back
        # here the day the agent is added to abx_guidelines.py.
        "markers":   [("Imipenem/Cilastatin", "R"), ("Meropenem", "R")],
        "require_any": 1,
        "icon":  "🔴",
        "label": "CRPA -- Carbapenem-Resistant Pseudomonas aeruginosa",
        "detail": "مقاوم لواحد على الأقل من الكاربابينيمات. خيارات علاجية محدودة.",
        "action": "Ceftolozane-Tazobactam أو Ceftazidime-Avibactam حسب الحساسية. "
                  "Colistin كخيار إنقاذ. راجع لوحة العلاج التوليفي.",
        "isolation": True,
    },
    "DTR_PA": {
        # Difficult-to-Treat Resistance (Kadri et al., Clin Infect Dis 2018;
        # adopted by IDSA AMR Guidance v4.0). DEFINED as non-susceptibility to
        # ALL of: piperacillin-tazobactam, ceftazidime, cefepime, aztreonam,
        # meropenem, imipenem, ciprofloxacin and levofloxacin — i.e. every
        # first-line agent has failed, which is a different and narrower thing
        # than carbapenem resistance and points at the novel beta-lactams rather
        # than at colistin.
        #
        # This is where Ceftazidime and Pip-Tazo actually belong. They were
        # previously sitting inside the CRPA marker list, which is what made a
        # carbapenem-susceptible isolate register as carbapenem-resistant.
        #
        # DEFINITION FIX 2026-08-03 (web-verified against Kadri et al. 2018 and
        # IDSA): DTR is non-susceptibility to ALL EIGHT agents, not a majority.
        # A 6-of-8 threshold over-calls it — an isolate still susceptible to
        # cefepime and levofloxacin is not difficult-to-treat, and labelling it
        # so pushes a clinician toward the novel beta-lactams when a first-line
        # agent still works.
        #
        # But requiring all eight to be PRESENT on the panel would make the rule
        # unreachable: no Egyptian panel carries aztreonam plus all three
        # anti-pseudomonal beta-lactams plus both fluoroquinolones. The engine
        # therefore requires every one of the eight that WAS TESTED to be R,
        # with a floor of 5 tested agents so a two-drug panel cannot qualify.
        # That is the faithful reading of "non-susceptible to all" under partial
        # testing, and it is handled by `require_all_tested` below rather than
        # by require_any.
        "organisms": ["Pseudomonas aeruginosa", "Pseudomonas spp."],
        "markers":   [("Piperacillin + Tazobactam", "R"), ("Ceftazidime", "R"),
                      ("Cefepime", "R"), ("Aztreonam", "R"),
                      ("Meropenem", "R"), ("Imipenem/Cilastatin", "R"),
                      ("Ciprofloxacin", "R"), ("Levofloxacin", "R")],
        "require_any": 5,          # floor: at least 5 of the 8 must be on the panel
        "require_all_tested": True, # and every tested one must be R
        "icon":  "🔴",
        "label": "DTR-P. aeruginosa -- Difficult-to-Treat Resistance",
        "detail": "مقاومة لكل الخطوط الأولى (بيتا-لاكتام + فلوروكينولون). "
                  "المفهوم أضيق من CRPA ويوجّه نحو البيتا-لاكتامات الحديثة.",
        "action": "Ceftolozane-Tazobactam أو Ceftazidime-Avibactam أو Cefiderocol "
                  "حسب الحساسية — يُفضَّل على Colistin (سمّية أقل، نتائج أفضل). "
                  "استشارة الأمراض المعدية مطلوبة.",
        "isolation": True,
    },
}

def detect_resistance_phenotypes(
    organism: str, sir_map: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    يكتشف الـ phenotypes المقاومة من نمط S/I/R.
    يعيد قائمة بكل الـ phenotypes المكتشفة.
    """
    if not sir_map:
        return []
    detected = []
    # `(organism or "")`: predict_esbl carried the same bare .lower() until
    # 2026-08-01 and raised AttributeError on None while every other entry point
    # in this file coerced. Same fix, same reason — fail closed, do not raise.
    org_lower = _re_ws_collapse(organism)

    for ph_name, rule in PHENOTYPE_RULES.items():
        if rule.get("derived"):
            continue          # emitted below, not by markers
        # Is this organism a candidate for this phenotype?
        # FIX 2026-08-03: this was an unguarded two-way substring test, the same
        # trap already fixed in is_esbl_producer(). `"" in "klebsiella spp."` is
        # True, so a blank or one-character organism matched EVERY rule and came
        # back claiming MRSA + VRE + CRE + CRAB simultaneously — four
        # immediate-isolation banners and four salvage-therapy panels for an
        # isolate with no name. _org_matches() carries the length floor and the
        # non-informative-token list, so the guard now lives in one place
        # instead of being re-derived per call site.
        if not _org_matches(org_lower, [o.lower() for o in rule["organisms"]]):
            continue

        markers   = rule.get("markers", [])
        for _toks, _excl in (rule.get("exclude_markers_for") or {}).items():
            if any(t in org_lower for t in _toks):
                markers = [(d, e) for d, e in markers if d not in _excl]
        req_any   = rule.get("require_any", len(markers))  # default: كل الـ markers

        # عدد الـ markers المطابقة
        matched = sum(1 for drug, expected in markers
                      if sir_map.get(drug) == expected)

        # `require_all_tested` (added 2026-08-03 for DTR-P. aeruginosa): the
        # definition is non-susceptibility to ALL of a named set, but a real
        # panel rarely carries every agent in it. Requiring all EIGHT to be
        # present makes the rule unreachable; requiring a mere majority
        # over-calls it. So: every listed agent that WAS tested must match, and
        # `require_any` becomes a floor on how many had to be tested at all.
        if rule.get("require_all_tested"):
            tested = [(d, e) for d, e in markers if sir_map.get(d) is not None]
            if len(tested) < req_any:
                continue
            if any(sir_map.get(d) != e for d, e in tested):
                continue
            matched = len(tested)

        if matched >= req_any and matched > 0:
            detected.append({
                "phenotype": ph_name,
                "icon":      rule["icon"],
                "label":     rule["label"],
                "detail":    rule["detail"],
                "action":    rule["action"],
                "isolation": rule.get("isolation", False),
                "matched_markers": [
                    drug for drug, exp in markers if sir_map.get(drug) == exp
                ],
            })

    # ── Phenotypes the organism NAME already states (added 2026-11-12) ──────
    # "MRSA" and "VRE" are entries of the organism pick-list. When the lab
    # reports the isolate under that name the phenotype is a given -- yet the
    # card (isolation precautions, salvage regimens) only appeared if the
    # marker drug also happened to be on the panel. A marker reported S
    # contradicts the name: that is left to QC, not asserted here.
    for _name, _rx, _markers in (("MRSA", r"\bmrsa\b", ("Oxacillin", "Cefoxitin")),
                                 ("VRE", r"\bvre\b", ("Vancomycin",))):
        if (_name not in {d["phenotype"] for d in detected}
                and re.search(_rx, org_lower)
                and not any(sir_map.get(m) == "S" for m in _markers)):
            _r = PHENOTYPE_RULES[_name]
            detected.append({"phenotype": _name, "icon": _r["icon"], "label": _r["label"],
                             "detail": _r["detail"], "action": _r["action"],
                             "isolation": _r.get("isolation", False),
                             "matched_markers": []})

    # ── Mechanism phenotypes from the predictor (added 2026-11-10) ──────────
    # The ESBL therapy panel existed but no detector ever emitted "ESBL", so
    # it could never be shown; AmpC and S. maltophilia had no panel at all.
    # Isolation is False: these change THERAPY, not the isolation protocol
    # (local IPC policy decides contact precautions for ESBL).
    _have = {d["phenotype"] for d in detected}

    def _derived(_name: str) -> Dict[str, Any]:
        _r = PHENOTYPE_RULES[_name]
        return {"phenotype": _name, "icon": _r["icon"], "label": _r["label"],
                "detail": _r["detail"], "action": _r["action"],
                "isolation": _r["isolation"], "matched_markers": []}

    if not ({"CRE", "CRAB", "CRPA", "DTR_PA"} & _have):
        try:
            _pm = (predict_esbl(organism, sir_map) or {}).get("probability")
        except Exception:          # harnesses that lift this function alone
            _pm = None
        if _pm == "high":
            detected.append(_derived("ESBL"))
        elif _pm in ("ampc", "ampc_plasmid"):
            detected.append(_derived("AMPC"))
    if "stenotrophomonas" in org_lower:
        detected.append(_derived("STENO"))

    # MRSA fallback: لو S. aureus + Vancomycin S + Linezolid S -> اشتباه MRSA
    if (("staphylococcus aureus" in org_lower or "staphylococcus spp" in org_lower)
            and "MRSA" not in [d["phenotype"] for d in detected]):
        vanco_s   = sir_map.get("Vancomycin") == "S"
        linezo_s  = sir_map.get("Linezolid")  == "S"
        beta_r    = any(sir_map.get(d) == "R" for d in
                        ["Amoxicillin + Clavulanic acid","Cephalexin","Cefuroxime"])
        screen_i = [d for d in ("Cefoxitin", "Oxacillin") if sir_map.get(d) == "I"]
        if screen_i:
            # No intermediate category exists for the mecA surrogates in staphylococci.
            detected.append({
                "phenotype": "Possible MRSA",
                "icon":      "⚠️",
                "label":     "Possible MRSA -- تأكيد مطلوب",
                "detail":    (" و ".join(screen_i) + " = I: لا توجد فئة Intermediate لهذا الاختبار في "
                              "المكورات العنقودية — مقاومة الميثيسيلين غير مستبعدة."),
                "action":    "أعِد Cefoxitin disk diffusion أو اطلب PCR (mecA/mecC).",
                "isolation": False,
                "matched_markers": [],
            })
        elif beta_r and (vanco_s or linezo_s):
            # Say what the panel shows: a cefoxitin/oxacillin already reported S makes
            # this a DISCORDANT result to repeat, not a screen that was never done.
            screen_s = [d for d in ("Cefoxitin", "Oxacillin") if sir_map.get(d) == "S"]
            detected.append({
                "phenotype": "Possible MRSA",
                "icon":      "⚠️",
                "label":     "Possible MRSA -- تأكيد مطلوب",
                "detail":    ("نتائج متعارضة: " + " و ".join(screen_s) + " = S مع بيتا-لاكتام آخر مقاوم "
                              "(BORSA / mecC / خطأ قراءة) — مقاومة الميثيسيلين غير مستبعدة."
                              if screen_s else
                              "نمط مقاومة beta-lactam مع حساسية للـ Vancomycin/Linezolid يشير لـ MRSA."),
                "action":    ("أعِد Cefoxitin disk diffusion أو اطلب PCR (mecA/mecC) لحسم التعارض."
                              if screen_s else
                              "أجرِ Cefoxitin disk diffusion أو PCR (mecA) للتأكيد."),
                "isolation": False,
                "matched_markers": [],
            })

    return detected
