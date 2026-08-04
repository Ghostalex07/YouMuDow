"""Application state management for YouMuDow.

Thread-safe state container for managing search results, download queue,
and application status.
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from youmudow.domain.models import Video
from youmudow.domain.enums import DownloadStatus


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
        with self._lock:
            video.status = DownloadStatus.QUEUED
            self._queue.append(video)
        self._notify_change()

    def remove_from_queue(self, video: Video) -> None:
        with self._lock:
            if video in self._queue:
                self._queue.remove(video)
        self._notify_change()

    def clear_queue(self) -> None:
        with self._lock:
            self._queue.clear()
        self._notify_change()

    def start_download(self, video: Video) -> None:
        with self._lock:
            if video in self._queue:
                self._queue.remove(video)
            video.status = DownloadStatus.DOWNLOADING
            self._active_downloads.append(video)
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
            if video in self._active_downloads:
                self._active_downloads.remove(video)
            self._completed_downloads.append(video)
            if not self._active_downloads:
                self._state = AppState.IDLE
        self._notify_change()

    def cancel_download(self, video: Video) -> None:
        with self._lock:
            if video in self._active_downloads:
                self._active_downloads.remove(video)
                video.status = DownloadStatus.READY
                self._queue.append(video)
            if not self._active_downloads:
                self._state = AppState.IDLE
        self._notify_change()

    def on_change(self, callback: Callable[[AppStateData], None]) -> None:
        self._change_callbacks.append(callback)

    def get_snapshot(self) -> AppStateData:
        with self._lock:
            return AppStateData(
                search_results=list(self._search_results),
                queue=list(self._queue),
                active_downloads=list(self._active_downloads),
                completed_downloads=list(self._completed_downloads),
                state=self._state,
                mode=self._mode,
                error_message=self._error_message,
            )

    def reset(self) -> None:
        with self._lock:
            self._search_results.clear()
            self._queue.clear()
            self._active_downloads.clear()
            self._completed_downloads.clear()
            self._state = AppState.IDLE
            self._error_message = ""
        self._notify_change()

    def _notify_change(self) -> None:
        with self._lock:
            snapshot = AppStateData(
                search_results=list(self._search_results),
                queue=list(self._queue),
                active_downloads=list(self._active_downloads),
                completed_downloads=list(self._completed_downloads),
                state=self._state,
                mode=self._mode,
                error_message=self._error_message,
            )
            callbacks = list(self._change_callbacks)
        for callback in callbacks:
            callback(snapshot)
