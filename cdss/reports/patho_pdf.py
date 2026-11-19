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
from cdss.reports.fit_page import mm, pt, render_one_page
from cdss.reports.fonts import with_bundled_fonts  # noqa: F401  (kept for importers)
from cdss.reports.html_utils import (
    _esc,
    bidi_isolate,
    pdf_glyph_guard,  # noqa: F401
)


def generate_patho_report_pdf(
    patho_result: Dict[str, Any],
    organism: str,
    specimen: str,
    inputs: Optional[Dict[str, Any]] = None,
    patient_ref: str = "",
    lang: str = "ar",
    return_html: bool = False,
    scale: float = 1.0,
):
    """Stand-alone PDF of the Pathogenicity Assessment (added 2026-11-11).

    v7.0: ONE A4 sheet -- compact two-column layout; the PDF is rendered by
    fit_page.render_one_page, which lowers the type scale until it fits.
    `scale` only applies to return_html (inspection / tests).

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

    _inputs_rows = []
    if inputs:
        for k, v in inputs.items():
            if v in (None, "", [], "مش محدد", "مش متعملة"):
                continue
            v = ", ".join(str(x) for x in v) if isinstance(v, (list, tuple)) else str(v)
            _inputs_rows.append((k, v))

    def _t(x: str) -> str:
        """Escape, with every English run of an Arabic sentence isolated (bidi)."""
        return _esc(bidi_isolate(x) if not en else x)

    def build(z: float) -> str:
        """The whole sheet at type scale z (fit_page shrinks z until it is ONE page)."""
        H: List[str] = []
        H.append(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size:A4; margin:8mm 10mm; }}
body {{ font-family:'Noto Sans','DejaVu Sans','Segoe UI',Tahoma,Arial,sans-serif; color:#1a1a2e;
        font-size:{pt(9, z)}; margin:0; }}
table.hdr {{ width:100%; border-collapse:collapse; border-bottom:1.6pt solid #0b6e6e;
            margin-bottom:{mm(2, z)}; }}
table.hdr td {{ vertical-align:bottom; padding:0 0 {mm(1.2, z)} 0; }}
.hdr-title {{ font-size:{pt(14, z)}; font-weight:bold; color:#0b6e6e; }}
.hdr-sub {{ font-size:{pt(7.5, z)}; color:#888; }}
.meta {{ font-size:{pt(8, z)}; text-align:right; line-height:1.35; }}
.sec {{ font-size:{pt(9.5, z)}; font-weight:bold; color:#0b6e6e; border-bottom:0.6pt solid #ddd;
        padding-bottom:{mm(0.5, z)}; margin:{mm(2.2, z)} 0 {mm(1, z)} 0; }}
.bar {{ height:{mm(3, z)}; background:#e6e6e6; border-radius:1.5mm; overflow:hidden; }}
.fill {{ height:{mm(3, z)}; }}
.verdict {{ font-size:{pt(11.5, z)}; font-weight:bold; margin:{mm(1, z)} 0 {mm(0.5, z)} 0; }}
.ar {{ direction:rtl; text-align:right; unicode-bidi:isolate; line-height:1.5;
       font-family:'Amiri','Noto Naskh Arabic','Segoe UI',Tahoma,Arial,sans-serif; }}
.ltr {{ direction:ltr; text-align:left; line-height:1.4; }}
.row {{ font-size:{pt(8.4, z)}; margin:{mm(0.6, z)} 0; }}
.small {{ font-size:{pt(7.6, z)}; color:#555; }}
.pos {{ color:#1e8449; }} .neg {{ color:#b7770d; }}
.box {{ background:#f7f7f9; border-left:2.4pt solid #0b6e6e; padding:{mm(1.3, z)} {mm(2.2, z)};
        border-radius:1.2mm; font-size:{pt(8.6, z)}; }}
table.cols {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
table.cols > tbody > tr > td {{ vertical-align:top; padding:0; }}
table.cols > tbody > tr > td.gap {{ width:4mm; }}
.in-tbl {{ width:100%; border-collapse:collapse; font-size:{pt(8, z)}; }}
.in-tbl td {{ padding:{mm(0.5, z)} {mm(1.2, z)}; border-bottom:0.5pt solid #eee; vertical-align:top; }}
.in-tbl td.k {{ width:36%; color:#555; }}
.footer {{ margin-top:{mm(2.5, z)}; padding-top:{mm(1, z)}; border-top:0.6pt solid #ddd;
           font-size:{pt(6.8, z)}; color:#888; }}
</style></head><body>""")
        _meta = [f"<b>Organism:</b> {_esc(organism or '—')}", f"<b>Specimen:</b> {_esc(specimen or '—')}",
                 f"<b>Generated:</b> {_esc(datetime.now().strftime('%Y-%m-%d %H:%M'))}"]
        if patient_ref:
            _meta.insert(0, "<b>Patient Ref:</b> %%PATIENT%%")
        H.append('<table class="hdr"><tr><td><div class="hdr-title">Pathogenicity Assessment Report</div>'
                 '<div class="hdr-sub">Infection vs colonisation vs contamination — engine v'
                 f'{_esc(str(pr.get("engine_version", "")))}</div></td>'
                 f'<td class="meta">{"<br>".join(_meta)}</td></tr></table>')

        # ── Result ───────────────────────────────────────────────────────────
        H.append(f'<div class="bar"><div class="fill" style="width:{sc}%;background:{col}"></div></div>')
        H.append(f'<div class="verdict" style="color:{col}">Evidence score {sc}/100 (not a probability) — {_esc(str(pr.get("verdict", "")))}'
                 f'<span class="small" style="font-weight:normal"> &nbsp;·&nbsp; '
                 f'{T("Assessment confidence", "ثقة التقييم")}: <b>{_conf[0] if en else _conf[1]}</b>'
                 '</span></div>')
        if pr.get("threshold"):
            H.append(f'<div class="row ltr"><b>Threshold applied:</b> {_esc(pr["threshold"])}</div>')
        if pr.get("missing_inputs"):
            H.append(f'<div class="row ltr neg"><b>Not entered (not counted against infection):</b> '
                     f'{_esc(", ".join(pr["missing_inputs"]))}</div>')
        if interp:
            H.append(f'<div class="box {tcls}">{_t(interp)}</div>')

        # ── Two columns: what was entered | what it means ─────────────────────
        left: List[str] = []
        if _inputs_rows:
            left.append(f'<div class="sec">{T("Data entered", "البيانات المُدخلة")}</div>')
            left.append('<table class="in-tbl">')
            for k, v in _inputs_rows:
                left.append(f'<tr><td class="k">{_esc(k)}</td><td>{_esc(v)}</td></tr>')
            left.append('</table>')
        right: List[str] = []
        if pr.get("factors_pos"):
            right.append(f'<div class="sec">{T("Supporting infection", "عوامل تدعم العدوى")}</div>')
            for f in pr["factors_pos"]:
                right.append(f'<div class="row pos" style="unicode-bidi:plaintext">{_esc(f)}</div>')
        if pr.get("factors_neg"):
            right.append(f'<div class="sec">{T("Against infection", "عوامل ضد العدوى")}</div>')
            for f in pr["factors_neg"]:
                right.append(f'<div class="row neg" style="unicode-bidi:plaintext">{_esc(f)}</div>')
        if left and right:
            H.append('<table class="cols"><tr><td>' + "".join(left) + '</td><td class="gap"></td><td>'
                     + "".join(right) + '</td></tr></table>')
        else:
            H.extend(left + right)

        if recs:
            H.append(f'<div class="sec">{T("Recommendations", "التوصيات")}</div>')
            for r_ in recs:
                H.append(f'<div class="row {tcls}">• {_t(r_)}</div>')
        if notes:
            H.append(f'<div class="sec">{T("Interpretive notes", "ملاحظات تفسيرية")}</div>')
            for n_ in notes:
                H.append(f'<div class="row {tcls}">{_t(n_)}</div>')
        if pr.get("references"):
            H.append(f'<div class="row ltr small" style="margin-top:{mm(2, z)}"><b>References:</b> '
                     f'{_esc(" · ".join(pr["references"]))}</div>')
        H.append('<div class="footer">Generated by Orange Lab Pathogenicity Engine. Decision support '
                 'only: the significance of a culture is a clinical judgement that remains with the '
                 'treating physician and the microbiologist.</div></body></html>')
        return _finish("".join(H))

    def _finish(html: str) -> str:
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
        return html.replace("%%PATIENT%%", _esc(patient_ref or ""))

    if return_html:
        return build(scale)
    try:
        # v7.0: one sheet -- the type shrinks step by step until it fits one A4 page
        return render_one_page(build)
    except Exception:
        return None
