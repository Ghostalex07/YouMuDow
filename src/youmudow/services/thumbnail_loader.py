"""Asynchronous thumbnail loading with an on-disk cache for YouMuDow."""

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from urllib.request import urlopen

from youmudow.services.thumbnail_cache import ThumbnailCache
from youmudow.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)

_POLL_INTERVAL_MS = 30


class ThumbnailLoader:
    """Fetches video thumbnails off the UI thread and caches them.

    A single daemon worker drains requests and downloads bytes; it never
    touches Tk. Results are handed back through a thread-safe queue that a
    self-rescheduling ``after`` poller drains on the main thread, so callbacks
    always fire in the UI thread. A monotonically increasing token marks each
    request as "latest"; results whose token is no longer current are dropped,
    so a slow thumbnail for a video the user has already left cannot overwrite
    the newer selection.
    """

    def __init__(
        self,
        root: tk.Misc,
        cache: ThumbnailCache,
        service: ThumbnailService,
    ) -> None:
        self._root = root
        self._cache = cache
        self._service = service
        self._queue: queue.Queue[tuple[int, str, Callable[[str, bytes | None], None]] | None] = (
            queue.Queue()
        )
        self._results: queue.Queue[
            tuple[int, str, bytes | None, Callable[[str, bytes | None], None]]
        ] = queue.Queue()
        self._stop = threading.Event()
        self._latest = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="thumbnail-loader", daemon=True)
        self._thread.start()
        self._poll_id = self._root.after(_POLL_INTERVAL_MS, self._poll_results)

    def request(self, video_url: str, on_ready: Callable[[str, bytes | None], None]) -> None:
        with self._lock:
            self._latest += 1
            token = self._latest
        self._queue.put((token, video_url, on_ready))

    def shutdown(self) -> None:
        self._stop.set()
        try:
            self._root.after_cancel(self._poll_id)
        except (AttributeError, ValueError):
            pass
        self._queue.put(None)

    # ------------------------------------------------------------------
    # Worker thread (never touches Tk)
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            token, video_url, on_ready = item
            if self._stop.is_set() or not self._is_current(token):
                continue
            data = self._fetch(video_url)
            if self._is_current(token):
                self._results.put((token, video_url, data, on_ready))

    def _fetch(self, video_url: str) -> bytes | None:
        video_id = self._service.extract_video_id(video_url)
        if video_id:
            cached = self._cache.get(video_id)
            if cached is not None:
                return cached
            download_url = self._service.get_url(video_id)
        else:
            download_url = video_url
        try:
            data: bytes = urlopen(download_url, timeout=5).read()
        except (OSError, ValueError) as exc:
            logger.debug("Could not fetch thumbnail %s: %s", download_url, exc)
            return None
        if video_id:
            self._cache.put(video_id, data)
        return data

    def _is_current(self, token: int) -> bool:
        with self._lock:
            return token == self._latest

    # ------------------------------------------------------------------
    # Main thread: drain results
    # ------------------------------------------------------------------

    def _poll_results(self) -> None:
        while True:
            try:
                token, video_url, data, on_ready = self._results.get_nowait()
            except queue.Empty:
                break
            if self._is_current(token):
                on_ready(video_url, data)
        if not self._stop.is_set():
            self._poll_id = self._root.after(_POLL_INTERVAL_MS, self._poll_results)
