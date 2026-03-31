"""Metadata service for YouMuDow.

Handles extraction and processing of video metadata.
"""

from typing import Any

from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
from youmudow.domain.models import Video


class MetadataService:
    """Service for extracting and processing video metadata."""

    def __init__(self, adapter: YtdlpAdapter | None = None) -> None:
        self._adapter = adapter or YtdlpAdapter()

    def get_metadata(self, url: str) -> Video | None:
        return self._adapter.get_metadata(url)

    def extract_title(self, video: Video) -> str:
        return video.title.strip()

    def extract_uploader(self, video: Video) -> str:
        return video.uploader.strip()

    def extract_duration_formatted(self, video: Video) -> str:
        seconds = video.duration
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def extract_playlist_info(self, url: str) -> dict[str, Any]:
        return {"url": url, "type": "playlist" if "playlist" in url else "video"}

    def format_for_display(self, video: Video) -> dict[str, str]:
        return {
            "title": self.extract_title(video),
            "uploader": self.extract_uploader(video),
            "duration": self.extract_duration_formatted(video),
            "url": video.url,
            "thumbnail": video.thumbnail,
        }
