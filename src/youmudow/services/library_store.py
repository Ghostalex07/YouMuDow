"""SQLite-backed library store for download history and, later, subscriptions.

The JSON files stay the source of truth for settings; this module only owns the
data that grows over time. It is deliberately small: one connection, one lock,
and plain SQL — the UI and the services keep their existing interfaces.
"""

import json
import logging
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from youmudow.domain.models import HistoryEntry

logger = logging.getLogger(__name__)


class LibraryError(RuntimeError):
    """The database could not be opened, checked or migrated safely."""


class LibraryStats(TypedDict):
    count: int
    total_bytes: int
    by_month: list[tuple[str, int, int]]
    by_format: list[tuple[str, int, int]]
    by_uploader: list[tuple[str, int, int]]


MAX_HISTORY = 2000
_RECENT_DUPLICATE_WINDOW = 50

_SCHEMA = """
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    uploader TEXT NOT NULL DEFAULT '',
    file_format TEXT NOT NULL DEFAULT '',
    output_path TEXT NOT NULL DEFAULT '',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    duration INTEGER NOT NULL DEFAULT 0,
    thumbnail TEXT NOT NULL DEFAULT '',
    downloaded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS downloads_downloaded_at ON downloads (downloaded_at DESC);
CREATE INDEX IF NOT EXISTS downloads_url ON downloads (url);

CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    position INTEGER NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'playlist',
    added_at TEXT NOT NULL,
    last_checked TEXT
);
"""

SCHEMA_VERSION = 1


def _migration_1(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


# Index i migrates from version i to i + 1. Never edit a shipped migration:
# append a new one instead, so databases already at that version keep working.
MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_migration_1]


def _check_integrity(conn: sqlite3.Connection) -> None:
    row = conn.execute("PRAGMA quick_check").fetchone()
    if row is not None and row[0] != "ok":
        raise LibraryError(f"database is corrupt: {row[0]}")


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring the schema up to date, one committed step at a time."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise LibraryError(
            f"database schema v{current} is newer than this version supports (v{SCHEMA_VERSION})"
        )
    for version in range(current, SCHEMA_VERSION):
        try:
            with conn:
                MIGRATIONS[version](conn)
                conn.execute(f"PRAGMA user_version = {version + 1}")
        except sqlite3.Error as exc:
            raise LibraryError(f"migration v{version} -> v{version + 1} failed: {exc}") from exc


_COLUMNS = (
    "url, title, uploader, file_format, output_path, "
    "file_size_bytes, duration, thumbnail, downloaded_at"
)


class LibraryStore:
    """Thin synchronous wrapper around the app's SQLite database."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        try:
            conn = sqlite3.connect(str(path), check_same_thread=False)
        except sqlite3.Error as exc:
            raise LibraryError(f"could not open the library: {exc}") from exc
        self._conn = conn
        conn.row_factory = sqlite3.Row
        try:
            with self._lock:
                conn.execute("PRAGMA journal_mode=WAL")
                _check_integrity(conn)
                _migrate(conn)
                conn.commit()
        except sqlite3.Error as exc:
            conn.close()
            raise LibraryError(f"could not open the library: {exc}") from exc
        except LibraryError:
            conn.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- history ---------------------------------------------------------

    def has_url(self, url: str) -> bool:
        """True when this URL already has a row in the download history."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM downloads WHERE url = ? LIMIT 1", (url,)
            ).fetchone()
        return row is not None

    def add_history(self, entry: HistoryEntry) -> None:
        with self._lock:
            recent = self._conn.execute(
                "SELECT url FROM downloads ORDER BY id DESC LIMIT ?",
                (_RECENT_DUPLICATE_WINDOW,),
            ).fetchall()
            if entry.url in {row["url"] for row in recent}:
                return
            self._conn.execute(
                f"INSERT INTO downloads ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.url,
                    entry.title,
                    entry.uploader,
                    entry.file_format,
                    entry.output_path,
                    entry.file_size_bytes,
                    entry.duration,
                    entry.thumbnail,
                    entry.downloaded_at,
                ),
            )
            self._conn.execute(
                "DELETE FROM downloads WHERE id NOT IN "
                "(SELECT id FROM downloads ORDER BY id DESC LIMIT ?)",
                (MAX_HISTORY,),
            )
            self._conn.commit()

    def history(self, limit: int = MAX_HISTORY) -> list[HistoryEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM downloads ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def count_history(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM downloads").fetchone()
        return int(row["n"])

    def remove_history(self, entry: HistoryEntry) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM downloads WHERE url = ? AND downloaded_at = ?",
                (entry.url, entry.downloaded_at),
            )
            self._conn.commit()

    def clear_history(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM downloads")
            self._conn.commit()

    # -- statistics and integrity ----------------------------------------

    def history_paths(self) -> set[str]:
        """Absolute paths the library already knows about."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT output_path FROM downloads WHERE output_path <> ''"
            ).fetchall()
        return {str(Path(row["output_path"]).resolve()) for row in rows}

    def stats(self) -> LibraryStats:
        """Totals and breakdowns for the library panel."""
        with self._lock:
            totals = self._conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(file_size_bytes), 0) AS size FROM downloads"
            ).fetchone()
            by_month = self._conn.execute(
                "SELECT substr(downloaded_at, 1, 7) AS bucket, COUNT(*) AS n, "
                "COALESCE(SUM(file_size_bytes), 0) AS size FROM downloads "
                "GROUP BY bucket ORDER BY bucket DESC"
            ).fetchall()
            by_format = self._conn.execute(
                "SELECT file_format, COUNT(*) AS n, COALESCE(SUM(file_size_bytes), 0) AS size "
                "FROM downloads GROUP BY file_format ORDER BY size DESC"
            ).fetchall()
            by_uploader = self._conn.execute(
                "SELECT uploader, COUNT(*) AS n, COALESCE(SUM(file_size_bytes), 0) AS size "
                "FROM downloads GROUP BY uploader ORDER BY size DESC"
            ).fetchall()
        return {
            "count": int(totals["n"]),
            "total_bytes": int(totals["size"]),
            "by_month": [(row["bucket"], int(row["n"]), int(row["size"])) for row in by_month],
            "by_format": [
                (row["file_format"], int(row["n"]), int(row["size"])) for row in by_format
            ],
            "by_uploader": [
                (row["uploader"], int(row["n"]), int(row["size"])) for row in by_uploader
            ],
        }

    def missing_downloads(self) -> list[HistoryEntry]:
        """History rows whose file is gone or was never recorded."""
        missing: list[HistoryEntry] = []
        for entry in self.history():
            if not entry.output_path or not Path(entry.output_path).is_file():
                missing.append(entry)
        return missing

    # -- pending queue ----------------------------------------------------

    def replace_queue(self, payloads: list[str]) -> None:
        """Replace the pending queue in one transaction."""
        with self._lock:
            self._conn.execute("DELETE FROM queue")
            self._conn.executemany(
                "INSERT INTO queue (url, position, payload) VALUES (?, ?, ?)",
                [(json.loads(p).get("url", ""), i, p) for i, p in enumerate(payloads)],
            )
            self._conn.commit()

    def queue_payloads(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM queue ORDER BY position, id").fetchall()
        return [row["payload"] for row in rows]

    # -- subscriptions (used by the subscription library) -----------------

    def add_subscription(self, url: str, title: str, kind: str) -> bool:
        """Insert a subscription. Returns False when it already exists."""
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO subscriptions (url, title, kind, added_at) VALUES (?, ?, ?, ?)",
                    (url, title, kind, datetime.now().astimezone().isoformat()),
                )
            except sqlite3.IntegrityError:
                return False
            self._conn.commit()
            return True

    def subscriptions(self) -> list[dict[str, str | None]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT url, title, kind, added_at, last_checked FROM subscriptions ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def remove_subscription(self, url: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM subscriptions WHERE url = ?", (url,))
            self._conn.commit()

    def mark_subscription_checked(self, url: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE subscriptions SET last_checked = ? WHERE url = ?",
                (datetime.now().astimezone().isoformat(), url),
            )
            self._conn.commit()

    # -- migration -------------------------------------------------------

    def import_history_json(self, path: Path) -> int:
        """Import a legacy ``history.json`` once. Returns how many rows landed."""
        if not path.exists() or self.count_history() > 0:
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise TypeError("expected a JSON array")
            entries = [HistoryEntry.from_dict(item) for item in data if isinstance(item, dict)]
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Could not import %s: %s", path, exc)
            return 0
        for entry in reversed(entries):  # oldest first, so ids keep the order
            self.add_history(entry)
        return len(entries)

    def import_queue_json(self, path: Path) -> int:
        """Import a legacy ``queue.json`` once, when the table is empty."""
        if not path.exists() or self.queue_payloads():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise TypeError("expected a JSON array")
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Could not import the legacy queue %s: %s", path, exc)
            return 0
        payloads = [json.dumps(item) for item in data if isinstance(item, dict)]
        self.replace_queue(payloads)
        return len(payloads)

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            title=row["title"],
            url=row["url"],
            uploader=row["uploader"],
            file_format=row["file_format"],
            output_path=row["output_path"],
            downloaded_at=row["downloaded_at"],
            duration=row["duration"],
            thumbnail=row["thumbnail"],
            file_size_bytes=row["file_size_bytes"],
        )
