"""Tests for the thumbnail service."""

import pytest

from youmudow.services.thumbnail_service import ThumbnailService


@pytest.fixture
def service():
    return ThumbnailService()


class TestExtractVideoId:
    def test_watch_url(self, service):
        assert service.extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self, service):
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s"
        assert service.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_embed_url_is_not_matched(self, service):
        assert service.extract_video_id("https://youtube.com/embed/dQw4w9WgXcQ") is None

    def test_youtu_be_short_url(self, service):
        assert service.extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self, service):
        assert service.extract_video_id("https://youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_non_youtube_url(self, service):
        assert service.extract_video_id("https://example.com/video/123") is None

    def test_empty_string(self, service):
        assert service.extract_video_id("") is None


class TestGetUrl:
    def test_default_quality(self, service):
        assert (
            service.get_url("dQw4w9WgXcQ") == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        )

    def test_custom_quality(self, service):
        assert service.get_url("dQw4w9WgXcQ", "maxresdefault") == (
            "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
        )


class TestGetThumbnailUrl:
    def test_valid_youtube_url(self, service):
        assert service.get_thumbnail_url("https://youtube.com/watch?v=dQw4w9WgXcQ") == (
            "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        )

    def test_short_url(self, service):
        assert service.get_thumbnail_url("https://youtu.be/dQw4w9WgXcQ") == (
            "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        )

    def test_unrecognized_url_returns_empty(self, service):
        assert service.get_thumbnail_url("https://example.com/foo") == ""

    def test_empty_url_returns_empty(self, service):
        assert service.get_thumbnail_url("") == ""
