"""Download service for YouMuDow.

Handles video downloads with queue support and progress tracking.
Emits detailed progress events for integration with any UI layer.
"""

import logging
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
from youmudow.domain.models import Video
from youmudow.domain.enums import DownloadStatus

logger = logging.getLogger(__name__)


class DownloadEventType(Enum):
    """Types of download events."""

    QUEUED = "queued"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class DownloadProgress:
    """Detailed progress information for a download."""

    video: Video | None = None
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    downloaded_bytes: str = ""
    total_bytes: str = ""
    status: DownloadStatus = DownloadStatus.READY


@dataclass
class DownloadEvent:
    """Download event with detailed information."""

    type: DownloadEventType
    video: Video
    progress: DownloadProgress | None = None
    error: str | None = None


def _format_speed(speed: str) -> str:
    if not speed:
        return "Calculating..."
    return f"{speed}/s"


class DownloadWorker(threading.Thread):
    """Worker thread for processing downloads."""

    def __init__(
        self,
        worker_id: int,
        adapter: YtdlpAdapter,
        output_path: Path,
        progress_callback: Callable[[DownloadEvent], None],
    ) -> None:
        super().__init__(daemon=True)
        self._worker_id = worker_id
        self._adapter = adapter
        self._output_path = output_path
        self._progress_callback = progress_callback
        self._current_video: Video | None = None
        self._cancel_event = threading.Event()
        self._ready = threading.Event()
        self._stop = threading.Event()

    @property
    def worker_id(self) -> int:
        return self._worker_id

    @property
    def is_busy(self) -> bool:
        return self._current_video is not None

    @property
    def current_video(self) -> Video | None:
        return self._current_video

    def submit(self, video: Video) -> None:
        self._current_video = video
        self._cancel_event.clear()
        self._ready.set()

    def cancel(self) -> None:
        self._cancel_event.set()

    def stop(self) -> None:
        self._stop.set()
        self._ready.set()

    def run(self) -> None:
        while not self._stop.is_set():
            self._ready.wait()
            self._ready.clear()
            if self._stop.is_set():
                break

            video = self._current_video
            if video is None:
                continue

            def progress_callback_fn(progress: float, speed: str) -> None:
                evt = DownloadEvent(
                    type=DownloadEventType.PROGRESS,
                    video=video,
                    progress=DownloadProgress(
                        video=video,
                        progress=progress,
                        speed=_format_speed(speed),
                        status=DownloadStatus.DOWNLOADING,
                    ),
                )
                self._progress_callback(evt)

            progress_callback_fn(0.0, "")

            try:
                self._adapter.download(
                    video, self._output_path, progress_callback_fn, cancel_event=self._cancel_event
                )
            except Exception as e:
                video.status = DownloadStatus.ERROR
                video.error_message = str(e)
                logger.exception("Download worker failed for %s", video.url)

            self._current_video = None
            self._progress_callback(
                DownloadEvent(
                    type=DownloadEventType.COMPLETED,
                    video=video,
                )
            )


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

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def remove(self, video: Video) -> None:
        with self._lock:
            try:
                self._queue.remove(video)
            except ValueError:
                pass


class DownloadService:
    """Service for downloading videos with queue and progress tracking.

    Supports multiple concurrent downloads and detailed progress events.
    Fully decoupled from UI layer.
    """

    def __init__(
        self,
        adapter: YtdlpAdapter | None = None,
        default_output_path: Path | None = None,
        max_concurrent: int = 1,
    ) -> None:
        self._adapter = adapter or YtdlpAdapter()
        self._queue = DownloadQueue()
        self._output_path = default_output_path or Path.home() / "Downloads"
        self._max_concurrent = max_concurrent
        self._workers: list[DownloadWorker] = []
        self._running = False
        self._event_callbacks: list[Callable[[DownloadEvent], None]] = []
        self._lock = threading.Lock()
        self._active_downloads: dict[int, Video] = {}
        self._queue_event = threading.Event()

    @property
    def queue_size(self) -> int:
        return self._queue.size()

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active_downloads)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def set_log_callback(self, callback) -> None:
        if hasattr(self._adapter, "set_log_callback"):
            self._adapter.set_log_callback(callback)

    def set_output_path(self, path: Path) -> None:
        self._output_path = path

    def get_output_path(self) -> Path:
        return self._output_path

    def on_event(self, callback: Callable[[DownloadEvent], None]) -> None:
        self._event_callbacks.append(callback)

    def on_progress(self, callback: Callable[[DownloadProgress], None]) -> None:
        def wrapper(event: DownloadEvent) -> None:
            if event.type == DownloadEventType.PROGRESS and event.progress:
                callback(event.progress)

        self._event_callbacks.append(wrapper)

    def on_complete(self, callback: Callable[[Video], None]) -> None:
        def wrapper(event: DownloadEvent) -> None:
            if event.type == DownloadEventType.COMPLETED:
                callback(event.video)

        self._event_callbacks.append(wrapper)

    def on_error(self, callback: Callable[[Video], None]) -> None:
        def wrapper(event: DownloadEvent) -> None:
            if event.type == DownloadEventType.ERROR:
                callback(event.video)

        self._event_callbacks.append(wrapper)

    def clear_queue(self) -> None:
        self._queue.clear()

    def add_to_queue(self, video: Video) -> None:
        self._queue.add(video)
        self._queue_event.set()
        self._emit_event(
            DownloadEvent(
                type=DownloadEventType.QUEUED,
                video=video,
            )
        )

    def add_multiple(self, videos: list[Video]) -> None:
        for video in videos:
            self.add_to_queue(video)

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        for i in range(self._max_concurrent):
            worker = DownloadWorker(
                worker_id=i,
                adapter=self._adapter,
                output_path=self._output_path,
                progress_callback=self._handle_worker_event,
            )
            self._workers.append(worker)
            worker.start()

        threading.Thread(target=self._process_queue, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        for worker in self._workers:
            worker.cancel()
            worker.stop()
        self._workers.clear()

    def cancel_video(self, video: Video) -> None:
        self._queue.remove(video)
        with self._lock:
            for worker in self._workers:
                if worker.current_video is video:
                    worker.cancel()
                    for wid, vid in list(self._active_downloads.items()):
                        if vid == video:
                            del self._active_downloads[wid]
                            break
                    break
        self._emit_event(
            DownloadEvent(
                type=DownloadEventType.CANCELLED,
                video=video,
            )
        )

    def _process_queue(self) -> None:
        while self._running:
            if self._queue.is_empty():
                self._queue_event.wait(timeout=0.1)
                self._queue_event.clear()
                continue
            with self._lock:
                idle_workers = [w for w in self._workers if not w.is_busy]
            if idle_workers:
                video = self._queue.get()
                if video:
                    worker = idle_workers[0]
                    with self._lock:
                        self._active_downloads[worker.worker_id] = video
                    worker.submit(video)
                    self._emit_event(
                        DownloadEvent(
                            type=DownloadEventType.STARTED,
                            video=video,
                        )
                    )
            else:
                self._queue_event.wait(timeout=0.05)
                self._queue_event.clear()

    def _handle_worker_event(self, event: DownloadEvent) -> None:
        if event.type == DownloadEventType.PROGRESS:
            self._emit_event(event)
        elif event.type == DownloadEventType.COMPLETED:
            with self._lock:
                video_id = None
                for wid, vid in self._active_downloads.items():
                    if vid == event.video:
                        video_id = wid
                        break
                if video_id is not None:
                    del self._active_downloads[video_id]

            if event.video.status == DownloadStatus.DONE:
                self._emit_event(
                    DownloadEvent(
                        type=DownloadEventType.COMPLETED,
                        video=event.video,
                    )
                )
            elif event.video.status == DownloadStatus.CANCELLED:
                self._emit_event(
                    DownloadEvent(
                        type=DownloadEventType.CANCELLED,
                        video=event.video,
                    )
                )
            else:
                self._emit_event(
                    DownloadEvent(
                        type=DownloadEventType.ERROR,
                        video=event.video,
                        error=event.video.error_message or "Download failed",
                    )
                )

    def _emit_event(self, event: DownloadEvent) -> None:
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception:
                logger.exception("Event callback failed for %s", event.type.value)

    def download_now(self, video: Video, path: Path | None = None) -> Video:
        output_path = path or self._output_path
        result_video = self._adapter.download(video, output_path)

        if result_video.status == DownloadStatus.DONE:
            self._emit_event(
                DownloadEvent(
                    type=DownloadEventType.COMPLETED,
                    video=result_video,
                )
            )
        else:
            self._emit_event(
                DownloadEvent(
                    type=DownloadEventType.ERROR,
                    video=result_video,
                    error=result_video.error_message or "Download failed",
                )
            )

        return result_video
