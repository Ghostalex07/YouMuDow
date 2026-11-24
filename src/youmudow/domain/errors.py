"""Domain vocabulary for download failures.

Keeping the classification here means the UI never inspects yt-dlp text and a
new release of yt-dlp only requires touching one table.
"""

from enum import Enum


class DownloadErrorKind(str, Enum):
    PRIVATE = "private"
    COOKIES = "cookies"
    GEO = "geo"
    NETWORK = "network"
    UNSUPPORTED = "unsupported"
    DISK = "disk"
    OTHER = "other"


# Checked in order: the first match wins, so the specific causes come first.
# "cookies" is ahead of "unavailable" on purpose: a bot check also says the
# video is unavailable, but signing in is what actually fixes it.
DOWNLOAD_ERROR_PATTERNS: tuple[tuple[DownloadErrorKind, tuple[str, ...]], ...] = (
    (
        DownloadErrorKind.COOKIES,
        (
            "sign in to confirm",
            "cookies",
            "login required",
            "log in",
            "confirm you're not a bot",
        ),
    ),
    (
        DownloadErrorKind.GEO,
        (
            "not available in your country",
            "geo restricted",
            "geo-restricted",
            "blocked it in your country",
            "in your country",
        ),
    ),
    (
        DownloadErrorKind.PRIVATE,
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
        DownloadErrorKind.DISK,
        (
            "no space left",
            "permission denied",
            "read-only file system",
            "errno 28",
        ),
    ),
    (
        DownloadErrorKind.NETWORK,
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
        DownloadErrorKind.UNSUPPORTED,
        (
            "unsupported url",
            "no suitable format",
            "requested format",
        ),
    ),
)


def classify_download_error(message: str | None) -> DownloadErrorKind:
    """Map a yt-dlp error message to the kind of failure it represents."""
    text = (message or "").lower()
    for kind, needles in DOWNLOAD_ERROR_PATTERNS:
        if any(needle in text for needle in needles):
            return kind
    return DownloadErrorKind.OTHER
