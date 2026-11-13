# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Pathogenicity report (HTML/PDF)."""
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
import re

from cdss.common.optional_deps import (
    WEASYPRINT_AVAILABLE,
    _wp,
)
from cdss.reports.html_utils import (
    _esc,
    pdf_glyph_guard,
)


def generate_patho_report_pdf(
    patho_result: Dict[str, Any],
    organism: str,
    specimen: str,
    inputs: Optional[Dict[str, Any]] = None,
    patient_ref: str = "",
    lang: str = "ar",
    return_html: bool = False,
):
    """Stand-alone PDF of the Pathogenicity Assessment (added 2026-11-11).

    Everything the panel shows -- score, verdict, threshold, supporting and
    opposing factors, interpretive notes, recommendations, references -- on
    one sheet, so the Arabic recommendations can be printed and filed.
    lang="ar" prints the Arabic interpretation; lang="en" prints the English
    forms and carries no Arabic. `return_html` allows inspection without
    WeasyPrint.
    """
    if not patho_result:
        return None
    if not return_html and (not WEASYPRINT_AVAILABLE or _wp is None):
        return None
    en = not str(lang or "ar").lower().startswith("ar")
    pr = patho_result
    sc = int(pr.get("score", 0))
    col = {"error": "#922b21", "warning": "#b7770d"}.get(pr.get("color"), "#1e8449")
    interp = pr.get("interpretation_en") if en else pr.get("interpretation")
    recs = pr.get("recommendations_en") if en else pr.get("recommendations")
    notes = pr.get("notes_en") if en else pr.get("notes")
    tcls = "ltr" if en else "ar"
    _conf = {"high": ("High", "عالية"), "moderate": ("Moderate", "متوسطة"),
             "low": ("Low", "منخفضة")}.get(pr.get("confidence"), ("-", "-"))

    def T(e, a):
        return e if en else a

    H: List[str] = []
    H.append("""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page { size:A4; margin:12mm 14mm; }
body { font-family:'Noto Sans','Segoe UI',Tahoma,Arial,'DejaVu Sans',sans-serif; color:#1a1a2e; font-size:10pt; }
.hdr { border-bottom:2px solid #0b6e6e; padding-bottom:3mm; margin-bottom:4mm; }
.hdr-title { font-size:16pt; font-weight:bold; color:#0b6e6e; }
.hdr-sub { font-size:9pt; color:#888; margin-top:1mm; }
.meta { display:flex; justify-content:space-between; font-size:9pt; margin-bottom:2mm;
        background:#f2f8f8; padding:2.5mm 3mm; border-radius:2mm; }
.sec { font-size:11pt; font-weight:bold; color:#0b6e6e; border-bottom:1px solid #ddd;
       padding-bottom:1mm; margin:4mm 0 2mm 0; }
.bar { height:4mm; background:#e6e6e6; border-radius:2mm; overflow:hidden; }
.fill { height:4mm; }
.verdict { font-size:13pt; font-weight:bold; margin:2mm 0; }
.ar { direction:rtl; text-align:right; unicode-bidi:isolate; line-height:1.6;
      font-family:'Amiri','Noto Naskh Arabic','Segoe UI',Tahoma,Arial,sans-serif; }
.ltr { direction:ltr; text-align:left; line-height:1.5; }
.row { font-size:9.3pt; margin:1.2mm 0; }
.pos { color:#1e8449; } .neg { color:#b7770d; }
.box { background:#f7f7f9; border-left:3px solid #0b6e6e; padding:2mm 3mm; border-radius:1.5mm; }
.in-tbl { width:100%; border-collapse:collapse; font-size:8.8pt; }
.in-tbl td { padding:1mm 2mm; border-bottom:1px solid #eee; vertical-align:top; }
.in-tbl td.k { width:34%; color:#555; }
.footer { margin-top:6mm; padding-top:2mm; border-top:1px solid #ddd; font-size:7.5pt; color:#888; }
</style></head><body>""")
    H.append('<div class="hdr"><div class="hdr-title">Pathogenicity Assessment Report</div>'
             '<div class="hdr-sub">Infection vs colonisation vs contamination — '
             f'engine v{_esc(str(pr.get("engine_version", "")))}</div></div>')
    H.append('<div class="meta">'
             f'<div><b>Organism:</b>&nbsp;{_esc(organism or "—")}</div>'
             f'<div><b>Specimen:</b>&nbsp;{_esc(specimen or "—")}</div>'
             f'<div><b>Generated:</b>&nbsp;{_esc(datetime.now().strftime("%Y-%m-%d  %H:%M"))}</div></div>')
    if patient_ref:
        H.append(f'<div class="meta"><div><b>Patient Ref:</b>&nbsp;%%PATIENT%%</div></div>')

    H.append(f'<div class="sec">{T("Result", "النتيجة")}</div>')
    H.append(f'<div class="bar"><div class="fill" style="width:{sc}%;background:{col}"></div></div>')
    H.append(f'<div class="verdict" style="color:{col}">{sc}% — {_esc(str(pr.get("verdict", "")))}</div>')
    H.append(f'<div class="row">{T("Assessment confidence", "ثقة التقييم")}: '
             f'<b>{_conf[0] if en else _conf[1]}</b></div>')
    if pr.get("threshold"):
        H.append(f'<div class="row ltr"><b>Threshold applied:</b> {_esc(pr["threshold"])}</div>')
    if pr.get("missing_inputs"):
        H.append(f'<div class="row ltr neg"><b>Not entered (not counted against infection):</b> '
                 f'{_esc(", ".join(pr["missing_inputs"]))}</div>')
    if interp:
        H.append(f'<div class="box {tcls}">{_esc(interp)}</div>')

    if inputs:
        _rows = [(k, v) for k, v in inputs.items() if v not in (None, "", [], "مش محدد", "مش متعملة")]
        if _rows:
            H.append(f'<div class="sec">{T("Data entered", "البيانات المُدخلة")}</div>')
            H.append('<table class="in-tbl">')
            for k, v in _rows:
                v = ", ".join(str(x) for x in v) if isinstance(v, (list, tuple)) else str(v)
                H.append(f'<tr><td class="k">{_esc(k)}</td><td>{_esc(v)}</td></tr>')
            H.append('</table>')

    if pr.get("factors_pos"):
        H.append(f'<div class="sec">{T("Supporting infection", "عوامل تدعم العدوى")}</div>')
        for f in pr["factors_pos"]:
            H.append(f'<div class="row pos" style="unicode-bidi:plaintext">{_esc(f)}</div>')
    if pr.get("factors_neg"):
        H.append(f'<div class="sec">{T("Against infection", "عوامل ضد العدوى")}</div>')
        for f in pr["factors_neg"]:
            H.append(f'<div class="row neg" style="unicode-bidi:plaintext">{_esc(f)}</div>')
    if notes:
        H.append(f'<div class="sec">{T("Interpretive notes", "ملاحظات تفسيرية")}</div>')
        for n_ in notes:
            H.append(f'<div class="row {tcls}">{_esc(n_)}</div>')
    if recs:
        H.append(f'<div class="sec">{T("Recommendations", "التوصيات")}</div>')
        for r_ in recs:
            H.append(f'<div class="row {tcls}">• {_esc(r_)}</div>')
    if pr.get("references"):
        H.append('<div class="sec">References</div>')
        H.append(f'<div class="row ltr" style="font-size:8.5pt;color:#555">'
                 f'{_esc(" · ".join(pr["references"]))}</div>')
    H.append('<div class="footer">Generated by Orange Lab Pathogenicity Engine. Decision support only: '
             'the significance of a culture is a clinical judgement that remains with the treating '
             'physician and the microbiologist.</div></body></html>')
    html = "".join(H)
    if en:
        # UI option labels that carry Arabic words: say them in English first,
        # so the strip below cannot turn "Organisms بدون WBCs" into "Organisms WBCs".
        for _a, _e in (("بدون", "without"), ("مش متعملة", "Not done"), ("مش محدد", "Not specified"),
                       ("طبيعية", "Normal"), ("تاريخ UTIs متكررة", "Recurrent UTIs"),
                       ("(لاهوائيات)", "")):
            html = html.replace(_a, _e)
        # the factor lines are English already; this is the guarantee, not the mechanism
        html = re.sub(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+", "", html)
        html = re.sub(r"\(\s*\)", "", html)
    html = html.replace("%%PATIENT%%", _esc(patient_ref or ""))
    if return_html:
        return html
    try:
        return _wp.HTML(string=pdf_glyph_guard(html)).write_pdf()
    except Exception:
        return None
