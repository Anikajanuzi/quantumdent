"""Time zone loading that also works on Windows without the `tzdata` package."""
from __future__ import annotations

import logging
from datetime import timedelta, timezone, tzinfo

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

_warned = False


def get_zone(name: str) -> tzinfo:
    global _warned
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        if not _warned:
            logging.getLogger("quantum").warning(
                "Time zone data for %s not found; using UTC+1. Run: python -m pip install tzdata", name)
            _warned = True
        return timezone(timedelta(hours=1), "CET")
