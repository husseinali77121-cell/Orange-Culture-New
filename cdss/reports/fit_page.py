# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Render a report on ONE A4 page whenever the content allows it (v7.0).

The Pathogenicity Assessment and the AST-QA sheets are filed with the culture,
one sheet each (user request, 2026-11-19). The layouts were made compact, and
this helper does the rest: it renders the document at its normal size and, if
that runs past one page, re-renders it at progressively smaller type until it
fits. Below the smallest scale it stops shrinking and returns the last render
(more pages, but still legible) -- text is never clipped to force a fit.

`build(scale)` must return the full HTML for a given type scale (1.0 = normal).
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from cdss.common.optional_deps import WEASYPRINT_AVAILABLE, _wp
from cdss.reports.fonts import with_bundled_fonts
from cdss.reports.html_utils import pdf_glyph_guard

# 1.0 -> 0.70: below ~0.7 the 8.5 pt base would fall under 6 pt.
SCALES: Tuple[float, ...] = (1.0, 0.93, 0.86, 0.80, 0.75, 0.70)


def pt(base: float, scale: float) -> str:
    """A type size in points at this scale (for the f-string CSS)."""
    return f"{base * scale:.2f}pt"


def mm(base: float, scale: float) -> str:
    """A spacing in millimetres at this scale (spacing shrinks with the type)."""
    return f"{base * scale:.2f}mm"


def render_one_page(build: Callable[[float], str],
                    scales: Tuple[float, ...] = SCALES) -> Optional[bytes]:
    """The PDF at the largest scale that fits one page (or the smallest scale)."""
    if not WEASYPRINT_AVAILABLE or _wp is None:
        return None
    doc = None
    for sc in scales:
        doc = _wp.HTML(string=with_bundled_fonts(pdf_glyph_guard(build(sc)))).render()
        if len(doc.pages) <= 1:
            break
    return doc.write_pdf() if doc is not None else None


__all__ = ["render_one_page", "pt", "mm", "SCALES"]
