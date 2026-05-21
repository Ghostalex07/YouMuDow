"""Tests for HistoryService."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from youmudow.services.history_service import HistoryService
from youmudow.domain.models import Video


@pytest.fixture
def temp_history_file():
    with tempfile.TemporaryDirectory() as tmp:
        history_path = Path(tmp) / "history.json"
        with patch("youmudow.services.history_service.HISTORY_FILE", history_path):
            yield history_path


def make_video(title="Test", url="https://example.com/video"):
    return Video(title=title, url=url, uploader="Uploader", duration=120)


class TestHistoryService:
    def test_add_and_get(self, temp_history_file):
        hs = HistoryService()
        video = make_video()
        hs.add(video, "/tmp/test.mp3", "mp3", 1024)
        entries = hs.get_all()
        assert len(entries) == 1
        assert entries[0].title == "Test"
        assert entries[0].file_size_bytes == 1024

    def test_dedup_by_url(self, temp_history_file):
        hs = HistoryService()
        video = make_video(url="https://example.com/dup")
        hs.add(video, "/tmp/a.mp3", "mp3")
        hs.add(video, "/tmp/b.mp3", "mp3")
        entries = hs.get_all()
        assert len(entries) == 1

    def test_remove(self, temp_history_file):
        hs = HistoryService()
        video = make_video()
        hs.add(video, "/tmp/test.mp3", "mp3")
        entries = hs.get_all()
        hs.remove(entries[0])
        assert len(hs.get_all()) == 0

    def test_clear(self, temp_history_file):
        hs = HistoryService()
        hs.add(make_video(title="A"), "/tmp/a.mp3", "mp3")
        hs.add(make_video(title="B"), "/tmp/b.mp3", "mp3")
        hs.clear()
        assert len(hs.get_all()) == 0

    def test_search(self, temp_history_file):
        hs = HistoryService()
        hs.add(make_video(title="Song One", url="https://example.com/1"), "/tmp/1.mp3", "mp3")
        hs.add(make_video(title="Another Track", url="https://example.com/2"), "/tmp/2.mp3", "mp3")
        results = hs.search("Song")
        assert len(results) == 1
        assert results[0].title == "Song One"

    def test_persistence_across_instances(self, temp_history_file):
        hs1 = HistoryService()
        hs1.add(make_video(url="https://example.com/persist"), "/tmp/p.mp3", "mp3")
        hs2 = HistoryService()
        entries = hs2.get_all()
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/persist"

    def test_corrupted_json_fallback(self, temp_history_file):
        temp_history_file.write_text("corrupted json", encoding="utf-8")
        hs = HistoryService()
        assert len(hs.get_all()) == 0
