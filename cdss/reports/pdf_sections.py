# -*- coding: utf-8 -*-
# © Dr. Hussein Ali — Orange Lab, 6 October City, Egypt
# Microbiology CDSS — All Rights Reserved
"""The sections of the clinical PDF, one function each.

Split out of report_service.generate_pdf_html_report() (v6.7, 2026-11-14),
which was one 1,000-line function: every section shared every local, so a
change to the pregnancy card could reach the ranked list. Each section now
receives exactly what it reads, by keyword, and appends its HTML to `H`.

The bodies moved byte-for-byte; the golden-output test
(tests/test_report_split.py) holds the English and Arabic HTML, the text
report and the decision-tree image to the pre-split output for 600 cases.

None of these decides anything clinical -- they render what run_analysis()
decided (see report_service's module docstring).
"""
import re

from cdss.common.renal import crcl_label
from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.formulary.abx_guidelines import normalize_abx_key
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.reports.html_utils import _esc
from cdss.reports.html_utils import _score_color
from cdss.reports.i18n_en import alert_en
from cdss.resistance.mdr import MDR_INFO
from cdss.reports.pdf_parts import avoid_reason_tag
from cdss.resistance.mdr import (mdr_display_label, physician_mdr_categories,  # noqa: F401
                               physician_mdr_label, physician_mdr_level)
from cdss.stewardship.duration import annotate_regimen_note
from cdss.stewardship.ranking import route_label
from cdss.stewardship.syndrome import INFECTION_SYNDROMES
from cdss.therapy.notes import warned_note_for
from cdss.therapy.panel_filters import _drop_intrinsic


def section_ranked(
    *, H,
    AWARE_CARD,
    AWARE_CLR,
    AWARE_PILL,
    _T,
    _rnote,
    is_preg,
    is_renal,
    lang,
    organism,
    pill,
    preg_warn_items,
    ranked,
    sir_map,
    specimen,
) -> None:
    """Recommended therapy, ranked (FIRST-LINE / ALTERNATIVE rows)."""
    # ── RECOMMENDED THERAPY — RANKED (Page 1 — compact like orange_lab) ──────
    if ranked:
        H.append(f'<div class="sec-ttl">{_T["recommended"]}</div>')
        # ── Line-of-therapy label is SITE-SPECIFIC, not AWaRe ────────────────
        # AWaRe (Access/Watch/Reserve) is a stewardship/conservation class, NOT a
        # clinical preference rank for this infection. Using it as the "line" made an
        # Access aminoglycoside (Gentamicin) show as "First-line" for a Sputum case,
        # sitting *below* the actually-preferred Watch agents — clinically misleading.
        # The first-line set now comes from the syndrome table (curated per specimen,
        # e.g. Sputum -> Amox/Clav, Levofloxacin, Azithromycin). AWaRe stays only as
        # the row tint + pill on the right.
        # First-line set is ORGANISM-aware first (curated per organism), then falls
        # back to the specimen syndrome. This stops e.g. Azithromycin being labelled
        # "FIRST-LINE" for an Enterobacterales (macrolides aren't first-line for GNB),
        # even though the CAP syndrome lists it as an empiric first choice.
        _prof_fl = _drop_intrinsic(
            (ORGANISM_PROFILE.get(organism) or {}).get("first_line") or [], organism)
        _syn_fl  = INFECTION_SYNDROMES.get((specimen, None), {})
        _fl_src  = _prof_fl or (_syn_fl.get("first_choice") or [])
        _fl_norm = {normalize_abx_key(n) for n in _fl_src}
        prev_tier = ""
        # If AST + safety filtering left NO curated first-line agent standing,
        # labelling every surviving row "ALTERNATIVE" leaves the document with
        # no primary recommendation. Detect that and promote the top row.
        _fl_survives = any(
            normalize_abx_key(_r.get("name","")) in _fl_norm for _r in ranked
        ) if _fl_norm else False
        # v6.6: when a guideline names the preferred agents for this mechanism and
        # site (IDSA 2026 -- ESBL, AmpC, CRE, DTR-PA, CRAB, MRSA ...), THAT is the
        # first line, not the organism's generic list (E. coli's generic first
        # line is the urinary agents, which made TMP-SMX "FIRST-LINE" and the
        # carbapenems "ALTERNATIVE" for an ESBL bacteraemia).
        _guide_any = any(_r.get("_guideline_preferred") for _r in ranked)
        for i, _rd in enumerate(ranked, 1):
            _raw  = _rd.get("aware","")
            _nm_norm = normalize_abx_key(_rd.get("name",""))
            if _guide_any:
                _tlbl = "FIRST-LINE" if _rd.get("_guideline_preferred") else "ALTERNATIVE"
            elif _fl_norm and _fl_survives:
                _tlbl = "FIRST-LINE" if _nm_norm in _fl_norm else "ALTERNATIVE"
            else:                                   # no curated syndrome list -> rank by position
                _tlbl = "PRIMARY" if i == 1 else "ALTERNATIVE"
            _clr  = AWARE_CLR.get(_raw,"#444")      # drug name + pill colour = AWaRe (stewardship)
            _hclr = "#1e8449" if _tlbl in ("FIRST-LINE", "PRIMARY") else "#0d3b66"  # header colour = line
            _ccss = AWARE_CARD.get(_raw,"")
            _sirv = sir_map.get(_rd.get("name",""),"S")
            _rte  = "PO" if route_label(_rd, specimen) == "PO" else "IV/IM"
            _rnl  = _esc(_rnote(_rd)) if is_renal else ""
            _dose = _esc(_rd.get("gate_dose_note_en" if lang == "en" else "gate_dose_note") or "")
            # v7.0: low muscle mass -- creatinine overestimates GFR; levels, not CrCl
            _tdm = _esc(_rd.get("tdm_note_en" if lang == "en" else "tdm_note") or "")
            if _tlbl != prev_tier:
                H.append(f'<div class="tier-sep" style="color:{_hclr};border-color:{_hclr}">{_tlbl}</div>')
                prev_tier = _tlbl
            H.append(
                f'<div class="ranked-row" style="{_ccss};border-radius:1.5mm;padding:1mm 2.5mm;margin:0.3mm 0">'
                '<div style="flex:1;min-width:0;overflow-wrap:anywhere">'
                f'<b style="font-size:10.5pt;color:{_clr}">{i}. {_esc(_rd.get("name",""))}</b>'
                f'&ensp;<span class="ltr" style="background:#fff;border:0.4pt solid {_clr};color:{_clr};'
                f'font-size:8.5pt;padding:0.3mm 2.5mm;border-radius:1mm">{_sirv}</span>'
                f'&ensp;<span style="font-size:8.5pt;color:#555">{_rte}</span>'
                + (f'&ensp;<small style="color:#b7770d">⚠ {_rnl}</small>' if _rnl else "")
                + (f'&ensp;<small style="color:#0d3b66">💉 {_dose}</small>' if _dose else "")
                + (f'<div style="font-size:7.8pt;color:#b7770d">⚠ {_tdm}</div>' if _tdm else "")
                + '</div>'
                f'<div>{pill(_raw, AWARE_PILL.get(_raw,""))}</div>'
                '</div>'
            )
        if is_preg and preg_warn_items:
            H.append('<div style="font-size:8.2pt;color:#6c3483;margin-top:0.5mm">'
                     f'{_T["preg_extra"]}</div>')
    else:
        H.append(f'<div class="sec-ttl">{_T["recommended"]}</div>')
        if is_preg and preg_warn_items:
            H.append(f'<div class="alert al-info" style="font-size:8.4pt">{_T["preg_only"]}</div>')
        else:
            H.append('<div class="alert al-info" style="font-size:8.4pt">'
                     'No clear first-line options — see Caution / Pregnancy sections below.</div>')


def section_avoid(
    *, H,
    _T,
    _is_carbapenemase,
    _is_esbl_like,
    _is_mrsa,
    banned,
    is_preg,
    sir_map,
) -> None:
    """Avoid / contraindicated: every banned agent with its reason tag."""
    # ── AVOID -- each drug with its specific reason ────────────────────────
    if banned:
        def _ban_reason(bd):
            return avoid_reason_tag(bd, sir_map, is_mrsa=_is_mrsa,
                                    is_carbapenemase=_is_carbapenemase, is_esbl_like=_is_esbl_like)

        H.append(
            '<div class="sec-ttl" style="margin-top:1mm;color:#922b21;border-bottom-color:#922b21">'
            f'{_T["avoid"]}</div>'
        )
        _avoid_rows = []
        for _bd in banned:
            _nm   = _esc(_bd.get("name",""))
            _tag, _clr = _ban_reason(_bd)
            _avoid_rows.append(
                f'<span style="display:inline-block;margin:0.3mm 1mm 0.3mm 0;'
                f'padding:0.2mm 2mm;background:#fff;border:0.4pt solid {_clr};'
                f'border-radius:1.5mm;font-size:8pt;max-width:90mm;overflow-wrap:anywhere;vertical-align:top">'
                f'<b style="color:#1a1a2e">{_nm}</b> '
                f'<span style="color:{_clr};font-size:8.2pt">{_tag}</span></span>'
            )
        H.append(
            f'<div class="alert al-danger" style="font-size:8.5pt;line-height:1.6">'
            f'{"".join(_avoid_rows)}</div>'
        )
        # Pregnancy-banned — separate line for clarity
        _preg_banned = [_bd for _bd in banned if _bd.get("category") == "pregnancy"]
        if _preg_banned and is_preg:
            _pb_names = ", ".join(_esc(_bd["name"]) for _bd in _preg_banned)
            H.append(
                '<div class="alert al-danger" style="font-size:8.5pt;margin-top:1mm">'
                f'⊘ <b>Pregnancy Contraindicated:</b> {_pb_names}</div>'
            )


def section_warned(*, H, _EN, _T, _rnote, cl_cr, is_renal, warned) -> None:
    """Dose adjustment / use with caution: one chip per warned agent."""
    # ── DOSE ADJUSTMENT / USE WITH CAUTION -- compact chip grid ──────────
    if warned:
        H.append('<div class="sec-ttl" style="margin-top:0.6mm;color:#b7770d;border-bottom-color:#b7770d">'
                 f'{_T["dose_adj"]}</div>')
        # Shared notes (renal / intermediate) stated ONCE here instead of
        # repeating under every single drug below.
        _sub_notes = []
        if is_renal:
            _sub_notes.append(f'Patient CrCl = {crcl_label(cl_cr, is_renal)}')
        if any(_wd.get("warning_reason") == "intermediate_culture" for _wd in warned):
            _sub_notes.append('⚠ Intermediate (I) / SDD in culture (CLSI M100) -- use only if no '
                              'susceptible option fits')
        if _sub_notes:
            H.append('<div style="font-size:8.2pt;color:#7d6608;margin-bottom:1mm">'
                     + ' &nbsp;·&nbsp; '.join(_sub_notes) + '</div>')

        H.append('<div class="dose-grid" style="display:flex;flex-wrap:wrap;gap:1mm;align-items:stretch">')
        for _wd in warned:
            _wname = _esc(_wd.get("name",""))
            _waw   = _esc(_wd.get("aware",""))
            _wreason = _wd.get("warning_reason","")
            _waw_style = {
                "Access":  "background:#1e8449;color:#fff",
                "Watch":   "background:#b7770d;color:#fff",
                "Reserve": "background:#922b21;color:#fff",
            }.get(_wd.get("aware",""), "background:#888;color:#fff")

            # Reason-specific detail -- "intermediate_culture" is skipped here
            # since it's already covered once by the shared note above.
            _detail = ""
            if _wreason == "renal_adjustment":
                _rl = _wd.get("renal_limit","-")
                _rn = _esc(_rnote(_wd))
                _detail = f'Renal dose adjustment required | Threshold: CrCl \u2264 {_rl} ml/min' + (f' -- {_rn}' if _rn else '')
            elif _wreason in ("esbl_bli_uti_only", "possible_carbapenemase"):
                _esbl_txt = (_wd.get("esbl_note_en") if _EN and _wd.get("esbl_note_en")
                             else _wd.get("esbl_note","ESBL organism -- BLI combo for uncomplicated UTI only"))
                _detail = _esc(_esbl_txt)
            elif _wreason == "intermediate_culture":
                # Never leave the card body empty -- a blank card next to cards
                # carrying a renal caveat reads as "nothing to adjust here".
                # v6.9: the CLSI meaning for this class / site, or the SDD regimen.
                _detail = _esc(_wd.get("intermediate_note_en" if _EN else "intermediate_note")
                               or 'Intermediate (I) on AST \u2014 use only if no better option '
                                  '(CLSI M100).')
                _rn_i = _esc(_rnote(_wd))
                if _rn_i:
                    _detail += f' Renal: {_rn_i}'
            else:
                # FIX 2026-08-03. This branch used to fall through to _rnote(),
                # i.e. the RENAL note, for every warning reason it did not name
                # explicitly — hepatic, safety-gate, neonatal, possible-MRSA.
                # It is the identical defect that was found and fixed in the
                # on-screen renderer the same day, and it survived here because
                # the two renderers each had their own if/else instead of one
                # resolver. A Child-Pugh C caution printed renal dosing; a CSF
                # gate refusal printed "no renal adjustment required" — a
                # reassuring sentence under a refusal.
                #
                # warned_note_for() is now the SINGLE resolver for both, injected
                # through bind(). If a reason has no branch there it returns ""
                # rather than substituting an unrelated note, and the card below
                # says so explicitly instead of printing something false.
                _detail = _esc(warned_note_for(_wd, "en" if _EN else "ar"))
                if not _detail:
                    _detail = _esc(_wd.get("note", "")) or (
                        "Caution recorded with no explanation attached — "
                        "review manually." if _EN else
                        "تحذير بلا تفسير مسجَّل — راجِع النتيجة يدوياً.")

            # v6.9: a second caution attached after the primary one (e.g. the
            # paediatric quinolone note on a renal-warned drug) is printed too.
            _xn = str(_wd.get("clinical_note_en" if _EN else "clinical_note") or "").strip()
            if _detail and _xn and _esc(_xn) not in _detail:
                _detail += " | " + _esc(_xn)
            H.append(
                # flex:1 1 42mm -> chips grow to fill each row evenly (fixes poor
                # distribution when few drugs); min-width forces a clean wrap; max-width
                # keeps a lone chip from spanning the whole page; overflow:hidden +
                # word wrapping on the name stop long drug names spilling past the
                # right margin.
                '<div style="flex:1 1 42mm;min-width:40mm;max-width:92mm;padding:0.5mm 2mm;'
                'border-radius:1.5mm;background:#fef9e7;border:0.5pt solid #b7770d;'
                'overflow:hidden;page-break-inside:avoid">'
                '<div style="display:flex;justify-content:space-between;align-items:center;gap:1.5mm;min-width:0">'
                f'<b style="font-size:9pt;color:#6b5806;min-width:0;overflow-wrap:anywhere;word-break:break-word">{_wname}</b>'
                '<span style="padding:0.2mm 1.8mm;border-radius:1.5mm;font-size:7pt;flex:0 0 auto;'
                f'font-weight:bold;white-space:nowrap;{_waw_style}">{_waw}</span>'
                '</div>'
                + (f'<div style="font-size:8pt;color:#4a4a4a;margin-top:0.4mm;line-height:1.35;overflow-wrap:anywhere">{_detail}</div>'
                   if _detail else '')
                + '</div>'
            )
        H.append('</div>')


def section_interactions(*, H, _EN, _T, interactions) -> None:
    """Drug interactions and the engine's side alerts."""
    # ── Interactions (compact) ─────────────────────────────────────────
    # SILENT-TRUNCATION FIX: this used to print `interactions[:4]`, so on a
    # hepatic patient with several flagged agents the 5th warning onwards simply
    # never appeared in the document the physician actually reads -- and nothing
    # told anyone it had been dropped. All items are now printed; if the list is
    # long the overflow is condensed onto one line rather than discarded.
    if interactions:
        # v6.7: English report -> the English form of each alert (pair + effect).
        _ia_all = [alert_en(_ia) for _ia in interactions] if _EN else list(interactions)
        _ia_head, _ia_tail = _ia_all[:6], _ia_all[6:]
        _rows = [f'<span style="font-size:9pt">{_esc(ia)}</span>' for ia in _ia_head]
        if _ia_tail:
            _rows.append('<span style="font-size:8pt">+ '
                         + _esc(" · ".join(_ia_tail)) + '</span>')
        H.append(f'<div class="sec-ttl" style="margin-top:0.6mm">{_T["interactions"]}</div>'
                 '<div class="alert al-warn">' + '<br>'.join(_rows) + '</div>')


def section_columns(
    *, H,
    _EN,
    _T,
    _clip,
    _join_more,
    _xlate_patho,
    allowed,
    duration_data,
    esbl_result,
    lang,
    mdr_result,
    patho_assessment,
    phenotypes,
    sir_map,
    specimen,
) -> None:
    """Two columns: treatment duration (left), pathogenicity or resistance profile (right)."""
    # 2-column equal — Treatment Duration LEFT, Pathogenicity RIGHT
    H.append('<div class="grid2" style="margin-top:0.6mm">')

    # ── Treatment Duration (now left column) ──────────────────────────────
    H.append('<div class="g2l">')
    if duration_data:
        d = duration_data
        H.append('<div class="sec-ttl">Treatment Duration</div>')
        std = d.get("standard_days", d.get("standard","?"))
        H.append('<table class="compact-tbl">'
                 f'<tr><td class="lbl">Protocol</td><td>{_esc(d.get("label",""))}</td></tr>'
                 f'<tr><td class="lbl">Standard</td><td><b style="font-size:12pt">{std} days</b></td></tr>'
                 f'<tr><td class="lbl">Range</td><td>{d.get("min_days","?")}–{d.get("max_days","?")} days</td></tr>'
                 f'<tr><td class="lbl">IV/PO Split</td><td class="ltr">IV:{d.get("iv_days",0)}d · PO:{d.get("po_days",0)}d</td></tr>'
                 '</table>')
        if d.get("notes"):
            _note = annotate_regimen_note(d["notes"], sir_map, lang=lang)
            H.append(f'<div class="alert al-info" style="font-size:8pt;margin-top:0.5mm">▣ {_esc(_clip(_note, 400))}</div>')
        if d.get("follow_up_culture"):
            H.append('<div class="alert al-warn" style="font-size:8.5pt">↻ Follow-up culture recommended after treatment</div>')
        H.append(f'<div style="font-size:8.4pt;color:#7b8794;margin-top:1.2mm">§ {_esc(d.get("ref",""))}</div>')
    else:
        H.append('<div class="sec-ttl">Treatment Duration</div>')
        H.append('<div class="alert al-info" style="font-size:9pt">Select severity level to see treatment duration</div>')
    H.append('</div>')

    # ── Pathogenicity (now right column, expanded) ────────────────────────
    H.append('<div class="g2r">')
    if patho_assessment:
        sc     = patho_assessment.get("score",0)
        verd   = _esc(patho_assessment.get("verdict",""))
        # Engine v3 supplies English forms; the phrase dictionary is only the
        # fallback for results produced by an older engine.
        if _EN and patho_assessment.get("interpretation_en"):
            interp = _esc(patho_assessment.get("interpretation_en", ""))
            recs   = [_esc(r) for r in patho_assessment.get("recommendations_en", [])]
        else:
            interp = _esc(_xlate_patho(patho_assessment.get("interpretation","")))
            recs   = [_esc(_xlate_patho(r)) for r in patho_assessment.get("recommendations",[])]
        flags  = patho_assessment.get("special_flags",[])
        fpos   = patho_assessment.get("factors_pos",[])
        fneg   = patho_assessment.get("factors_neg",[])
        clr2   = _score_color(sc)

        H.append('<div class="sec-ttl">Pathogenicity Assessment</div>')
        # Score bar
        H.append(f'<div class="score-bar"><div class="score-fill" '
                 f'style="width:{sc}%;background:{clr2}"></div></div>')
        H.append(f'<div style="font-size:10pt;margin:0.5mm 0;font-weight:bold;color:{clr2}">{sc}% — {verd}</div>')
        # Interpretation
        if interp:
            H.append(f'<div style="font-size:9pt;color:#444;margin-bottom:0.5mm">{_clip(interp, 240)}</div>')
        # Flags
        flag_msgs = {
            "ABU_NO_TREAT":  ("al-warn",   "ABU -- Do NOT Treat (IDSA 2019)"),
            "ABU_TREAT":     ("al-danger", "ABU -- TREAT (High-risk)"),
            "MW_REJECT":     ("al-danger", "Specimen REJECTED -- Repeat"),
            "MW_ADEQUATE":   ("al-info",   "Murray-Washington: Adequate"),
            "SIRS_HIGH":     ("al-danger", "SIRS ≥3 -- Sepsis Probable"),
            "PEDIATRIC_UTI": ("al-info",   "Pediatric threshold applied"),
            # Added 2026-08-01: an unread colony count used to contribute a
            # silent zero. It now contributes nothing AND says so, because a
            # verdict built on a field nobody filled in should not look the
            # same as one built on a real reading.
            "CFU_NOT_REPORTED": ("al-warn",
                                 "Colony count not reported / unreadable -- "
                                 "excluded from the score"),
        }
        for fl, (cls, msg) in flag_msgs.items():
            if fl in flags:
                H.append(f'<div class="alert {cls}" style="font-size:8.5pt;margin:0.3mm 0">{msg}</div>')
        # Supporting factors (compact)
        if fpos:
            H.append(f'<div style="font-size:8.5pt;color:#1e8449;margin-top:1mm"><b>{_T["supporting"]}</b></div>')
            for f in fpos[:3]:
                H.append(f'<div style="font-size:8.5pt;color:#1e8449">{_esc(_clip(_xlate_patho(f), 120))}</div>')
        # Against factors
        if fneg:
            H.append(f'<div style="font-size:8.5pt;color:#b7770d;margin-top:0.5mm"><b>{_T["against"]}</b></div>')
            for f in fneg[:3]:
                H.append(f'<div style="font-size:8.5pt;color:#b7770d">{_esc(_clip(f, 120))}</div>')
        # Recommendations
        if recs:
            H.append(f'<div style="font-size:8.5pt;font-weight:bold;margin-top:0.5mm">{_T["recs"]}</div>')
            for r in recs[:3]:
                H.append(f'<div style="font-size:8.5pt">• {_clip(r, 150)}</div>')
    else:
        # Non-urine: show ESBL / MDR / resistance summary instead of pathogenicity
        _is_urine_pdf = "urine" in (specimen or "").lower()
        if _is_urine_pdf:
            H.append('<div class="sec-ttl">Pathogenicity Assessment</div>')
            H.append('<div class="alert al-info" style="font-size:9pt">Run Pathogenicity Assessment in the app to see score</div>')
        else:
            H.append('<div class="sec-ttl">Organism Resistance Profile</div>')
            # ESBL / Mechanism
            if esbl_result and esbl_result.get("probability") not in ("low", None):
                _ep3 = esbl_result.get("probability")
                _em3 = _esc(esbl_result.get("mechanism", ""))
                _ec3 = esbl_result.get("confidence", 0)
                # v6.7: the mechanism engine writes detail_en beside the Arabic detail.
                _ed3 = _esc((esbl_result.get("detail_en") if _EN else None)
                            or esbl_result.get("detail",""))
                if _ep3 == "carbapenemase":
                    H.append(f'<div class="alert al-danger" style="font-size:8.5pt"><b>▲ {_em3}</b> ({_ec3}%)</div>')
                    H.append(f'<div style="font-size:8pt;color:#922b21">{_clip(_ed3, 200)}</div>')
                elif _ep3 in ("high","ampc"):
                    _l3 = "AmpC β-Lactamase" if _ep3 == "ampc" else "ESBL Producer"
                    H.append(f'<div class="alert al-danger" style="font-size:8.5pt"><b>⚠ {_l3}</b> ({_ec3}%) — {_em3}</div>')
                    H.append(f'<div style="font-size:8pt;color:#555">{_clip(_ed3, 200)}</div>')
                elif _ep3 == "moderate":
                    H.append(f'<div class="alert al-warn" style="font-size:8.5pt"><b>◆ ESBL Suspected</b> ({_ec3}%)</div>')
                    H.append(f'<div style="font-size:8pt;color:#555">{_clip(_ed3, 200)}</div>')
            # MDR level
            if mdr_result and mdr_result.get("level"):
                # v7.0: physician-facing -- a provisional XDR/PDR prints as MDR,
                # and each category shows the agents in it that are still S.
                _ml3 = physician_mdr_level(mdr_result)
                _mi3 = MDR_INFO.get(_ml3, {})
                _clr3 = "#922b21" if _ml3 in ("XDR","PDR") else "#b7770d"
                H.append(f'<div style="font-size:9pt;font-weight:bold;color:{_clr3};margin-top:1mm">'
                         f'{_mi3.get("icon","")} {_esc(physician_mdr_label(mdr_result))}</div>')
                H.append(f'<div style="font-size:8pt;color:#555">'
                         f'Non-susceptible {mdr_result["resistant_count"]}/{mdr_result["total_tested"]} categories: '
                         f'{_esc(_join_more(physician_mdr_categories(mdr_result, sir_map, {d.get("name") for d in allowed or []}), 6))}</div>')
            # Phenotypes
            if phenotypes:
                for _ph3 in phenotypes[:3]:
                    _phn3 = _esc(_ph3.get("phenotype",""))
                    H.append(f'<div style="font-size:8.5pt;color:#6e2fa0;margin-top:0.5mm">◆ {_phn3}</div>')
            # No resistance info → show full Susceptibility Summary
            if (not esbl_result or esbl_result.get("probability") in ("low", None)) \
               and not (mdr_result and mdr_result.get("level")) \
               and not phenotypes:
                H.append('<div class="sec-ttl">Susceptibility Summary</div>')
                # ── AST stats ──────────────────────────────────────────────────
                _s_n = sum(1 for v in sir_map.values() if v == "S")
                _i_n = sum(1 for v in sir_map.values() if v == "I")
                _r_n = sum(1 for v in sir_map.values() if v == "R")
                _tot = len(sir_map)
                _gram_txt = ("Gram-positive organism"
                             if (mdr_result or {}).get("gram") == "positive"
                             else "Gram-negative organism"
                             if (mdr_result or {}).get("gram") == "negative"
                             else "")
                _access_n = sum(1 for d in allowed if d.get("aware") == "Access")
                _watch_n  = sum(1 for d in allowed if d.get("aware") == "Watch")
                _res_n    = sum(1 for d in allowed if d.get("aware") == "Reserve")
                _aware_str = (
                    (f"{_access_n} Access" if _access_n else "")
                    + (" · " if _access_n and (_watch_n or _res_n) else "")
                    + (f"{_watch_n} Watch" if _watch_n else "")
                    + (" · " if _watch_n and _res_n else "")
                    + (f"{_res_n} Reserve" if _res_n else "")
                )
                # Score bar colour: green if >60% sensitive
                _pct_s = int(_s_n / _tot * 100) if _tot else 0
                _bar_clr = "#1e8449" if _pct_s >= 60 else "#b7770d" if _pct_s >= 40 else "#922b21"
                H.append(
                    f'<div class="score-bar" style="margin:1mm 0">'
                    f'<div class="score-fill" style="width:{_pct_s}%;background:{_bar_clr}"></div></div>'
                )
                H.append(
                    '<table style="width:100%;border-collapse:collapse;font-size:9pt;margin-top:0.5mm">'
                    f'<tr><td style="padding:0.5mm 1mm;color:#1e8449">✓ Sensitive</td>'
                    f'<td style="padding:0.5mm 1mm;font-weight:bold;color:#1e8449">{_s_n} agents</td>'
                    f'<td style="padding:0.5mm 1mm;font-size:8pt;color:#888">{_pct_s}%</td></tr>'
                    + (f'<tr><td style="padding:0.5mm 1mm;color:#b7770d">● Intermediate</td>'
                       f'<td style="padding:0.5mm 1mm;font-weight:bold;color:#b7770d">{_i_n} agent{"s" if _i_n!=1 else ""}</td>'
                       f'<td></td></tr>' if _i_n else "")
                    + f'<tr><td style="padding:0.5mm 1mm;color:#922b21">✗ Resistant</td>'
                      f'<td style="padding:0.5mm 1mm;font-weight:bold;color:#922b21">{_r_n} agent{"s" if _r_n!=1 else ""}</td>'
                      f'<td></td></tr>'
                    '</table>'
                )
                H.append('<hr class="dv" style="margin:0.8mm 0">')
                if _gram_txt:
                    H.append(f'<div style="font-size:9pt;color:#1a1a2e;margin:0.3mm 0">'
                             f'● {_gram_txt}</div>')
                H.append(f'<div style="font-size:9pt;color:#0d3b66;margin:0.3mm 0">'
                         f'Pattern: <b>Non-MDR / Susceptible</b></div>')
                if _aware_str:
                    H.append(f'<div style="font-size:9pt;color:#555;margin:0.3mm 0">'
                             f'AWaRe: {_aware_str}</div>')
                H.append('<hr class="dv" style="margin:0.8mm 0">')
                H.append(
                    '<div class="alert al-info" style="font-size:8.5pt">'
                    '▣ No ESBL / AmpC / Carbapenemase markers detected.<br>'
                    '<span style="font-size:8pt">Standard culture-directed therapy applicable. '
                    'Follow recommended regimen above.</span></div>'
                )
    H.append('</div></div>')


def section_pregnancy(*, H, _EN, _T, _xlate_preg_note, is_preg, preg_warn_items) -> None:
    """Pregnancy -- use with caution: one card per agent with its trimester note."""
    # ── PREGNANCY -- USE WITH CAUTION  (dedicated section) ─────────────────
    if is_preg and preg_warn_items:
        H.append('<hr class="dv">')
        H.append(
            '<div class="sec-ttl" style="color:#7d3c98;border-bottom-color:#7d3c98">'
            f'{_T["pregnancy"]} &nbsp;'
            '<span style="font-size:8pt;font-weight:normal;color:#888">'
            f'{_T["preg_sub"]}</span></div>'
        )
        for _pw in preg_warn_items:
            _pname = _esc(_pw.get("name", ""))
            _paw   = _esc(_pw.get("aware", ""))
            _pnote = (_pw.get("preg_note") or "").strip()
            # Use English note if lang=en
            if _EN and _pw.get("preg_note_en"):
                _pnote = _pw.get("preg_note_en").strip()
            H.append(
                f'<div style="margin:0.3mm 0;padding:0.8mm 2.5mm;border-radius:2mm;'
                f'border:1pt solid #c39bd3;background:#f5eef8;page-break-inside:avoid">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<b style="font-size:9pt;color:#6c3483">{_pname}</b>'
                f'<span style="padding:0.3mm 2.5mm;border-radius:2mm;font-size:8pt;'
                f'font-weight:bold;background:#7d3c98;color:#fff">{_paw}</span>'
                f'</div>'
            )
            if _pnote:
                _preg_dropped = 0
                for _line in _pnote.splitlines():
                    _line = _line.strip()
                    if not _line:
                        continue
                    # 2026-11-11: the phrase dictionary translates these notes
                    # only in part, and a half-translated line ("risk of
                    # التشوهات ...") is worse than none. In the English report a
                    # line that still holds Arabic is dropped and replaced by
                    # one complete English sentence below.
                    if _EN and re.search(r'[\u0600-\u06FF]', _xlate_preg_note(_line)):
                        _preg_dropped += 1
                        continue
                    if _line.startswith("⊘"):
                        _lcolor = "#922b21"; _lbg = "#fdf2f2"
                    elif _line.startswith("✓"):
                        _lcolor = "#1e8449"; _lbg = "#eafaf1"
                    elif _line.startswith("⚠"):
                        _lcolor = "#b7770d"; _lbg = "#fef9e7"
                    elif _line.startswith(">>>"):
                        _lcolor = "#444";   _lbg = "#f0f0f0"
                    else:
                        _lcolor = "#444";   _lbg = "transparent"
                    H.append(
                        f'<div style="font-size:9pt;color:{_lcolor};'
                        f'background:{_lbg};padding:0.3mm 2mm;margin-top:0.5mm;'
                        f'border-radius:1mm">{_esc(_xlate_preg_note(_line))}</div>'
                    )
                if _EN and _preg_dropped:
                    H.append(
                        '<div style="font-size:9pt;color:#444;padding:0.3mm 2mm;margin-top:0.5mm">'
                        'Pregnancy: not a first-line agent. Use only when no safer alternative exists '
                        'and the benefit outweighs the risk; the decision rests with the treating '
                        'physician.</div>'
                    )
            H.append('</div>')


def section_combo_hepatic_footer(
    *, H,
    child_pugh,
    combo_suggestions,
    hepatic_recs,
    is_hepatic,
) -> None:
    """Combination therapy, hepatic dosing and the footer."""
    # Combination + Hepatic (compact)
    if combo_suggestions:
        H.append('<hr class="dv" style="margin:0.5mm 0"><div class="sec-ttl">Combination Therapy — MDR</div>')
        for cs in combo_suggestions[:2]:
            data = cs["data"]
            H.append(f'<div class="alert al-danger" style="font-size:8.5pt">'
                     f'<b>{_esc(data["urgency"])} — {_esc(data["title"])}</b></div>')
            for opt in data["options"][:3]:
                avoid = "AVOID" in opt.get("evidence","") or "AVOID" in opt["combo"].upper()
                H.append(f'<div style="font-size:8.5pt;margin:0.3mm 0;color:{"#922b21" if avoid else "#1a1a2e"}">'
                         f'{"⊘ " if avoid else "• "}<b>{_esc(opt["combo"])}</b>'
                         f' <span style="color:#888">({_esc(opt["evidence"])})</span></div>')

    if is_hepatic and hepatic_recs:
        action_recs = [r for r in hepatic_recs if r.get("requires_action")][:3]
        if action_recs:
            H.append(f'<hr class="dv" style="margin:0.5mm 0"><div class="sec-ttl">Hepatic Dosing — CP-{_esc(child_pugh)}</div>')
            for r in action_recs:
                cls4 = "danger-val" if "Avoid" in r["level"] else "warn-val"
                H.append(f'<div style="font-size:9pt;margin:0.3mm 0">'
                         f'<b class="{cls4}">{_esc(r["name"])}</b>: {_esc(r["recommendation"])}</div>')

    # Footer
    H.append("""<hr class="dv" style="margin-top:1mm">
<div class="grid2">
  <div class="g2l" style="font-size:8pt;color:#666">
    <b>References:</b> CLSI M100 Ed36 | IDSA AMR Guidance 2026 | EUCAST Expected Resistant Phenotypes | WHO AWaRe 2025 | Sanford 2025 | BNF 2025 | Egypt Nat. Guidelines
  </div>
  <div class="g2r" style="font-size:8pt;color:#666">
    <b>Disclaimer:</b> Clinical decision support only. Treatment decisions are the sole responsibility of the treating physician.
  </div>
</div>

</div></body></html>"""
)
