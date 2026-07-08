"""Build and normalize a segment timeline for multi-model rendering."""

from __future__ import annotations

from typing import Any

_DEFAULT_FADE = 0.03


def build_segments(raw_segments: list[dict[str, Any]], lrc_text: str, default_model_id: str, duration: float | None) -> list[dict[str, Any]]:
    """Normalize a segment timeline.

    Accepts either explicit ``raw_segments`` or an LRC string. Missing segment
    ends are inferred from the next segment start; the final segment end falls
    back to ``duration`` when known.
    """
    from application.lrc_parser import parse_lrc

    if raw_segments:
        segments = [_coerce(seg, default_model_id) for seg in raw_segments]
    else:
        segments = [
            {
                "id": f"seg_{idx:03d}",
                "start": line["start"],
                "end": None,
                "text": line.get("text", ""),
                "assigned_model_ids": [default_model_id],
                "mode": "solo",
                "fade_in": _DEFAULT_FADE,
                "fade_out": _DEFAULT_FADE,
            }
            for idx, line in enumerate(parse_lrc(lrc_text))
        ]

    segments.sort(key=lambda seg: float(seg["start"]))
    for idx, seg in enumerate(segments):
        seg["id"] = seg.get("id") or f"seg_{idx:03d}"
        if seg.get("end") is None:
            nxt = segments[idx + 1]["start"] if idx + 1 < len(segments) else duration
            seg["end"] = float(nxt) if nxt is not None else float(seg["start"])
        seg["end"] = float(seg["end"])
        if seg["end"] < seg["start"]:
            seg["end"] = float(seg["start"])
        if duration is not None and seg["end"] > duration:
            seg["end"] = duration
    return segments


def _coerce(seg: dict[str, Any], default_model_id: str) -> dict[str, Any]:
    assigned = seg.get("assigned_model_ids")
    if not isinstance(assigned, list) or not assigned:
        assigned = [default_model_id]
    return {
        "id": str(seg.get("id") or ""),
        "start": float(seg.get("start") or 0),
        "end": None if seg.get("end") in (None, "") else float(seg.get("end")),
        "text": str(seg.get("text") or ""),
        "assigned_model_ids": [str(m) for m in assigned],
        "mode": str(seg.get("mode") or "solo"),
        "fade_in": float(seg.get("fade_in") if seg.get("fade_in") is not None else _DEFAULT_FADE),
        "fade_out": float(seg.get("fade_out") if seg.get("fade_out") is not None else _DEFAULT_FADE),
    }
