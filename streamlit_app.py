# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Entry point:  streamlit run streamlit_app.py"""
import sys

try:
    from cdss_ui.app import main
except ImportError:
    # A file of the app is missing -- typically a browser upload that is still
    # half done. Streamlit keeps one Python process across reruns, so every
    # module that DID import during this run would stay in memory as it is now,
    # including any that fell back to a "module not available" state. Forget
    # them all, so the first run after the missing file arrives starts clean
    # instead of carrying today's gaps until a reboot.
    for _name in [m for m in sys.modules if m.split(".")[0] in ("cdss", "cdss_ui")]:
        del sys.modules[_name]
    raise

main()
