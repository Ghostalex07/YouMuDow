"""Group download failures by the reason a person can act on."""

from collections.abc import Sequence

from youmudow.domain.errors import DownloadErrorKind, classify_download_error
from youmudow.domain.models import Video

ErrorCause = DownloadErrorKind


def classify_error(message: str | None) -> ErrorCause:
    """Map a yt-dlp error message to the cause a user can act on."""
    return classify_download_error(message)


def summarize_failures(videos: Sequence[Video]) -> list[tuple[ErrorCause, int]]:
    """Causes with at least one failure, most frequent first."""
    counts: dict[ErrorCause, int] = {}
    for video in videos:
        cause = classify_error(video.error_message)
        counts[cause] = counts.get(cause, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0].value))
