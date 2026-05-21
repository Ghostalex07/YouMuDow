"""Tests for domain models."""

from youmudow.domain.models import Video


class TestVideoFormatDuration:
    """Tests for Video.format_duration method."""

    def test_zero_duration_returns_dash(self):
        video = Video(title="Test", url="https://youtube.com/watch?v=x")
        assert video.format_duration() == "-"

    def test_seconds_only(self):
        video = Video(title="Test", url="https://youtube.com/watch?v=x", duration=45)
        assert video.format_duration() == "0:45"

    def test_minutes_and_seconds(self):
        video = Video(title="Test", url="https://youtube.com/watch?v=x", duration=185)
        assert video.format_duration() == "3:05"

    def test_hours_minutes_seconds(self):
        video = Video(title="Test", url="https://youtube.com/watch?v=x", duration=3661)
        assert video.format_duration() == "1:01:01"

    def test_exactly_one_hour(self):
        video = Video(title="Test", url="https://youtube.com/watch?v=x", duration=3600)
        assert video.format_duration() == "1:00:00"
