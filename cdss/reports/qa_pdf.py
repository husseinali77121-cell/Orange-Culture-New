# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""AST QA report (HTML/PDF)."""
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from cdss.common.drug_names import tag_with_ast as _tag_with_ast
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.common.optional_deps import (
    WEASYPRINT_AVAILABLE,
    _wp,
)
from cdss.health import (
    PANEL_COMPLETENESS_AVAILABLE,
    _check_panel_completeness_ext,
)
from cdss.reports.fit_page import mm, pt, render_one_page
from cdss.reports.fonts import with_bundled_fonts  # noqa: F401  (kept for importers)
from cdss.reports.html_utils import (
    _esc,
    _md_inline,
    bidi_isolate,
    pdf_glyph_guard,  # noqa: F401
)


def generate_qa_report_pdf(
    organism: str,
    specimen: str,
    sir_map: Dict[str, str],
    qc_issues: List[Dict[str, Any]],
    confidence: Dict[str, Any],
    microbiologist: str = "",
    lab_id: str = "",
    patient_ref: str = "",
    return_html: bool = False,
    scale: float = 1.0,
    sdd=None,
) -> Optional[bytes]:
    """
    تقرير AST-QA PDF منفصل تماماً عن تقرير الطبيب.
    للأرشفة الداخلية ومراجعة الجودة من قِبل الميكروبيولوجي فقط.
    لا يُعرض ولا يُرسل للطبيب المعالج.

    v7.0: ONE A4 sheet (user request, 2026-11-19) -- compact header, findings
    first, completeness and the panel side by side, organism summary last;
    fit_page.render_one_page lowers the type scale until it fits. The Arabic
    organism notes isolate their English runs (bidi_isolate). `return_html`
    and `scale` exist for inspection and tests.
    """
    if not return_html and (not WEASYPRINT_AVAILABLE or _wp is None):
        return None

    _now = datetime.now().strftime("%Y-%m-%d  %H:%M")
    _issues = list(qc_issues or [])
    _n_err = sum(1 for i in _issues if i.get("severity") == "error")
    _n_warn = len(_issues) - _n_err

    _pc = None
    if PANEL_COMPLETENESS_AVAILABLE and _check_panel_completeness_ext and sir_map:
        try:
            _pc = _check_panel_completeness_ext(organism, specimen, sir_map)
            if _pc.status == "not_evaluated":
                _pc = None
        except Exception:
            _pc = None
    _op_qa = ORGANISM_PROFILE.get(organism) or {}
    _sdd = set(sdd or ())
    try:
        from cdss.resistance.mdr import classify_mdr, mdr_breakdown
        from cdss.resistance.esbl_status import (mdr_heading, mdr_without_unverified,
                                                mdr_xdr_note, unverified_results)
        _mdr = classify_mdr(organism, sir_map or {}) if sir_map else {}
        _mdr_rows = mdr_breakdown(_mdr, sir_map or {}) if (_mdr or {}).get("total_tested") else []
        # v7.9: the same heading as the physician advisory (no bare "XDR" here
        # while the advisory says "MDR"), and the results that cannot be used
        # as printed (cefepime "I" where CLSI has no I) are marked.
        _unv = unverified_results(organism, sir_map or {}, _sdd)
        _mdr_unv = mdr_without_unverified(organism, sir_map or {}, _mdr, _unv) if _mdr else {}
        _mdr_head = mdr_heading(_mdr) if _mdr else ""
        _mdr_xdr = mdr_xdr_note(_mdr, list_categories=True) if _mdr else ""
    except Exception:
        _mdr, _mdr_rows, _unv, _mdr_unv, _mdr_head, _mdr_xdr = {}, [], [], {}, "", ""

    def _ar(text: str) -> str:
        return _md_inline(bidi_isolate(text))

    def build(z: float) -> str:
        H: List[str] = []
        H.append(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size:A4; margin:8mm 10mm; }}
body {{ font-family:'Noto Sans','DejaVu Sans','Segoe UI',Tahoma,Arial,sans-serif; color:#1a1a2e;
        font-size:{pt(8.6, z)}; margin:0; }}
.confidential {{ background:#fdf2f2; color:#922b21; font-weight:bold; text-align:center;
                 padding:{mm(0.8, z)}; border-radius:1mm; font-size:{pt(7.4, z)}; margin-bottom:{mm(1.5, z)}; }}
table.hdr {{ width:100%; border-collapse:collapse; border-bottom:1.6pt solid #6e2fa0; margin-bottom:{mm(1.5, z)}; }}
table.hdr td {{ vertical-align:bottom; padding:0 0 {mm(1, z)} 0; }}
.hdr-title {{ font-size:{pt(13.5, z)}; font-weight:bold; color:#6e2fa0; }}
.hdr-sub {{ font-size:{pt(7.3, z)}; color:#888; }}
table.meta {{ width:100%; border-collapse:collapse; font-size:{pt(7.8, z)}; background:#f7f5fb;
              margin-bottom:{mm(1.5, z)}; }}
table.meta td {{ padding:{mm(0.6, z)} {mm(1.8, z)}; }}
.sec-ttl {{ font-size:{pt(9.3, z)}; font-weight:bold; color:#6e2fa0; border-bottom:0.6pt solid #ddd;
            padding-bottom:{mm(0.4, z)}; margin:{mm(2, z)} 0 {mm(0.8, z)} 0; }}
.conf-box {{ padding:{mm(1, z)} {mm(2, z)}; border-radius:1.2mm; margin-bottom:{mm(0.6, z)}; }}
.issue {{ padding:{mm(0.8, z)} {mm(1.8, z)}; margin:{mm(0.7, z)} 0; border-radius:1mm;
          font-size:{pt(7.9, z)}; line-height:1.35; }}
.issue .fix {{ color:#555; }}
.err {{ background:#fdf2f2; border-left:2.2pt solid #922b21; }}
.warn {{ background:#fef9e7; border-left:2.2pt solid #b7770d; }}
.chip {{ font-weight:bold; font-size:{pt(7, z)}; }}
table.cols {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
table.cols > tbody > tr > td {{ vertical-align:top; padding:0; }}
table.cols > tbody > tr > td.gap {{ width:4mm; }}
.sir-line {{ font-size:{pt(7.9, z)}; line-height:1.4; margin:{mm(0.5, z)} 0; }}
.sir-S {{ color:#1e8449; font-weight:bold; }} .sir-I {{ color:#b7770d; font-weight:bold; }}
.sir-R {{ color:#922b21; font-weight:bold; }}
.small {{ font-size:{pt(7.4, z)}; color:#555; }}
.org-box {{ background:#f7f5fb; border-left:2.2pt solid #6e2fa0; padding:{mm(1, z)} {mm(2, z)};
            border-radius:1.2mm; font-size:{pt(7.8, z)}; line-height:1.4; }}
.org-box .ar {{ direction:rtl; text-align:right; unicode-bidi:isolate; margin-bottom:{mm(0.6, z)};
               font-family:'Amiri','Noto Naskh Arabic','Segoe UI',Tahoma,Arial,sans-serif; }}
.org-box .ln {{ direction:ltr; margin-top:{mm(0.4, z)}; }}
.footer {{ margin-top:{mm(2, z)}; padding-top:{mm(0.8, z)}; border-top:0.6pt solid #ddd;
           font-size:{pt(6.6, z)}; color:#888; }}
</style></head><body>""")
        H.append('<div class="confidential">🔒 INTERNAL LABORATORY USE ONLY &nbsp;—&nbsp; '
                 'NOT FOR PHYSICIAN OR PATIENT DISTRIBUTION</div>')
        H.append('<table class="hdr"><tr><td><div class="hdr-title">🔬 AST Quality Assurance Report</div>'
                 '<div class="hdr-sub">Laboratory Consistency &amp; Confidence Audit — Internal QA Archive'
                 '</div></td></tr></table>')
        H.append(
            '<table class="meta"><tr>'
            f'<td><b>Organism:</b>&nbsp;{_esc(organism or "—")}</td>'
            f'<td><b>Specimen:</b>&nbsp;{_esc(specimen or "—")}</td>'
            f'<td><b>Generated:</b>&nbsp;{_esc(_now)}</td></tr><tr>'
            f'<td><b>Microbiologist:</b>&nbsp;{_esc(microbiologist or "—")}</td>'
            f'<td><b>Patient Ref:</b>&nbsp;{_esc(patient_ref or "—")}</td>'
            f'<td><b>Lab ID:</b>&nbsp;{_esc(lab_id or "—")}</td></tr></table>')

        # ── Confidence (one line) ────────────────────────────────────────────
        _c = confidence or {}
        _col = _c.get("color", "#555")
        H.append(
            f'<div class="conf-box" style="background:{_col}18;border:1.2pt solid {_col}">'
            f'<b style="font-size:{pt(10.5, z)};color:{_col}">{_c.get("icon", "")} '
            f'{_esc(str(_c.get("level", "")))} — {_c.get("score", "")}/100</b>'
            f'<span class="small"> &nbsp;|&nbsp; Errors: <b>{_c.get("n_errors", _n_err)}</b>'
            f' &nbsp;|&nbsp; Warnings: <b>{_c.get("n_warnings", _n_warn)}</b>'
            f' &nbsp;|&nbsp; Antibiotics tested: <b>{_c.get("n_tested", len(sir_map or {}))}</b></span>'
            + (f'<div class="small" dir="rtl" style="text-align:right;unicode-bidi:isolate">'
               f'{_esc(bidi_isolate(" · ".join(_c.get("reasons") or [])))}</div>'
               if _c.get("reasons") else "")
            + '</div>')

        # ── Findings ─────────────────────────────────────────────────────────
        H.append(f'<div class="sec-ttl">🔍 AST-QA Findings ({len(_issues)})</div>')
        if not _issues:
            H.append('<div style="color:#1e8449">✅ All AST consistency checks passed. '
                     'No issues detected.</div>')
        for issue in _issues:
            _err = issue.get("severity") == "error"
            H.append(
                f'<div class="issue {"err" if _err else "warn"}">'
                f'<span class="chip" style="color:{"#922b21" if _err else "#b7770d"}">'
                f'{"❌ ERROR" if _err else "⚠️ WARNING"}</span> '
                f'{_md_inline(issue.get("message", ""))}'
                + (f'<br><span class="fix">✏️ {_md_inline(issue.get("fix", ""))}</span>'
                   if issue.get("fix") else "")
                + '</div>')

        # ── Completeness | panel as entered ──────────────────────────────────
        left: List[str] = []
        if _pc is not None:
            _miss = _pc.missing_primary + _pc.missing_supplemental
            _reflex = getattr(_pc, "reflex_missing", {}) or {}
            left.append('<div class="sec-ttl">🧫 AST Panel Completeness</div>')
            # v7.4 (external case review): "Tested 10" beside "14 antibiotics tested"
            # read as a counting error. The line now reconciles with the panel:
            # expected = covered + missing; entered = covered + additional.
            _extra = list(getattr(_pc, "extra_tested", []) or [])
            _total = getattr(_pc, "total_tested", 0) or len(sir_map or {})
            left.append(f'<div class="small">Group: <b>{_esc(_pc.organism_group)}</b> · Expected '
                        f'<b>{_pc.expected_total}</b> · Covered <b>{_pc.tested_count}</b> · Missing '
                        f'<b>{len(_miss)}</b> · Additional (not on the standard panel) '
                        f'<b>{len(_extra)}</b> · Total entered <b>{_total}</b></div>')
            _alias = [f"{_esc(', '.join(v))} → {_esc(k)}"
                      for k, v in (getattr(_pc, "covered_by", {}) or {}).items()
                      if any(x != k for x in v)]
            if _alias:
                left.append('<div class="small" style="color:#555">Counted as the same agent: '
                            + "; ".join(_alias) + '</div>')
            if _extra:
                left.append(f'<div class="small" style="color:#555">Additional: '
                            f'{_esc(", ".join(_extra))}</div>')
            if not _miss:
                left.append('<div class="sir-line" style="color:#1e8449">✅ Panel adequate — every '
                            'expected agent was tested.</div>')
            if _pc.status == "critical":
                left.append('<div class="issue err"><b>❌ CRITICAL</b> — every primary agent tested '
                            'was R and expected primary agents were never tested; do not report '
                            '&ldquo;no susceptible options&rdquo; from this panel.</div>')
            if _reflex:
                left.append('<div class="issue err"><b>❌ Required by another result:</b> '
                            + _esc(" · ".join(f"{d} ({w})" for d, w in _reflex.items()))
                            + '</div>')
            _prim = [d for d in _pc.missing_primary if d not in _reflex]
            if _prim:
                left.append(f'<div class="sir-line"><b>⚠️ Missing (primary):</b> '
                            f'{_esc(", ".join(_prim))}</div>')
            if _pc.missing_supplemental:
                left.append(f'<div class="sir-line small">🔵 Missing (supplemental): '
                            f'{_esc(", ".join(_pc.missing_supplemental))}</div>')
            if _pc.rule_id:
                try:
                    from cdss.guidelines.guideline_registry import citation_line as _cite
                    _ref = _cite(_pc.rule_id)
                except Exception:
                    _ref = ""
                if _ref:
                    left.append(f'<div class="small" style="color:#888">📖 {_esc(_ref)}</div>')
        right: List[str] = ['<div class="sec-ttl">🧪 Full AST Panel as Entered</div>']
        if sir_map:
            for _res, _lbl in (("S", "Susceptible"), ("I", "Intermediate / SDD"), ("R", "Resistant")):
                _grp = sorted((f"{d} (SDD)" if d in _sdd else d)
                              for d, r in sir_map.items() if r == _res)
                if _grp:
                    right.append(f'<div class="sir-line"><span class="sir-{_res}">{_res} — {_lbl} '
                                 f'({len(_grp)}):</span> {_esc(", ".join(_grp))}</div>')
            _oth = sorted(f"{d} ({r})" for d, r in sir_map.items() if r not in ("S", "I", "R"))
            if _oth:
                right.append(f'<div class="sir-line"><b>Other:</b> {_esc(", ".join(_oth))}</div>')
        else:
            right.append('<div class="small">No AST data recorded.</div>')
        if left:
            H.append('<table class="cols"><tr><td>' + "".join(left) + '</td><td class="gap"></td><td>'
                     + "".join(right) + '</td></tr></table>')
        else:
            H.extend(right)

        # ── MDR calculation (v7.4, external case review) ─────────────────────
        # "MDR 6/9" was printed with three category names and no way to check
        # it. The internal sheet shows the count: each tested category, its
        # agents with their results, and whether it counted as non-susceptible.
        if _mdr_rows:
            H.append(f'<div class="sec-ttl">🧮 MDR classification: {_esc(_mdr_head)}</div>')
            H.append('<div class="small">Magiorakos 2012: a category is non-susceptible when '
                     '&ge; 1 agent in it is I or R; MDR = non-susceptible in &ge; 3 categories. '
                     'Several resistant agents in ONE category count once. XDR / PDR are '
                     'confirmed only when every category of the organism\'s table was tested.</div>')
            if _mdr_xdr:
                H.append(f'<div class="sir-line" style="color:#922b21">⚠️ {_esc(_mdr_xdr)}. '
                         'Test them before reporting XDR; the established level is '
                         f'{_esc((_mdr_head or "").split(" — ")[0])}.</div>')
            if _unv:
                _rest = (_mdr_unv or {}).get("categories_resting_on_unverified") or []
                H.append('<div class="sir-line" style="color:#b7770d">⏳ Pending verification '
                         f'(CLSI has no I here — SDD or R by MIC): {_esc(", ".join(_unv))}. '
                         + (f'Category verdict resting on it alone: {_esc(", ".join(_rest))} — '
                            'recalculate after the MIC.' if _rest else
                            'No category verdict rests on it alone — the level stands either way.')
                         + ((' Level without it: ' + _esc(str((_mdr_unv or {}).get('level_without')
                                                                 or 'not MDR')) + '.')
                            if (_mdr_unv or {}).get("changed") else '')
                         + '</div>')
            for _row in _mdr_rows:
                _ag = ", ".join(f"{_esc(d)} <span class='sir-{r}'>{_esc(r)}</span>"
                                + (" <i>(unverified)</i>" if d in _unv else "")
                                for d, r in _row["agents"])
                H.append(f'<div class="sir-line">{"❌" if _row["non_susceptible"] else "✅"} '
                         f'<b>{_esc(_row["category"])}</b>: {_ag}</div>')

        # ── Organism summary (2026-11-11), last: reference, not a finding ─────
        if _op_qa:
            # v7.4 (external case review): general guidance for the organism, NOT
            # this isolate's options -- every agent carries this isolate's result
            # (or "not tested"), and salt forms are not listed as separate drugs.
            H.append('<div class="sec-ttl">📌 Organism Summary — general guidance, NOT adjusted '
                     'to this isolate (tags = this isolate\'s result)</div>')
            H.append('<div class="org-box">')
            if _op_qa.get("note"):
                H.append(f'<div class="ar">{_ar(_op_qa["note"])}</div>')
            _ctx_qa = (_op_qa.get("specimen_context") or {}).get(specimen, "")
            if _ctx_qa:
                H.append(f'<div class="ar"><b>{_esc(specimen)}:</b> {_ar(_ctx_qa)}</div>')
            for _lbl, _key in (("First-line", "first_line"), ("Second-line", "second_line"),
                               ("Third-line", "third_line"), ("Avoid", "avoid")):
                if _op_qa.get(_key):
                    _names = _tag_with_ast(_op_qa[_key], sir_map or {})
                    H.append(f'<div class="ln"><b>{_lbl}:</b> {_esc(", ".join(_names))}</div>')
            if "urine" in str(specimen).lower() and _op_qa.get("urine_note"):
                H.append(f'<div class="ar">{_ar(_op_qa["urine_note"])}</div>')
            H.append('</div>')

        H.append('<div class="footer">Generated by Orange Lab AST-QA Engine&nbsp;|&nbsp;CLSI M100 Ed36 '
                 '/ EUCAST Expert Rules v3.1 (2016). Internal laboratory quality control and audit '
                 'only — not for referring physicians or the patient report.</div>')
        H.append('</body></html>')
        return "".join(H)

    if return_html:
        return build(scale)
    try:
        return render_one_page(build)
    except Exception:
        return None
