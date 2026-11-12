"""Download event contract.

Kept apart from the download service so workers, services and any UI layer can
share the event payloads without importing the orchestration code.
"""

from dataclasses import dataclass
from enum import Enum

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video


class DownloadEventType(Enum):
    """Types of download events."""

    QUEUED = "queued"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class DownloadProgress:
    """Detailed progress information for a download."""

    video: Video | None = None
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    status: DownloadStatus = DownloadStatus.READY


@dataclass
class DownloadEvent:
    """Download event with detailed information."""

    type: DownloadEventType
    video: Video
    progress: DownloadProgress | None = None
    error: str | None = None
