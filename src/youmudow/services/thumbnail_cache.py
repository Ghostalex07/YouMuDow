"""On-disk thumbnail cache with an in-memory LRU for hot entries."""

from collections import OrderedDict
from pathlib import Path


class ThumbnailCache:
    """Store thumbnail bytes keyed by video id, bounded by ``max_entries``.

    Bytes live on disk under ``cache_dir/<video_id>.jpg`` and, for the most
    recently used entries, in memory. Eviction drops the least recently used
    entry from both memory and disk.
    """

    def __init__(self, cache_dir: Path, max_entries: int = 200):
        self._dir = Path(cache_dir)
        self._max = max_entries
        self._dir.mkdir(parents=True, exist_ok=True)
        self._memory: OrderedDict[str, bytes] = OrderedDict()

    def get_path(self, video_id: str) -> Path:
        """Return the on-disk path for a video id's thumbnail."""
        return self._dir / f"{video_id}.jpg"

    def get(self, video_id: str) -> bytes | None:
        """Return cached bytes, or ``None`` on a miss."""
        if video_id in self._memory:
            self._memory.move_to_end(video_id)
            return self._memory[video_id]
        path = self.get_path(video_id)
        if path.exists():
            data = path.read_bytes()
            self._memory[video_id] = data
            self._memory.move_to_end(video_id)
            self._evict()
            return data
        return None

    def put(self, video_id: str, data: bytes) -> None:
        """Store bytes for ``video_id``, evicting the LRU entry if needed."""
        self.get_path(video_id).write_bytes(data)
        self._memory.pop(video_id, None)
        self._memory[video_id] = data
        self._evict()

    def _evict(self) -> None:
        while len(self._memory) > self._max:
            oldest, _ = self._memory.popitem(last=False)
            oldest_path = self.get_path(oldest)
            if oldest_path.exists():
                oldest_path.unlink()

    def clear(self) -> None:
        """Drop every cached thumbnail, from memory and from disk."""
        self._memory.clear()
        for path in self._dir.glob("*.jpg"):
            path.unlink(missing_ok=True)
