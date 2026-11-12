"""Thread-safe download queue and video matching helpers."""

import threading
from collections import deque
from collections.abc import Iterable, Sequence

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video


def is_same_video(candidate: Video | None, video: Video) -> bool:
    """True when two entries denote the same video: the same object or the same URL."""
    return candidate is video or (candidate is not None and candidate.url == video.url)


def find_video_index(items: Sequence[Video], video: Video) -> int:
    """Locate a video by identity or URL inside a sequence."""
    for index, item in enumerate(items):
        if is_same_video(item, video):
            return index
    return -1


def find_entry_index(items: Sequence[Video], video: Video) -> int:
    """Locate a queue entry by its stable id.

    An entry that carries an id is matched by that id only: a URL fallback
    would find the *re-queued* copy of a finished video and remove the wrong
    row. Videos that never entered the queue have no id and fall back to the
    identity/URL match.
    """
    if not video.queue_id:
        return find_video_index(items, video)
    for index, item in enumerate(items):
        if item.queue_id == video.queue_id:
            return index
    return -1


class DownloadQueue:
    """Thread-safe download queue."""

    def __init__(self) -> None:
        self._queue: deque[Video] = deque()
        self._lock = threading.Lock()

    def add(self, video: Video) -> None:
        with self._lock:
            video.status = DownloadStatus.QUEUED
            self._queue.append(video)

    def get(self) -> Video | None:
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def peek(self) -> list[Video]:
        with self._lock:
            return list(self._queue)

    def has_url(self, url: str) -> bool:
        with self._lock:
            return any(item.url == url for item in self._queue)

    def is_known(self, active: Iterable[Video], video: Video) -> bool:
        """True when a video with the same URL is queued or actively downloading."""
        if self.has_url(video.url):
            return True
        return any(item.url == video.url for item in active)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def remove(self, video: Video) -> Video | None:
        """Remove a video from the queue, matching by identity or URL.

        Returns the removed video, or ``None`` if it was not present. Matching
        uses ``find_video_index`` so a deep-copied snapshot entry can still
        cancel the original.
        """
        with self._lock:
            index = find_video_index(self._queue, video)
            if index < 0:
                return None
            item = self._queue[index]
            del self._queue[index]
            return item

    def remove_entry(self, video: Video) -> bool:
        """Remove the queue entry a video stands for, matching by its queue id.

        Returns whether an entry was removed.
        """
        with self._lock:
            index = find_entry_index(self._queue, video)
            if index < 0:
                return False
            del self._queue[index]
            return True
