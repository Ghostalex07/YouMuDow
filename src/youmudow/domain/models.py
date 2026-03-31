"""Data models for YouMuDow."""

from dataclasses import dataclass, field
from pathlib import Path

from youmudow.domain.enums import DownloadStatus


@dataclass
class Video:
    """Represents a downloadable video."""

    title: str
    url: str
    uploader: str = ""
    duration: int = 0
    thumbnail: str = ""
    status: DownloadStatus = field(default=DownloadStatus.READY)
    path: Path | None = None
    format: str = "mp3"
    error_message: str = ""
    progress: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)
