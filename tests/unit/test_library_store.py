"""Tests for the SQLite library store."""

import json

import pytest

from youmudow.domain.models import HistoryEntry
from youmudow.services.library_store import MAX_HISTORY, LibraryStore


def _entry(title="Song", url="https://x.test/1", downloaded_at="2026-11-20T10:00:00"):
    return HistoryEntry(
        title=title,
        url=url,
        uploader="Chan",
        file_format="mp3",
        output_path="/music/song.mp3",
        downloaded_at=downloaded_at,
        duration=200,
        thumbnail="https://x.test/t.jpg",
        file_size_bytes=1234,
    )


def test_history_round_trip(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    store.add_history(_entry())
    rows = store.history()
    assert len(rows) == 1
    assert rows[0].title == "Song"
    assert rows[0].file_size_bytes == 1234
    assert rows[0].duration == 200
    store.close()


def test_history_is_newest_first(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    store.add_history(_entry("Old", "https://x.test/1"))
    store.add_history(_entry("New", "https://x.test/2"))
    assert [row.title for row in store.history()] == ["New", "Old"]
    store.close()


def test_recent_duplicate_url_is_not_added_twice(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    store.add_history(_entry())
    store.add_history(_entry(downloaded_at="2026-11-21T10:00:00"))
    assert store.count_history() == 1
    store.close()


def test_history_is_trimmed_to_the_limit(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    for i in range(MAX_HISTORY + 5):
        store.add_history(_entry(f"Song {i}", f"https://x.test/{i}"))
    assert store.count_history() == MAX_HISTORY
    store.close()


def test_remove_and_clear(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    first, second = _entry(), _entry("Other", "https://x.test/2")
    store.add_history(first)
    store.add_history(second)
    store.remove_history(first)
    assert [row.title for row in store.history()] == ["Other"]
    store.clear_history()
    assert store.history() == []
    store.close()


def test_data_survives_reopening(tmp_path):
    path = tmp_path / "lib.db"
    store = LibraryStore(path)
    store.add_history(_entry())
    store.close()

    reopened = LibraryStore(path)
    assert reopened.count_history() == 1
    reopened.close()


def test_subscriptions_are_unique(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    assert store.add_subscription("https://x.test/chan", "Chan", "channel") is True
    assert store.add_subscription("https://x.test/chan", "Chan", "channel") is False
    assert [row["url"] for row in store.subscriptions()] == ["https://x.test/chan"]
    store.mark_subscription_checked("https://x.test/chan")
    assert store.subscriptions()[0]["last_checked"] is not None
    store.remove_subscription("https://x.test/chan")
    assert store.subscriptions() == []
    store.close()


def test_import_history_json_keeps_order_and_is_one_shot(tmp_path):
    legacy = tmp_path / "history.json"
    legacy.write_text(
        json.dumps(
            [
                {"title": "New", "url": "https://x.test/2", "uploader": "C"},
                {"title": "Old", "url": "https://x.test/1", "uploader": "C"},
            ]
        ),
        encoding="utf-8",
    )
    store = LibraryStore(tmp_path / "lib.db")

    assert store.import_history_json(legacy) == 2
    assert [row.title for row in store.history()] == ["New", "Old"]
    # A second run must not duplicate anything.
    assert store.import_history_json(legacy) == 0
    assert store.count_history() == 2
    store.close()


def test_import_ignores_a_corrupt_file(tmp_path):
    legacy = tmp_path / "history.json"
    legacy.write_text("{not json", encoding="utf-8")
    store = LibraryStore(tmp_path / "lib.db")
    assert store.import_history_json(legacy) == 0
    assert store.count_history() == 0
    store.close()


def test_queue_round_trip_replaces_previous_entries(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    store.replace_queue(['{"url": "https://x.test/a", "title": "A"}'])
    store.replace_queue(
        ['{"url": "https://x.test/b", "title": "B"}', '{"url": "https://x.test/c", "title": "C"}']
    )
    assert [json.loads(p)["url"] for p in store.queue_payloads()] == [
        "https://x.test/b",
        "https://x.test/c",
    ]
    store.close()


def test_import_queue_json_is_one_shot(tmp_path):
    legacy = tmp_path / "queue.json"
    legacy.write_text(
        json.dumps(
            [{"url": "https://x.test/a", "title": "A"}, {"url": "https://x.test/b", "title": "B"}]
        ),
        encoding="utf-8",
    )
    store = LibraryStore(tmp_path / "lib.db")
    assert store.import_queue_json(legacy) == 2
    assert len(store.queue_payloads()) == 2
    assert store.import_queue_json(legacy) == 0
    store.close()


def test_has_url_reports_recorded_downloads(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    assert store.has_url("https://x.test/a") is False
    store.add_history(_entry(url="https://x.test/a"))
    assert store.has_url("https://x.test/a") is True
    store.close()


def test_fresh_database_is_stamped_with_the_current_schema_version(tmp_path):
    from youmudow.services import library_store

    store = library_store.LibraryStore(tmp_path / "lib.db")
    try:
        version = store._conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        store.close()
    assert version == library_store.SCHEMA_VERSION


def test_existing_rows_survive_the_migration_from_version_zero(tmp_path):
    import sqlite3

    path = tmp_path / "lib.db"
    legacy = sqlite3.connect(path)
    legacy.executescript(
        "CREATE TABLE downloads (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL,"
        " title TEXT NOT NULL, uploader TEXT NOT NULL DEFAULT '',"
        " file_format TEXT NOT NULL DEFAULT '', output_path TEXT NOT NULL DEFAULT '',"
        " file_size_bytes INTEGER NOT NULL DEFAULT 0, duration INTEGER NOT NULL DEFAULT 0,"
        " thumbnail TEXT NOT NULL DEFAULT '', downloaded_at TEXT NOT NULL);"
    )
    legacy.execute(
        "INSERT INTO downloads (url, title, downloaded_at) VALUES (?, ?, ?)",
        ("https://x.test/old", "Old", "2026-01-01T00:00:00+00:00"),
    )
    legacy.commit()
    legacy.close()

    from youmudow.services import library_store

    store = library_store.LibraryStore(path)
    try:
        assert store.count_history() == 1
        version = store._conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        store.close()
    assert version == library_store.SCHEMA_VERSION


def test_a_failing_migration_leaves_the_database_untouched(tmp_path, monkeypatch):
    import sqlite3

    from youmudow.domain.models import HistoryEntry
    from youmudow.services import library_store

    path = tmp_path / "lib.db"
    store = library_store.LibraryStore(path)
    store.add_history(
        HistoryEntry(
            title="Kept",
            url="https://x.test/kept",
            uploader="",
            file_format="mp3",
            output_path="",
            downloaded_at="2026-01-01T00:00:00+00:00",
        )
    )
    store.close()

    def broken(_conn):
        raise sqlite3.OperationalError("boom")

    monkeypatch.setattr(library_store, "MIGRATIONS", [*library_store.MIGRATIONS, broken])
    monkeypatch.setattr(library_store, "SCHEMA_VERSION", 2)

    with pytest.raises(library_store.LibraryError):
        library_store.LibraryStore(path)

    reopened = sqlite3.connect(path)
    try:
        assert reopened.execute("PRAGMA user_version").fetchone()[0] == 1
        assert reopened.execute("SELECT COUNT(*) FROM downloads").fetchone()[0] == 1
    finally:
        reopened.close()


def test_a_corrupt_database_raises_library_error(tmp_path):
    from youmudow.services import library_store

    path = tmp_path / "lib.db"
    path.write_bytes(b"this is not a database" * 100)

    with pytest.raises(library_store.LibraryError):
        library_store.LibraryStore(path)


def test_search_history_matches_title_channel_and_path(tmp_path):
    from youmudow.domain.models import HistoryEntry

    store = LibraryStore(tmp_path / "lib.db")
    store.add_history(
        HistoryEntry(
            title="Lofi Rain",
            url="https://x.test/1",
            uploader="ChillHop",
            file_format="mp3",
            output_path="/music/lofi.mp3",
            downloaded_at="2026-01-01T00:00:00+00:00",
            file_size_bytes=1,
        )
    )
    store.add_history(
        HistoryEntry(
            title="Other",
            url="https://x.test/2",
            uploader="Someone",
            file_format="mp3",
            output_path="/music/other.mp3",
            downloaded_at="2026-01-02T00:00:00+00:00",
            file_size_bytes=1,
        )
    )

    assert [e.title for e in store.search_history("lofi")] == ["Lofi Rain"]
    assert [e.title for e in store.search_history("CHILLHOP")] == ["Lofi Rain"]
    assert [e.title for e in store.search_history("other.mp3")] == ["Other"]
