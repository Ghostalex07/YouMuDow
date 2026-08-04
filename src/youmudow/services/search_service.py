"""Search service for YouMuDow.

Handles video search operations using yt-dlp adapter.
"""

from typing import Protocol

from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
from youmudow.domain.models import Video


class YtdlpAdapterProtocol(Protocol):
    """Protocol defining the search adapter interface."""

    def search(self, query: str, limit: int = 10) -> list[Video]: ...

    def get_metadata(self, url: str) -> Video | None: ...

    def get_playlist_videos(self, url: str, limit: int = 50) -> list[Video]: ...


class SearchService:
    """Service for searching videos."""

    def __init__(self, adapter: YtdlpAdapterProtocol | None = None) -> None:
        self._adapter = adapter or YtdlpAdapter()

    def set_log_callback(self, callback) -> None:
        if hasattr(self._adapter, "set_log_callback"):
            self._adapter.set_log_callback(callback)

    def search(self, query: str, limit: int = 10) -> list[Video]:
        if not query or not query.strip():
            return []
        return self._adapter.search(query.strip(), limit)

    def get_metadata(self, url: str) -> Video | None:
        return self._adapter.get_metadata(url)

    def get_playlist(self, url: str, limit: int = 50) -> list[Video]:
        return self._adapter.get_playlist_videos(url, limit)
