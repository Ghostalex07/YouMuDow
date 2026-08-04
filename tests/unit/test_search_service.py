"""Tests for search service."""

from unittest.mock import Mock

import pytest

from youmudow.domain.models import Video
from youmudow.services.search_service import SearchService


@pytest.fixture
def mock_adapter():
    """Create a mock adapter."""
    return Mock()


@pytest.fixture
def search_service(mock_adapter):
    """Create a search service with mock adapter."""
    return SearchService(adapter=mock_adapter)


class TestSearchService:
    """Tests for SearchService."""

    def test_init_with_adapter(self, mock_adapter):
        service = SearchService(adapter=mock_adapter)
        assert service._adapter is mock_adapter

    def test_init_without_adapter(self):
        service = SearchService()
        assert service._adapter is not None

    def test_search_returns_results(self, search_service, mock_adapter):
        expected = [
            Video(title="Video 1", url="url1"),
            Video(title="Video 2", url="url2"),
        ]
        mock_adapter.search.return_value = expected

        results = search_service.search("test query")

        assert results == expected
        mock_adapter.search.assert_called_once_with("test query", 10)

    def test_search_trims_query(self, search_service, mock_adapter):
        mock_adapter.search.return_value = []
        search_service.search("  test query  ")
        mock_adapter.search.assert_called_once_with("test query", 10)

    def test_search_empty_query_returns_empty(self, search_service, mock_adapter):
        results = search_service.search("")
        assert results == []
        mock_adapter.search.assert_not_called()

    def test_search_whitespace_query_returns_empty(self, search_service, mock_adapter):
        results = search_service.search("   ")
        assert results == []
        mock_adapter.search.assert_not_called()

    def test_search_with_custom_limit(self, search_service, mock_adapter):
        mock_adapter.search.return_value = []
        search_service.search("test", limit=5)
        mock_adapter.search.assert_called_once_with("test", 5)

    def test_get_metadata_calls_adapter(self, search_service, mock_adapter):
        expected = Video(title="Test", url="url")
        mock_adapter.get_metadata.return_value = expected
        result = search_service.get_metadata("https://youtube.com/watch?v=abc")
        assert result == expected


class TestSearchServiceIntegration:
    """Integration tests for SearchService with mocked yt-dlp."""

    def test_search_flow(self):
        """Test complete search flow with mock."""
        mock_adapter = Mock()
        mock_adapter.search.return_value = [
            Video(title="Song - Artist", url="https://youtube.com/watch?v=123"),
            Video(title="Artist - Song", url="https://youtube.com/watch?v=456"),
        ]

        service = SearchService(adapter=mock_adapter)
        results = service.search("test song")

        assert len(results) == 2
        assert results[0].title == "Song - Artist"
