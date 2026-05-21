"""Metadata service for YouMuDow.

Handles extraction and processing of video metadata.
"""

from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
from youmudow.domain.models import Video


class MetadataService:
    """Service for extracting video metadata."""

    def __init__(self, adapter: YtdlpAdapter | None = None) -> None:
        self._adapter = adapter or YtdlpAdapter()

    def get_metadata(self, url: str) -> Video | None:
        return self._adapter.get_metadata(url)

    def format_for_display(self, video: Video) -> dict[str, str]:
        return {
            "title": video.title.strip(),
            "uploader": video.uploader.strip(),
            "duration": video.format_duration(),
            "url": video.url,
            "thumbnail": video.thumbnail,
        }
