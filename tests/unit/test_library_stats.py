"""Statistics and integrity checks over the SQLite library."""

from datetime import datetime, timedelta
from pathlib import Path

from youmudow.domain.models import HistoryEntry
from youmudow.services.library_store import LibraryStore


def _entry(url: str, title: str = "T", size: int = 10, fmt: str = "mp3", **kw) -> HistoryEntry:
    now = datetime.now().astimezone()
    return HistoryEntry(
        title=title,
        url=url,
        uploader=kw.pop("uploader", "Chan"),
        file_format=fmt,
        output_path=kw.pop("output_path", "/tmp/x.mp3"),
        downloaded_at=kw.pop("downloaded_at", now.isoformat()),
        file_size_bytes=size,
    )


def test_stats_totals_and_breakdowns(tmp_path):
    store = LibraryStore(tmp_path / "db.sqlite")
    store.add_history(_entry("https://x.test/1", size=100, fmt="mp3"))
    store.add_history(_entry("https://x.test/2", size=300, fmt="mp4"))
    store.add_history(_entry("https://x.test/3", size=600, fmt="mp3"))

    stats = store.stats()

    assert stats["count"] == 3
    assert stats["total_bytes"] == 1000
    assert ("mp3", 2, 700) in stats["by_format"]
    assert ("mp4", 1, 300) in stats["by_format"]
    assert ("Chan", 3, 1000) in stats["by_uploader"]


def test_stats_groups_by_month(tmp_path):
    store = LibraryStore(tmp_path / "db.sqlite")
    old = (datetime.now().astimezone() - timedelta(days=40)).isoformat()
    store.add_history(_entry("https://x.test/1", size=100, downloaded_at=old))
    store.add_history(_entry("https://x.test/2", size=50))

    months = store.stats()["by_month"]

    assert [count for _, count, _ in months] == [1, 1]
    assert sum(size for _, _, size in months) == 150


def test_missing_downloads_lists_entries_without_their_file(tmp_path):
    store = LibraryStore(tmp_path / "db.sqlite")
    present = tmp_path / "present.mp3"
    present.write_bytes(b"x")
    store.add_history(_entry("https://x.test/1", output_path=str(present)))
    store.add_history(_entry("https://x.test/2", output_path=str(tmp_path / "gone.mp3")))
    store.add_history(_entry("https://x.test/3", output_path=""))

    missing = store.missing_downloads()

    assert [entry.url for entry in missing] == ["https://x.test/3", "https://x.test/2"]


def test_stats_on_an_empty_library(tmp_path):
    stats = LibraryStore(Path(tmp_path) / "db.sqlite").stats()
    assert stats == {
        "count": 0,
        "total_bytes": 0,
        "by_month": [],
        "by_format": [],
        "by_uploader": [],
    }
