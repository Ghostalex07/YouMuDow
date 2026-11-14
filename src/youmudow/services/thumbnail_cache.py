"""On-disk thumbnail cache with an in-memory LRU for hot entries."""

from collections import OrderedDict
from pathlib import Path

DEFAULT_MAX_BYTES = 32 * 1024 * 1024
"""Default disk budget: 32 MiB, roughly a thousand 640x360 JPEG thumbnails."""


class ThumbnailCache:
    """Store thumbnail bytes keyed by video id, bounded by count and size.

    Bytes live on disk under ``cache_dir/<video_id>.jpg`` and, for the most
    recently used entries, in memory. Eviction drops the least recently used
    entry from both memory and disk once the entry count exceeds
    ``max_entries`` or the files on disk exceed ``max_bytes``.

    Thumbnails left behind by a previous run are measured on startup so a
    cache grown past its budget while the app was closed is trimmed, oldest
    first. Pass ``max_bytes=0`` to disable the size budget.
    """

    def __init__(
        self,
        cache_dir: Path,
        max_entries: int = 200,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ):
        self._dir = Path(cache_dir)
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._dir.mkdir(parents=True, exist_ok=True)
        self._memory: OrderedDict[str, bytes] = OrderedDict()
        self._disk: OrderedDict[str, int] = OrderedDict()
        self._disk_bytes = 0
        self._scan()
        self._evict()

    def get_path(self, video_id: str) -> Path:
        """Return the on-disk path for a video id's thumbnail."""
        return self._dir / f"{video_id}.jpg"

    def get(self, video_id: str) -> bytes | None:
        """Return cached bytes, or ``None`` on a miss."""
        if video_id in self._memory:
            self._memory.move_to_end(video_id)
            return self._memory[video_id]
        path = self.get_path(video_id)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return None
        self._memory[video_id] = data
        self._remember(video_id, len(data))
        path.touch()
        return data

    def put(self, video_id: str, data: bytes) -> None:
        """Store bytes for ``video_id``, evicting least recently used entries."""
        self.get_path(video_id).write_bytes(data)
        self._memory.pop(video_id, None)
        self._memory[video_id] = data
        self._remember(video_id, len(data))
        self._evict()

    def clear(self) -> None:
        """Drop every cached thumbnail, from memory and from disk."""
        self._memory.clear()
        self._disk.clear()
        self._disk_bytes = 0
        for path in self._dir.glob("*.jpg"):
            path.unlink(missing_ok=True)

    def _scan(self) -> None:
        """Register thumbnails left by a previous run, oldest first."""
        entries = []
        for path in self._dir.glob("*.jpg"):
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append((stat.st_mtime, path.stem, stat.st_size))
        for _, video_id, size in sorted(entries):
            self._disk[video_id] = size
            self._disk_bytes += size

    def _remember(self, video_id: str, size: int) -> None:
        """Move ``video_id`` to the young end of the disk LRU, tracking sizes."""
        previous = self._disk.pop(video_id, None)
        if previous is not None:
            self._disk_bytes -= previous
        self._disk[video_id] = size
        self._disk_bytes += size

    def _evict(self) -> None:
        while len(self._disk) > 1 and (
            len(self._disk) > self._max_entries
            or (self._max_bytes > 0 and self._disk_bytes > self._max_bytes)
        ):
            oldest, size = self._disk.popitem(last=False)
            self._disk_bytes -= size
            self._memory.pop(oldest, None)
            self.get_path(oldest).unlink(missing_ok=True)
