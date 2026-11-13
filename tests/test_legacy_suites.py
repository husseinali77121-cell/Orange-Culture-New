# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""The 21 regression suites written before the package split, each run as its own script.

They are kept as they were (own `check()` harness, exit code 0 = green); only the way
they load the application changed -- see tests/legacy/legacy_support.py.
"""
import pathlib
import subprocess
import sys

import pytest

LEGACY = pathlib.Path(__file__).resolve().parent / "legacy"
SUITES = sorted(p.name for p in LEGACY.glob("test_*.py"))


def test_all_legacy_suites_are_present():
    assert len(SUITES) >= 21, SUITES


@pytest.mark.parametrize("suite", SUITES)
def test_legacy_suite(suite):
    r = subprocess.run([sys.executable, suite], cwd=LEGACY, capture_output=True, text=True,
                       timeout=1500)
    tail = "\n".join((r.stdout + "\n" + r.stderr).strip().splitlines()[-25:])
    assert r.returncode == 0, f"{suite} failed:\n{tail}"
