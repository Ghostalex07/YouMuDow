"""Parsing of yt-dlp format listings and size estimation.

Pure functions only: the adapter hands in the JSON payload and the caller
decides what to show. Anything unexpected degrades to "no estimate" instead of
raising, because a missing size must never break a download.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from youmudow.domain.models import DownloadOptions
from youmudow.domain.validators import AUDIO_FORMATS

_VIDEO_HEIGHTS = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080}


@dataclass(frozen=True)
class FormatInfo:
    """One downloadable stream as yt-dlp describes it."""

    format_id: str
    ext: str
    height: int
    abr: float
    tbr: float
    filesize: int


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_formats(payload: dict[str, Any]) -> list[FormatInfo]:
    """Extract the usable formats from a `--dump-single-json` payload."""
    raw = payload.get("formats")
    if not isinstance(raw, list):
        return []

    formats: list[FormatInfo] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        format_id = item.get("format_id")
        if not isinstance(format_id, str) or not format_id:
            continue
        filesize = _to_int(item.get("filesize")) or _to_int(item.get("filesize_approx"))
        formats.append(
            FormatInfo(
                format_id=format_id,
                ext=str(item.get("ext") or ""),
                height=_to_int(item.get("height")),
                abr=_to_float(item.get("abr")),
                tbr=_to_float(item.get("tbr")),
                filesize=filesize,
            )
        )
    return formats


def estimate_size(
    formats: Sequence[FormatInfo], options: DownloadOptions, duration: int
) -> int | None:
    """Estimated bytes for the download `options` would produce, or None."""
    if not duration or duration <= 0:
        return None
    if options.file_format in AUDIO_FORMATS:
        return _estimate_audio(formats, options, duration)
    return _estimate_video(formats, options, duration)


def _estimate_audio(
    formats: Sequence[FormatInfo], options: DownloadOptions, duration: int
) -> int | None:
    quality = options.quality or "best"
    if quality.endswith("kbps"):
        bitrate = _to_int(quality.removesuffix("kbps"))
    else:
        bitrate = int(max((f.abr for f in formats), default=0))
    if bitrate <= 0:
        return None
    return duration * bitrate * 1000 // 8


def _estimate_video(
    formats: Sequence[FormatInfo], options: DownloadOptions, duration: int
) -> int | None:
    target = _VIDEO_HEIGHTS.get(options.quality or "")
    if target is None:
        return None

    candidates = [f for f in formats if 0 < f.height <= target]
    if not candidates:
        return None

    best_height = max(f.height for f in candidates)
    at_target = [f for f in candidates if f.height == best_height]

    sized = [f.filesize for f in at_target if f.filesize > 0]
    if sized:
        return max(sized)

    by_rate = [f for f in at_target if f.tbr > 0]
    if by_rate:
        best = max(by_rate, key=lambda f: f.tbr)
        return int(best.tbr * 1000 / 8 * duration)
    return None
