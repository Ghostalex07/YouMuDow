"""Download history service for YouMuDow."""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from youmudow.domain.models import HistoryEntry, Video
from youmudow.paths import config_dir

logger = logging.getLogger(__name__)

HISTORY_FILE: Path = config_dir() / "history.json"
MAX_HISTORY = 500


class HistoryService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: list[HistoryEntry] = []
        self._load()

    def _load(self) -> None:
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                self._entries = [HistoryEntry.from_dict(e) for e in data if isinstance(e, dict)]
        except (OSError, ValueError, TypeError) as e:
            logger.warning("Failed to load download history from %s: %s", HISTORY_FILE, e)
            self._entries = []

    def _save(self) -> None:
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [e.to_dict() for e in self._entries[:MAX_HISTORY]]
            HISTORY_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("Failed to save download history to %s: %s", HISTORY_FILE, e)

    def add(
        self, video: Video, output_path: str, file_format: str, file_size_bytes: int = 0
    ) -> None:
        entry = HistoryEntry(
            title=video.title,
            url=video.url,
            uploader=video.uploader or "",
            file_format=file_format,
            output_path=output_path,
            downloaded_at=datetime.now().astimezone().isoformat(),
            duration=video.duration or 0,
            thumbnail=video.thumbnail or "",
            file_size_bytes=file_size_bytes,
        )
        with self._lock:
            recent_urls = {e.url for e in self._entries[:50]}
            if entry.url not in recent_urls:
                self._entries.insert(0, entry)
                if len(self._entries) > MAX_HISTORY:
                    self._entries = self._entries[:MAX_HISTORY]
                self._save()

    def get_all(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._entries)

    def remove(self, entry: HistoryEntry) -> None:
        with self._lock:
            try:
                self._entries.remove(entry)
                self._save()
            except ValueError:
                pass

    def clear(self) -> None:
        with self._lock:
            self._entries = []
            self._save()

    def search(self, query: str) -> list[HistoryEntry]:
        q = query.lower()
        with self._lock:
            return [e for e in self._entries if q in e.title.lower() or q in e.uploader.lower()]
