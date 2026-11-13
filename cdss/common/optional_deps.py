# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Optional third-party libraries (OCR, PIL, WeasyPrint, Arabic shaping) and their availability flags."""



try:
    import cv2
    import numpy as np
    import pytesseract
    OCR_AVAILABLE = True
    OCR_IMPORT_ERROR = ""
except Exception as exc:
    cv2 = None
    np = None
    pytesseract = None
    OCR_AVAILABLE = False
    OCR_IMPORT_ERROR = str(exc)

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = ImageDraw = ImageFont = None

try:
    import weasyprint as _wp
    WEASYPRINT_AVAILABLE = True
except Exception:
    # Broad except deliberately, not ImportError: weasyprint's native
    # dependency (GTK3/Pango/Cairo, via cffi) raises OSError -- not
    # ImportError -- when the Python package is installed but the native
    # library is missing or broken (e.g. "cannot load library
    # 'libgobject-2.0-0'"). An ImportError-only except let that OSError
    # propagate and crash app startup entirely instead of degrading to "no
    # PDF generation", on ANY machine with a partial GTK3 install -- found
    # 2026-08-22 when the Windows EXE build's own test step hit exactly
    # this before GTK3 had been staged yet.
    WEASYPRINT_AVAILABLE = False
    _wp = None

try:
    import arabic_reshaper as _arabic_reshaper_mod
    from bidi.algorithm import get_display as _bidi_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False
    _arabic_reshaper_mod = None
    _bidi_display = None
