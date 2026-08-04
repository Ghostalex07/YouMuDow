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


class TestHistoryEntryFormatSize:
    def test_format_size_does_not_mutate(self):
        from youmudow.domain.models import HistoryEntry

        e = HistoryEntry(
            title="T",
            url="u",
            uploader="A",
            file_format="mp3",
            output_path="/tmp/t.mp3",
            downloaded_at="2026-01-01T00:00:00",
            file_size_bytes=4_200_000,
        )
        first = e.format_size()
        second = e.format_size()
        assert first == second, f"format_size mutates state: {first!r} != {second!r}"
        assert "MB" in first

    def test_format_size_zero(self):
        from youmudow.domain.models import HistoryEntry

        e = HistoryEntry(
            title="T",
            url="u",
            uploader="A",
            file_format="mp3",
            output_path="/t",
            downloaded_at="2026-01-01T00:00:00",
            file_size_bytes=0,
        )
        assert e.format_size() == ""

    def test_format_size_bytes(self):
        from youmudow.domain.models import HistoryEntry

        e = HistoryEntry(
            title="T",
            url="u",
            uploader="A",
            file_format="mp3",
            output_path="/t",
            downloaded_at="2026-01-01T00:00:00",
            file_size_bytes=500,
        )
        assert "B" in e.format_size()
