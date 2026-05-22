"""Data models for YouMuDow."""

from dataclasses import dataclass, field
from datetime import datetime as _dt
from pathlib import Path

from youmudow.domain.enums import DownloadStatus


@dataclass
class DownloadOptions:
    """Options for downloading a video."""

    file_format: str = "mp3"
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
    speed: str = ""
    eta: str = ""
    options: DownloadOptions = field(default_factory=DownloadOptions)

    def format_duration(self) -> str:
        if self.duration == 0:
            return "-"
        minutes, secs = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if isinstance(self.options, dict):
            self.options = DownloadOptions(**self.options)

@dataclass
class HistoryEntry:
    title: str
    url: str
    uploader: str
    file_format: str
    output_path: str
    downloaded_at: str
    duration: int = 0
    thumbnail: str = ""
    file_size_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "uploader": self.uploader,
            "file_format": self.file_format,
            "output_path": self.output_path,
            "downloaded_at": self.downloaded_at,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "file_size_bytes": self.file_size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            uploader=data.get("uploader", ""),
            file_format=data.get("file_format", ""),
            output_path=data.get("output_path", ""),
            downloaded_at=data.get("downloaded_at", ""),
            duration=data.get("duration", 0),
            thumbnail=data.get("thumbnail", ""),
            file_size_bytes=data.get("file_size_bytes", 0),
        )

    def format_date(self) -> str:
        try:
            dt = _dt.fromisoformat(self.downloaded_at)
            return dt.strftime("%d %b %Y %H:%M")
        except Exception:
            return self.downloaded_at

    def format_size(self) -> str:
        if self.file_size_bytes <= 0:
            return ""
        size = self.file_size_bytes
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
