# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""AST QA report (HTML/PDF)."""
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.common.optional_deps import (
    WEASYPRINT_AVAILABLE,
    _wp,
)
from cdss.health import (
    PANEL_COMPLETENESS_AVAILABLE,
    _check_panel_completeness_ext,
)
from cdss.reports.html_utils import (
    _esc,
    _md_inline,
    pdf_glyph_guard,
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
) -> Optional[bytes]:
    """
    تقرير AST-QA PDF منفصل تماماً عن تقرير الطبيب.
    للأرشفة الداخلية ومراجعة الجودة من قِبل الميكروبيولوجي فقط.
    لا يُعرض ولا يُرسل للطبيب المعالج.
    """
    if not WEASYPRINT_AVAILABLE or _wp is None:
        return None

    _now = datetime.now().strftime("%Y-%m-%d  %H:%M")

    H: List[str] = []
    H.append("""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page { size:A4; margin:12mm 14mm; }
body { font-family:'Segoe UI',Tahoma,Arial,sans-serif; color:#1a1a2e; font-size:10pt; }
.hdr { border-bottom:2px solid #6e2fa0; padding-bottom:3mm; margin-bottom:4mm; }
.hdr-title { font-size:16pt; font-weight:bold; color:#6e2fa0; }
.hdr-sub   { font-size:9pt; color:#888; margin-top:1mm; }
.meta-row  { display:flex; justify-content:space-between; font-size:9pt; margin-bottom:3mm;
             background:#f7f5fb; padding:2.5mm 3mm; border-radius:2mm; }
.sec-ttl   { font-size:11pt; font-weight:bold; color:#6e2fa0;
             border-bottom:1px solid #ddd; padding-bottom:1mm; margin:4mm 0 2mm 0; }
.conf-box  { padding:3mm; border-radius:2mm; margin-bottom:4mm; }
.issue     { padding:2mm 3mm; margin:1.5mm 0; border-radius:1.5mm; font-size:9pt; line-height:1.5; }
.err       { background:#fdf2f2; border-left:3px solid #922b21; }
.warn      { background:#fef9e7; border-left:3px solid #b7770d; }
.ast-tbl   { width:100%; border-collapse:collapse; font-size:8.5pt; margin-top:2mm; }
.ast-tbl th{ background:#6e2fa0; color:#fff; padding:1.5mm 2mm; text-align:left; }
.ast-tbl td{ padding:1.2mm 2mm; border-bottom:1px solid #eee; }
.sir-S     { color:#1e8449; font-weight:bold; }
.sir-I     { color:#b7770d; font-weight:bold; }
.sir-R     { color:#922b21; font-weight:bold; }
.footer    { margin-top:6mm; padding-top:2mm; border-top:1px solid #ddd;
             font-size:7.5pt; color:#888; }
.org-box   { background:#f7f5fb; border-left:3px solid #6e2fa0; padding:2mm 3mm;
             border-radius:1.5mm; font-size:8.8pt; line-height:1.45; }
.org-box .ar { direction:rtl; text-align:right; unicode-bidi:isolate; margin-bottom:1mm;
               font-family:'Amiri','Noto Naskh Arabic','Segoe UI',Tahoma,Arial,sans-serif; }
.org-box .ln { direction:ltr; margin-top:0.6mm; }
.sir-line  { font-size:8.8pt; line-height:1.5; margin:0.8mm 0; }
.confidential { background:#fdf2f2; color:#922b21; font-weight:bold;
                text-align:center; padding:1.5mm; border-radius:1.5mm;
                font-size:8.5pt; margin-bottom:3mm; }
</style></head><body>""")

    H.append(
        '<div class="confidential">'
        '🔒 INTERNAL LABORATORY USE ONLY &nbsp;—&nbsp; '
        'NOT FOR PHYSICIAN OR PATIENT DISTRIBUTION'
        '</div>'
    )

    H.append(
        '<div class="hdr">'
        '<div class="hdr-title">🔬 AST Quality Assurance Report</div>'
        '<div class="hdr-sub">Laboratory Consistency &amp; Confidence Audit — Internal QA Archive</div>'
        '</div>'
    )

    H.append(
        '<div class="meta-row">'
        f'<div><b>Organism:</b>&nbsp;{_esc(organism or "—")}</div>'
        f'<div><b>Specimen:</b>&nbsp;{_esc(specimen or "—")}</div>'
        f'<div><b>Generated:</b>&nbsp;{_esc(_now)}</div>'
        '</div>'
    )
    H.append(
        '<div class="meta-row">'
        f'<div><b>Microbiologist:</b>&nbsp;{_esc(microbiologist or "—")}</div>'
        f'<div><b>Patient Ref:</b>&nbsp;{_esc(patient_ref or "—")}</div>'
        f'<div><b>Lab ID:</b>&nbsp;{_esc(lab_id or "—")}</div>'
        '</div>'
    )

    # ── Organism summary (2026-11-11) ──────────────────────────────────────
    # The same guidance card the screen shows under the specimen data, in full,
    # so the archived QA sheet says what the organism IS, not only its name.
    _op_qa = ORGANISM_PROFILE.get(organism) or {}
    if _op_qa:
        H.append('<div class="sec-ttl">📌 Organism Summary</div>')
        H.append('<div class="org-box">')
        if _op_qa.get("note"):
            H.append(f'<div class="ar">{_md_inline(_op_qa["note"])}</div>')
        _ctx_qa = (_op_qa.get("specimen_context") or {}).get(specimen, "")
        if _ctx_qa:
            H.append(f'<div class="ar"><b>{_esc(specimen)}:</b> {_md_inline(_ctx_qa)}</div>')
        for _lbl, _key in (("First-line", "first_line"), ("Second-line", "second_line"),
                           ("Third-line", "third_line"), ("Avoid", "avoid")):
            if _op_qa.get(_key):
                H.append(f'<div class="ln"><b>{_lbl}:</b> {_esc(", ".join(_op_qa[_key]))}</div>')
        if "urine" in str(specimen).lower() and _op_qa.get("urine_note"):
            H.append(f'<div class="ar">{_md_inline(_op_qa["urine_note"])}</div>')
        H.append('</div>')

    # ── Confidence Score ──────────────────────────────────────────────
    H.append('<div class="sec-ttl">📊 Recommendation Confidence Score</div>')
    H.append(
        f'<div class="conf-box" style="background:{confidence["color"]}18;'
        f'border:1.5px solid {confidence["color"]}">'
        f'<div style="font-size:13pt;font-weight:bold;color:{confidence["color"]}">'
        f'{confidence["icon"]} {_esc(confidence["level"])} — {confidence["score"]}/100</div>'
        '<ul style="margin:2mm 0 0 4mm;padding:0;font-size:9pt">'
        + "".join(f'<li>{_esc(r)}</li>' for r in confidence["reasons"])
        + '</ul></div>'
    )
    H.append(
        f'<div style="font-size:8pt;color:#888;margin-bottom:3mm">'
        f'Errors: <b>{confidence["n_errors"]}</b> &nbsp;|&nbsp; '
        f'Warnings: <b>{confidence["n_warnings"]}</b> &nbsp;|&nbsp; '
        f'Antibiotics tested: <b>{confidence["n_tested"]}</b>'
        '</div>'
    )

    # ── QC Issues ────────────────────────────────────────────────────
    H.append(f'<div class="sec-ttl">🔍 AST-QA Findings ({len(qc_issues)})</div>')
    if not qc_issues:
        H.append(
            '<div style="font-size:9.5pt;color:#1e8449">'
            '✅ All AST consistency checks passed. No issues detected.'
            '</div>'
        )
    else:
        for issue in qc_issues:
            cls  = "err" if issue["severity"] == "error" else "warn"
            icon = "❌"  if issue["severity"] == "error" else "⚠️"
            H.append(
                f'<div class="issue {cls}">'
                f'<b>{icon} {_esc(issue["severity"].upper())}</b><br>'
                f'{_md_inline(issue["message"])}<br>'
                f'<span style="color:#555">✏️ {_md_inline(issue["fix"])}</span>'
                '</div>'
            )

    # ── AST Panel Completeness ──────────────────────────────────────────
    # Added 2026-08-22: this is THE internal QA PDF (confirmed against a
    # live screenshot -- "تقرير الجودة الداخلي للميكروبيولوجي فقط" is
    # this document's own header text) -- Panel Completeness had been added
    # to generate_report()/generate_pdf_html_report() (the CLINICIAN-facing
    # report) instead, which was the wrong document for an "internal AST
    # report" request. Kept in both now; this is the one that actually
    # matters for "was enough tested" as a QA question, not a treatment one.
    if PANEL_COMPLETENESS_AVAILABLE and _check_panel_completeness_ext and sir_map:
        _pc_pdf = _check_panel_completeness_ext(organism, specimen, sir_map)
        if _pc_pdf.status != "not_evaluated":
            _pc_pdf_missing = _pc_pdf.missing_primary + _pc_pdf.missing_supplemental
            H.append('<div class="sec-ttl">🧫 AST Panel Completeness</div>')
            H.append(
                f'<div style="font-size:9pt;color:#555;margin-bottom:2mm">'
                f'Organism group: <b>{_esc(_pc_pdf.organism_group)}</b> &nbsp;|&nbsp; '
                f'Expected: <b>{_pc_pdf.expected_total}</b> &nbsp;|&nbsp; '
                f'Tested: <b>{_pc_pdf.tested_count}</b> &nbsp;|&nbsp; '
                f'Missing: <b>{len(_pc_pdf_missing)}</b>'
                '</div>'
            )
            if not _pc_pdf_missing:
                H.append(
                    '<div style="font-size:9.5pt;color:#1e8449">'
                    '✅ Panel adequate -- all expected agents for this organism were tested.'
                    '</div>'
                )
            else:
                if _pc_pdf.status == "critical":
                    H.append(
                        '<div class="issue err">'
                        '<b>❌ CRITICAL</b><br>'
                        'Every primary agent tested came back Resistant, and expected '
                        'primary agent(s) were never tested. A therapeutic option may '
                        'exist among the untested agents -- this panel cannot rule that '
                        'out. Do not report &ldquo;no susceptible options&rdquo; from an '
                        'incomplete panel.'
                        '</div>'
                    )
                if _pc_pdf.missing_primary:
                    H.append(
                        f'<div class="issue warn"><b>⚠️ Missing (primary)</b><br>'
                        f'{_esc(", ".join(_pc_pdf.missing_primary))}</div>'
                    )
                if _pc_pdf.missing_supplemental:
                    H.append(
                        f'<div style="font-size:8.5pt;color:#555;margin:1mm 0">'
                        f'🔵 Missing (supplemental): {_esc(", ".join(_pc_pdf.missing_supplemental))}'
                        '</div>'
                    )
            if _pc_pdf.rule_id:
                try:
                    from cdss.guidelines.guideline_registry import citation_line as _pc_pdf_cite_fn
                    _pc_pdf_ref = _pc_pdf_cite_fn(_pc_pdf.rule_id)
                except Exception:
                    _pc_pdf_ref = ""
                if _pc_pdf_ref:
                    H.append(
                        f'<div style="font-size:7.5pt;color:#888">📖 {_esc(_pc_pdf_ref)}</div>'
                    )

    # ── Full AST Panel ────────────────────────────────────────────────
    # Compact since 2026-11-11: one row per drug pushed the sheet onto a
    # second page for any normal panel. Grouped by result it is three lines,
    # and nothing is lost -- every tested agent is still named.
    H.append('<div class="sec-ttl">🧪 Full AST Panel as Entered</div>')
    if sir_map:
        for _res, _lbl in (("S", "Susceptible"), ("I", "Intermediate / SDD"), ("R", "Resistant")):
            _grp = sorted(d for d, r in sir_map.items() if r == _res)
            if _grp:
                H.append(f'<div class="sir-line"><span class="sir-{_res}">{_res} — {_lbl} '
                         f'({len(_grp)}):</span> {_esc(", ".join(_grp))}</div>')
        _oth = sorted(f"{d} ({r})" for d, r in sir_map.items() if r not in ("S", "I", "R"))
        if _oth:
            H.append(f'<div class="sir-line"><b>Other:</b> {_esc(", ".join(_oth))}</div>')
    else:
        H.append('<div style="font-size:9pt;color:#888">No AST data recorded.</div>')

    H.append(
        '<div class="footer">'
        'Generated by Orange Lab AST-QA Engine&nbsp;|&nbsp;'
        'EUCAST Expert Rules v3.1 (2016) / CLSI M100 Ed36<br>'
        'This document is for internal laboratory quality control and audit only. '
        'It must not be shared with referring physicians or included in the patient report.'
        '</div>'
    )
    H.append('</body></html>')

    try:
        return _wp.HTML(string=pdf_glyph_guard("".join(H))).write_pdf()
    except Exception:
        return None
