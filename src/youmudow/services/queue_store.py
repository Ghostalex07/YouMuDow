"""Durable storage for the pending download queue.

The queue file is a convenience, never a source of truth: an unreadable or
half-written file is logged and ignored (it is kept on disk for inspection),
and a missing one simply means "nothing to restore".
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video
from youmudow.services.persistence import write_atomic

logger = logging.getLogger(__name__)

_PERSISTED_FIELDS = ("title", "url", "uploader", "duration", "thumbnail")


def video_to_dict(video: Video) -> dict[str, Any]:
    """Serialise the fields needed to re-queue a video later."""
    data: dict[str, Any] = {name: getattr(video, name) for name in _PERSISTED_FIELDS}
    data["options"] = asdict(video.options)
    return data


def video_from_dict(data: dict[str, Any]) -> Video | None:
    """Rebuild a queued video, or None when the entry cannot be trusted."""
    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    raw_options = data.get("options")
    try:
        options = (
            DownloadOptions(**raw_options) if isinstance(raw_options, dict) else DownloadOptions()
        )
    except TypeError:
        logger.warning("Ignoring unknown queue options for %s", url)
        options = DownloadOptions()
    duration = data.get("duration")
    thumbnail = data.get("thumbnail")
    return Video(
        title=str(data.get("title") or url),
        url=url,
        uploader=str(data.get("uploader") or ""),
        duration=duration if isinstance(duration, int) else 0,
        thumbnail=thumbnail if isinstance(thumbnail, str) else "",
        status=DownloadStatus.READY,
        options=options,
    )


def save_queue(path: Path, videos: Sequence[Video]) -> None:
    """Write the pending queue atomically."""
    payload = json.dumps([video_to_dict(video) for video in videos], indent=2)
    write_atomic(path, payload)


def load_queue(path: Path) -> list[Video]:
    """Read the pending queue, dropping anything unusable."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable queue file %s: %s", path, exc)
        return []
    if not isinstance(raw, list):
        logger.warning("Ignoring queue file %s: expected a list of entries", path)
        return []

    videos: list[Video] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        video = video_from_dict(entry)
        if video is not None:
            videos.append(video)
    return videos
