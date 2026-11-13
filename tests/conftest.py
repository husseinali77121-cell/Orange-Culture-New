# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""pytest configuration: repository root on sys.path; the legacy script suites are
run by tests/test_legacy_suites.py as subprocesses, never collected as modules."""
import logging
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

collect_ignore_glob = ["legacy/*"]
logging.getLogger("orange_cdss").setLevel(logging.CRITICAL)
