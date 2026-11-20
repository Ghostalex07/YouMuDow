"""Group download failures by the reason a person can act on."""

from collections.abc import Sequence
from enum import Enum

from youmudow.domain.models import Video


class ErrorCause(str, Enum):
    PRIVATE = "private"
    COOKIES = "cookies"
    GEO = "geo"
    NETWORK = "network"
    UNSUPPORTED = "unsupported"
    DISK = "disk"
    OTHER = "other"


# Checked in order: the first match wins, so the specific causes come first.
_PATTERNS: tuple[tuple[ErrorCause, tuple[str, ...]], ...] = (
    (
        ErrorCause.COOKIES,
        (
            "sign in to confirm",
            "cookies",
            "login required",
            "log in",
            "confirm you're not a bot",
        ),
    ),
    (
        ErrorCause.GEO,
        (
            "not available in your country",
            "geo restricted",
            "geo-restricted",
            "blocked it in your country",
            "in your country",
        ),
    ),
    (
        ErrorCause.PRIVATE,
        (
            "private video",
            "video unavailable",
            "this video is unavailable",
            "has been removed",
            "members-only",
            "account has been terminated",
        ),
    ),
    (
        ErrorCause.DISK,
        (
            "no space left",
            "permission denied",
            "read-only file system",
            "errno 28",
        ),
    ),
    (
        ErrorCause.NETWORK,
        (
            "timed out",
            "timeout",
            "connection",
            "network",
            "getaddrinfo",
            "temporary failure",
            "unable to download",
        ),
    ),
    (
        ErrorCause.UNSUPPORTED,
        (
            "unsupported url",
            "no suitable format",
            "requested format",
        ),
    ),
)


def classify_error(message: str | None) -> ErrorCause:
    """Map a yt-dlp error message to the cause a user can act on."""
    text = (message or "").lower()
    for cause, needles in _PATTERNS:
        if any(needle in text for needle in needles):
            return cause
    return ErrorCause.OTHER


def summarize_failures(videos: Sequence[Video]) -> list[tuple[ErrorCause, int]]:
    """Causes with at least one failure, most frequent first."""
    counts: dict[ErrorCause, int] = {}
    for video in videos:
        cause = classify_error(video.error_message)
        counts[cause] = counts.get(cause, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0].value))
