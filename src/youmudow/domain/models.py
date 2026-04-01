"""Data models for YouMuDow."""

from dataclasses import dataclass, field
from pathlib import Path

from youmudow.domain.enums import DownloadStatus


@dataclass
class DownloadOptions:
    """Options for downloading a video."""

    format: str = "mp3"
    quality: str = "best"
    subtitles: bool = False
    subtitle_lang: str = "en"
    embed_subtitles: bool = False
    use_cookies: bool = False
    cookies_from_browser: str | None = None
    cookies_profile: str | None = None
    cookies_file: str | None = None
    rate_limit: str | None = None  # e.g., "1M", "500K"
    split_chapters: bool = False


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
    error_message: str = ""
    progress: float = 0.0
    options: DownloadOptions = field(default_factory=DownloadOptions)

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if isinstance(self.options, dict):
            self.options = DownloadOptions(**self.options)
