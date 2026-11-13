# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Whole-panel steps that run after every drug has been judged.

Each takes the four buckets and returns them; none can move a drug out of
`banned`.
"""
from typing import Dict, List

from cdss.common.specimen import classify_specimen
from cdss.therapy.intrinsic import build_banned_item
from cdss.therapy.therapy_rules import CLINICAL_NOTE_EN as _NOTE_EN


def apply_upper_uti(cx, allowed, warned, banned, preg_warn_items):
    """Pyelonephritis / cUTI: lower-tract-only agents are not options (IDSA cUTI 2025)."""
    # ── Upper UTI / pyelonephritis: lower-tract-only agents (2026-11-10) ──────
    # Nitrofurantoin, oral fosfomycin and norfloxacin do not reach renal tissue
    # or serum; IDSA cUTI 2025 and the IDSA AMR guidance restrict them to
    # cystitis. They used to be offered for pyelonephritis because the engine
    # only knew "urine", not which part of the urinary tract was infected.
    if cx.uti_upper:
        _lower_only = {"Nitrofurantoin", "Fosfomycin", "Norfloxacin"}
        _hit = ({d["name"] for d in allowed if d.get("name") in _lower_only}
                | {d["name"] for d in warned if d.get("name") in _lower_only}
                | {d["name"] for d in preg_warn_items if d.get("name") in _lower_only})
        allowed = [d for d in allowed if d.get("name") not in _lower_only]
        warned = [d for d in warned if d.get("name") not in _lower_only]
        preg_warn_items = [d for d in preg_warn_items if d.get("name") not in _lower_only]
        for _nm in sorted(_hit):
            banned.append(build_banned_item(
                _nm, "uti_upper",
                "التهاب حويضة / cUTI -- عامل للمثانة فقط.",
                f"{_nm}: لا يحقق تركيزاً علاجياً في نسيج الكلى أو الدم، فلا يُستخدم لالتهاب "
                "الحويضة أو cUTI أو الإنتان البولي (IDSA cUTI 2025). الخيارات: TMP-SMX أو "
                "Ciprofloxacin/Levofloxacin إذا كانت حساسة، أو بيتا-لاكتام وريدي حسب المزرعة."))
    return allowed, warned, banned, preg_warn_items


def apply_clinical_notes(cx, allowed, warned, banned, preg_warn_items, post_notes):
    """Attach the notes recorded by the rules; a 'warn' note demotes allowed -> warned."""
    # ── Post-loop clinical notes (2026-11-10) ─────────────────────────────────
    # Applied after every hard ban has had its chance: a note never rescues a
    # drug from `banned`, and a "warn" note only DEMOTES allowed -> warned.
    if post_notes:
        _banned_names = {b.get("name") for b in banned if isinstance(b, dict)}
        _new_allowed = []
        for _it in allowed:
            _nm = _it.get("name")
            if _nm in post_notes and _nm not in _banned_names:
                _lvl, _note, _rsn = post_notes[_nm]
                _it = dict(_it)
                _it["clinical_note"] = _note
                _it["clinical_note_en"] = _NOTE_EN.get(_rsn, _NOTE_EN["organism_caution"])
                if _lvl == "warn":
                    _it["warning_reason"] = _rsn
                    warned.append(_it)
                    continue
            _new_allowed.append(_it)
        allowed = _new_allowed
        for _bucket in (warned, preg_warn_items):
            for _it in _bucket:
                _nm = _it.get("name")
                if _nm in post_notes and not _it.get("clinical_note"):
                    _it["clinical_note"] = post_notes[_nm][1]
                    _it["clinical_note_en"] = _NOTE_EN.get(post_notes[_nm][2],
                                                           _NOTE_EN["organism_caution"])
    return allowed, warned, banned, preg_warn_items


def flag_intermediate(cx, allowed, warned, banned, preg_warn_items):
    """`culture_intermediate` is a fact of its own, independent of warning_reason."""
    # ── The Intermediate fact is INDEPENDENT of warning_reason ───────────────
    # DEFECT 2026-08-01: `warning_reason` is a single slot and the branches above
    # are ordered hard-ban -> hepatic -> renal -> intermediate, each ending in
    # `continue`. So for a patient with renal impairment an Intermediate result
    # was relabelled "renal_adjustment" and the I vanished from the report: the
    # dedicated "⚠ Intermediate (I) on culture — use only if no better option"
    # banner filters on warning_reason == "intermediate_culture" and no longer
    # matched.
    #
    # The two facts are not merely both true, they pull OPPOSITE WAYS. EUCAST
    # redefined I as "Susceptible, Increased exposure" — the agent works only at
    # a HIGHER dose or longer infusion — while the renal note instructs the
    # clinician to REDUCE the dose. Showing one and hiding the other is the
    # worst of the three possible outputs.
    #
    # Reordering the branches was rejected: the ordering is load-bearing (see
    # the pregnancy block) and moving it risks letting a caution pre-empt a hard
    # ban. A separate key costs nothing and cannot be overwritten.
    for _item in warned:
        _item["culture_intermediate"] = (cx.sir.get(_item.get("name")) == "I")
    for _item in allowed:
        _item["culture_intermediate"] = False   # an I never reaches allowed
    return allowed, warned, banned, preg_warn_items


def sort_by_priority(cx, allowed, warned, banned, preg_warn_items):
    """Stable sort of the three positive buckets by formulary priority."""
    allowed         = sorted(allowed,         key=lambda x: x.get("priority", 999))
    warned          = sorted(warned,          key=lambda x: x.get("priority", 999))
    preg_warn_items = sorted(preg_warn_items, key=lambda x: x.get("priority", 999))
    return allowed, warned, banned, preg_warn_items


def apply_specimen_filter(cx, allowed, warned, banned, preg_warn_items):
    """Urine-only agents are specimen-inappropriate outside urine (stool keeps norfloxacin)."""
    # ── Specimen-appropriateness filter ───────────────────────────────────────
    # Urine-only agents achieve therapeutic concentrations ONLY in urine:
    #   • Nitrofurantoin / Fosfomycin (oral): negligible serum & tissue levels
    #     -> useless for bacteremia, pneumonia, wound, meningitis.
    #   • Norfloxacin: poor serum levels -> urinary (and some GI) use only.
    # They are BANNED (with a reason) for every non-urine systemic specimen.
    # For stool/GI, Norfloxacin retains an enteric role so only Nitro/Fosfo go.
    # Canonical classifier, not a raw substring test. Three different "is this
    # urine?" tests used to coexist in this file and they disagreed: the ESBL
    # branch asked classify_specimen(), this filter asked `"urine" in text`, and
    # _hide_urine_only() asked a third. For "MSU", "Midstream" or "Catheter
    # specimen" the first said urine and the other two said not-urine, so
    # Nitrofurantoin and Fosfomycin were banned off a genuine urine sample as
    # "specimen-inappropriate" -- removing the two best-targeted oral agents for
    # an uncomplicated UTI. One classifier, one answer.
    _spec_cat_final = classify_specimen(cx.specimen)
    _spec_l     = (cx.specimen or "").lower()
    is_urine    = _spec_cat_final == "urine"
    is_stool_gi = _spec_cat_final == "stool"

    if not is_urine:
        if is_stool_gi:
            _urine_only = {"Nitrofurantoin", "Fosfomycin"}   # Norfloxacin has GI use
            _reason = ("عامل بولي فقط -- لا يصل لتركيز علاجي داخل الأمعاء؛ "
                       "غير مناسب لعدوى الجهاز الهضمي.")
        else:
            _urine_only = {"Nitrofurantoin", "Fosfomycin", "Norfloxacin"}
            _reason = ("عامل بولي فقط -- لا يحقق تركيزاً علاجياً في الدم أو الأنسجة؛ "
                       "غير مناسب للعدوى الجهازية (دم / رئة / جرح / سائل نخاعي). "
                       "(ملاحظة: Fosfomycin الوريدي استثناء غير متوفر في هذه القائمة.)")
        _moved = ({d["name"] for d in allowed if d.get("name") in _urine_only} |
                  {d["name"] for d in warned  if d.get("name") in _urine_only} |
                  {d["name"] for d in preg_warn_items if d.get("name") in _urine_only})
        allowed = [d for d in allowed if d.get("name") not in _urine_only]
        warned  = [d for d in warned  if d.get("name") not in _urine_only]
        # Also purge urine-only agents from the pregnancy-warning list: for a
        # non-urine specimen they are specimen-inappropriate regardless of
        # pregnancy status, so they belong in 'banned' (below), not as a
        # standalone pregnancy note that would otherwise leave them unflagged.
        preg_warn_items = [d for d in preg_warn_items if d.get("name") not in _urine_only]
        for _nm in sorted(_moved):
            banned.append(build_banned_item(
                _nm, "specimen",
                "عامل بولي فقط -- غير مناسب لهذه العينة.", _reason,
            ))
    return allowed, warned, banned, preg_warn_items
