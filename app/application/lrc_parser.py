"""Parse LRC lyrics into a time-ordered list of segments."""

from __future__ import annotations

import re
from typing import Any

_TIME = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def parse_lrc(text: str) -> list[dict[str, Any]]:
    """Return ``[{"start": float, "text": str}, ...]`` sorted by start time."""
    lines: list[dict[str, Any]] = []
    for raw in (text or "").splitlines():
        stamps = list(_TIME.finditer(raw))
        if not stamps:
            continue
        content = raw[stamps[-1].end():].strip()
        for match in stamps:
            minutes, seconds, frac = match.group(1), match.group(2), match.group(3) or "0"
            start = int(minutes) * 60 + int(seconds) + int(frac.ljust(3, "0")) / 1000
            lines.append({"start": start, "text": content})
    lines.sort(key=lambda item: item["start"])
    return lines
