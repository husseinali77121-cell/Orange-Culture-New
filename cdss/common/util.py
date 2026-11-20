# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Small pure helpers."""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
import datetime as _dt
import hashlib
import os




def make_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default

def get_route_label(item: Dict[str, Any]) -> str:
    return "🟢 Oral preferred / PO-friendly" if item.get("high_po") else "💉 IV/IM only"

def uniq_keep_order(items: List[str]) -> List[str]:
    seen:   set       = set()
    result: List[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result

def best_default_index(options: List[str], preferred: Optional[str]) -> int:
    if preferred and preferred in options:
        return options.index(preferred)
    return 0


# ── The laboratory's calendar date, whatever the machine clock (v7.5) ────
# External review of v7.4: tests/legacy/test_guidelines.py failed with "rule
# 'hier_pip_vs_tzp' was verified in the future (2026-11-20)" on a CI machine set
# to UTC, where it was still 19 November while it was already 20 November in
# Cairo, where the verification was dated. Every review date in the registry is
# a Cairo date, so "today" is compared in Cairo too.
#
#   * ORANGE_LAB_TODAY=YYYY-MM-DD pins the date (reproducible runs); an invalid
#     value is reported and ignored (v7.6) -- it used to raise in every caller;
#   * otherwise Africa/Cairo via zoneinfo (tzdata is a requirement and is
#     bundled into the Windows EXE, v7.6);
#   * without timezone data, Egypt's own rule (v7.6 -- v7.5 used a fixed UTC+3,
#     one hour wrong all winter): UTC+2, and UTC+3 from the last Friday of April
#     00:00 to the last Thursday of October 24:00, since 2023 (tz database
#     "Rule Egypt 2023 max"; no summer time 2015-2022). Checked hour by hour
#     against zoneinfo for 2023-2035 in tests/test_v7_6_review.py.
import logging as _logging

LAB_TZ = "Africa/Cairo"
_log = _logging.getLogger(__name__)


def _last_weekday(year: int, month: int, weekday: int) -> _dt.date:
    """The last <weekday> (Mon=0 .. Sun=6) of a month."""
    d = (_dt.date(year, month + 1, 1) if month < 12 else _dt.date(year + 1, 1, 1)) - _dt.timedelta(days=1)
    return d - _dt.timedelta(days=(d.weekday() - weekday) % 7)


def egypt_utc_offset(now_utc: _dt.datetime) -> _dt.timedelta:
    """Egypt's offset from UTC at an instant, by rule (no tz database needed)."""
    now = now_utc.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    if now.year < 2023:
        return _dt.timedelta(hours=2)
    # summer time starts at local 00:00 (UTC+2) on the last Friday of April
    start = _dt.datetime.combine(_last_weekday(now.year, 4, 4), _dt.time()) - _dt.timedelta(hours=2)
    # and ends at local 24:00 (UTC+3) on the last Thursday of October
    end = (_dt.datetime.combine(_last_weekday(now.year, 10, 3), _dt.time())
           + _dt.timedelta(hours=24) - _dt.timedelta(hours=3))
    return _dt.timedelta(hours=3 if start <= now < end else 2)


def _pinned_date() -> Optional[_dt.date]:
    pinned = os.environ.get("ORANGE_LAB_TODAY", "").strip()
    if not pinned:
        return None
    try:
        return _dt.date.fromisoformat(pinned)
    except ValueError:
        _log.warning("ORANGE_LAB_TODAY=%r is not a YYYY-MM-DD date -- ignored, the clock is used",
                     pinned)
        return None


def lab_today(now_utc: Optional[_dt.datetime] = None, *, use_tz_database: bool = True) -> _dt.date:
    if now_utc is None:
        pinned = _pinned_date()
        if pinned is not None:
            return pinned
    now = now_utc or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    if use_tz_database:
        try:
            from zoneinfo import ZoneInfo
            return now.astimezone(ZoneInfo(LAB_TZ)).date()
        except Exception:
            pass
    return (now.astimezone(_dt.timezone.utc) + egypt_utc_offset(now)).date()
