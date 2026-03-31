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


class SearchService:
    """Service for searching videos."""

    def __init__(self, adapter: YtdlpAdapterProtocol | None = None) -> None:
        self._adapter = adapter or YtdlpAdapter()

    def search(self, query: str, limit: int = 10) -> list[Video]:
        if not query or not query.strip():
            return []
        return self._adapter.search(query.strip(), limit)

    def search_by_url(self, url: str) -> Video | None:
        return self.get_metadata(url)

    def get_metadata(self, url: str) -> Video | None:
        return self._adapter.get_metadata(url)
