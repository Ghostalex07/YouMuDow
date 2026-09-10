"""Application state management for YouMuDow.

Thread-safe state container for managing search results, download queue,
and application status.
"""

import copy
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video


class AppMode(Enum):
    """Application operation modes."""

    NORMAL = auto()
    DEBUG = auto()


class AppState(Enum):
    """Application status states."""

    IDLE = auto()
    SEARCHING = auto()
    DOWNLOADING = auto()
    ERROR = auto()


@dataclass
class AppStateData:
    """Immutable snapshot of application state."""

    search_results: list[Video]
    queue: list[Video]
    active_downloads: list[Video]
    completed_downloads: list[Video]
    state: AppState
    mode: AppMode
    error_message: str


class StateManager:
    """Thread-safe state manager for the application."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._search_results: list[Video] = []
        self._queue: list[Video] = []
        self._active_downloads: list[Video] = []
        self._completed_downloads: list[Video] = []
        self._state = AppState.IDLE
        self._mode = AppMode.NORMAL
        self._error_message = ""
        self._change_callbacks: list[Callable[[AppStateData], None]] = []
        self._last_progress_notify: float = 0.0
        self._PROGRESS_THROTTLE_S: float = 0.25

    @property
    def state(self) -> AppState:
        with self._lock:
            return self._state

    @property
    def mode(self) -> AppMode:
        with self._lock:
            return self._mode

    def get_search_results(self) -> list[Video]:
        with self._lock:
            return list(self._search_results)

    def get_queue(self) -> list[Video]:
        with self._lock:
            return list(self._queue)

    def get_completed_downloads(self) -> list[Video]:
        with self._lock:
            return list(self._completed_downloads)

    def set_state(self, state: AppState) -> None:
        with self._lock:
            self._state = state
        self._notify_change()

    def set_mode(self, mode: AppMode) -> None:
        with self._lock:
            self._mode = mode
        self._notify_change()

    def set_error(self, message: str) -> None:
        with self._lock:
            self._state = AppState.ERROR
            self._error_message = message
        self._notify_change()

    def clear_error(self) -> None:
        with self._lock:
            if self._state == AppState.ERROR:
                self._state = AppState.IDLE
            self._error_message = ""
        self._notify_change()

    def set_search_results(self, results: list[Video]) -> None:
        with self._lock:
            self._search_results = list(results)
        self._notify_change()

    def clear_search_results(self) -> None:
        with self._lock:
            self._search_results.clear()
        self._notify_change()

    def add_to_queue(self, video: Video) -> None:
        """Add a video to the queue, rejecting duplicate URLs.

        Mirrors ``DownloadService._is_known``: a URL already queued or actively
        downloading is not re-added, so the observable state stays consistent
        with the service (which would otherwise ignore the duplicate silently,
        leaving a phantom entry).
        """
        with self._lock:
            for item in self._queue:
                if item.url == video.url:
                    return
            for item in self._active_downloads:
                if item.url == video.url:
                    return
            video.status = DownloadStatus.QUEUED
            self._queue.append(video)
        self._notify_change()

    def remove_from_queue(self, video: Video) -> None:
        with self._lock:
            index = self._find_index(self._queue, video)
            if index >= 0:
                self._queue.pop(index)
        self._notify_change()

    def clear_queue(self) -> None:
        with self._lock:
            self._queue.clear()
        self._notify_change()

    def start_download(self, video: Video) -> None:
        """Move a video into the active download list.

        Safe to call with an already-active video (no duplicate entries).
        """
        with self._lock:
            queue_index = self._find_index(self._queue, video)
            active_index = self._find_index(self._active_downloads, video)
            if queue_index >= 0:
                self._queue.pop(queue_index)
            if active_index < 0:
                self._active_downloads.append(video)
            video.status = DownloadStatus.DOWNLOADING
            if self._state != AppState.DOWNLOADING:
                self._state = AppState.DOWNLOADING
        self._notify_change()

    def update_progress(
        self, video: Video, progress: float, speed: str = "", eta: str = ""
    ) -> None:
        with self._lock:
            video.progress = progress
            video.speed = speed
            video.eta = eta
        now = time.monotonic()
        if now - self._last_progress_notify >= self._PROGRESS_THROTTLE_S:
            self._last_progress_notify = now
            self._notify_change()

    def finish_download(self, video: Video) -> None:
        with self._lock:
            index = self._find_index(self._active_downloads, video)
            actual = self._active_downloads.pop(index) if index >= 0 else video
            self._completed_downloads.append(actual)
            if not self._active_downloads:
                self._state = AppState.IDLE
        self._notify_change()

    def cancel_download(self, video: Video) -> None:
        """Mark a download as cancelled and remove it from active downloads.

        Does not requeue the video; a cancelled download is a terminal state.
        """
        with self._lock:
            index = self._find_index(self._active_downloads, video)
            if index >= 0:
                active_video = self._active_downloads.pop(index)
                active_video.status = DownloadStatus.CANCELLED
            if not self._active_downloads:
                self._state = AppState.IDLE
        self._notify_change()

    def stop_all(self) -> None:
        """Cancel all active downloads and reset to IDLE."""
        with self._lock:
            for video in list(self._active_downloads):
                video.status = DownloadStatus.CANCELLED
            self._active_downloads.clear()
            self._state = AppState.IDLE
        self._notify_change()

    def on_change(self, callback: Callable[[AppStateData], None]) -> None:
        with self._lock:
            self._change_callbacks.append(callback)

    def get_snapshot(self) -> AppStateData:
        with self._lock:
            return self._snapshot()

    def reset(self) -> None:
        with self._lock:
            self._search_results.clear()
            self._queue.clear()
            self._active_downloads.clear()
            self._completed_downloads.clear()
            self._state = AppState.IDLE
            self._error_message = ""
        self._notify_change()

    @staticmethod
    def _find_index(items: list[Video], video: Video) -> int:
        """Locate a video by identity or URL inside a list."""
        for i, item in enumerate(items):
            if item is video or item.url == video.url:
                return i
        return -1

    @staticmethod
    def _copy_video(video: Video) -> Video:
        """Return an independent copy of a video for a snapshot.

        Every ``Video`` field is a value type (str/int/float/bool/path/enum);
        the only nested object is ``options``, whose fields are all value types
        too. Two shallow copies therefore produce the same isolation as
        ``copy.deepcopy`` at a fraction of the cost, which matters because a
        snapshot is built on every state change (including throttled progress
        notifications).
        """
        independent = copy.copy(video)
        if video.options is not None:
            independent.options = copy.copy(video.options)
        return independent

    def _snapshot(self) -> AppStateData:
        """Build an immutable snapshot: lists and contained videos are copies."""
        return AppStateData(
            search_results=[self._copy_video(v) for v in self._search_results],
            queue=[self._copy_video(v) for v in self._queue],
            active_downloads=[self._copy_video(v) for v in self._active_downloads],
            completed_downloads=[self._copy_video(v) for v in self._completed_downloads],
            state=self._state,
            mode=self._mode,
            error_message=self._error_message,
        )

    def _notify_change(self) -> None:
        with self._lock:
            snapshot = self._snapshot()
            callbacks = list(self._change_callbacks)
        for callback in callbacks:
            callback(snapshot)
