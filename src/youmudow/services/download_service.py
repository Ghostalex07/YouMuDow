"""Download service for YouMuDow.

Handles video downloads with queue support and progress tracking.
Emits detailed progress events for integration with any UI layer.
"""

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from youmudow.adapters.ytdlp_adapter import ProgressCallback, YtdlpAdapter
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video

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
        output_path_getter: Callable[[], Path],
        progress_callback: Callable[[DownloadEvent], None],
    ) -> None:
        super().__init__(daemon=True)
        self._worker_id = worker_id
        self._adapter = adapter
        self._output_path_getter = output_path_getter
        self._progress_callback = progress_callback
        self._current_video: Video | None = None
        self._video_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._ready = threading.Event()
        self._shutdown = threading.Event()

    @property
    def worker_id(self) -> int:
        return self._worker_id

    @property
    def is_busy(self) -> bool:
        with self._video_lock:
            return self._current_video is not None

    @property
    def current_video(self) -> Video | None:
        with self._video_lock:
            return self._current_video

    def submit(self, video: Video) -> bool:
        """Assign a video to this worker.

        Returns False if the worker is already busy, in which case the caller
        must keep the video queued.
        """
        with self._video_lock:
            if self._current_video is not None:
                return False
            self._current_video = video
        self._cancel_event.clear()
        self._ready.set()
        return True

    def cancel(self) -> None:
        self._cancel_event.set()

    def stop(self) -> None:
        self._shutdown.set()
        self._ready.set()

    def _make_progress_callback(self, video: Video) -> Callable[[float, str], None]:
        def callback(progress: float, speed: str) -> None:
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

        return callback

    def run(self) -> None:
        while not self._shutdown.is_set():
            self._ready.wait()
            self._ready.clear()
            if self._shutdown.is_set():
                break

            with self._video_lock:
                video = self._current_video
            if video is None:
                continue

            progress_callback_fn = self._make_progress_callback(video)
            progress_callback_fn(0.0, "")

            try:
                self._adapter.download(
                    video,
                    self._output_path_getter(),
                    progress_callback_fn,
                    cancel_event=self._cancel_event,
                )
            except Exception as e:
                video.status = DownloadStatus.ERROR
                video.error_message = str(e)
                logger.exception("Download worker failed for %s", video.url)

            with self._video_lock:
                self._current_video = None

            if video.status == DownloadStatus.CANCELLED:
                event_type = DownloadEventType.CANCELLED
            elif video.status == DownloadStatus.ERROR:
                event_type = DownloadEventType.ERROR
            else:
                event_type = DownloadEventType.COMPLETED

            self._progress_callback(DownloadEvent(type=event_type, video=video))


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
        self._callbacks_lock = threading.Lock()
        self._active_downloads: dict[int, Video] = {}
        self._queue_event = threading.Event()
        self._queue_thread: threading.Thread | None = None

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
        with self._lock:
            return self._max_concurrent

    def set_max_concurrent(self, value: int) -> None:
        with self._lock:
            self._max_concurrent = max(1, value)

    def set_log_callback(self, callback) -> None:
        if hasattr(self._adapter, "set_log_callback"):
            self._adapter.set_log_callback(callback)

    def set_output_path(self, path: Path) -> None:
        with self._lock:
            self._output_path = path

    def get_output_path(self) -> Path:
        with self._lock:
            return self._output_path

    def on_event(self, callback: Callable[[DownloadEvent], None]) -> None:
        with self._callbacks_lock:
            self._event_callbacks.append(callback)

    def on_progress(self, callback: Callable[[DownloadProgress], None]) -> None:
        def wrapper(event: DownloadEvent) -> None:
            if event.type == DownloadEventType.PROGRESS and event.progress:
                callback(event.progress)

        with self._callbacks_lock:
            self._event_callbacks.append(wrapper)

    def on_complete(self, callback: Callable[[Video], None]) -> None:
        def wrapper(event: DownloadEvent) -> None:
            if event.type == DownloadEventType.COMPLETED:
                callback(event.video)

        with self._callbacks_lock:
            self._event_callbacks.append(wrapper)

    def on_error(self, callback: Callable[[Video], None]) -> None:
        def wrapper(event: DownloadEvent) -> None:
            if event.type == DownloadEventType.ERROR:
                callback(event.video)

        with self._callbacks_lock:
            self._event_callbacks.append(wrapper)

    def on_cancelled(self, callback: Callable[[Video], None]) -> None:
        """Register a callback invoked when a worker confirms a cancellation."""

        def wrapper(event: DownloadEvent) -> None:
            if event.type == DownloadEventType.CANCELLED:
                callback(event.video)

        with self._callbacks_lock:
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

    def _get_output_path(self) -> Path:
        with self._lock:
            return self._output_path

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        for i in range(self._max_concurrent):
            worker = DownloadWorker(
                worker_id=i,
                adapter=self._adapter,
                output_path_getter=self._get_output_path,
                progress_callback=self._handle_worker_event,
            )
            self._workers.append(worker)
            worker.start()

        self._queue_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
        )
        self._queue_thread.start()

    def stop(self) -> None:
        self._running = False
        with self._lock:
            workers = list(self._workers)
            self._workers.clear()
        for worker in workers:
            worker.cancel()
            worker.stop()
        for worker in workers:
            worker.join(timeout=5)
            if worker.is_alive():
                logger.warning("Download worker %s did not terminate within 5s", worker.worker_id)
        if self._queue_thread is not None:
            self._queue_thread.join(timeout=1.0)
            self._queue_thread = None
        with self._lock:
            for video in self._active_downloads.values():
                if video.status == DownloadStatus.DOWNLOADING:
                    video.status = DownloadStatus.CANCELLED
            self._active_downloads.clear()

    def cancel_video(self, video: Video) -> bool:
        """Cancel a video.

        Removes it from the pending queue if present. If a worker is currently
        processing it, the worker is signalled and the video is only removed
        from ``active_downloads`` once the worker emits its terminal event.

        Returns True if the video was cancelled synchronously (was still
        queued); False if the worker will confirm cancellation via an event.
        """
        self._queue.remove(video)
        with self._lock:
            for worker in self._workers:
                current = worker.current_video
                if current is video or (current is not None and current.url == video.url):
                    worker.cancel()
                    return False
        return True

    def _process_queue(self) -> None:
        while self._running:
            if self._queue.is_empty():
                self._queue_event.wait(timeout=0.1)
                self._queue_event.clear()
                continue

            with self._lock:
                idle_workers = [w for w in self._workers if not w.is_busy]
            if not idle_workers:
                self._queue_event.wait(timeout=0.05)
                self._queue_event.clear()
                continue

            with self._lock:
                if not self._running:
                    break
                worker = idle_workers[0]
                if worker not in self._workers:
                    continue
                video = self._queue.get()
                if video is None:
                    continue
                if not worker.submit(video):
                    self._queue.add(video)
                    continue
                self._active_downloads[worker.worker_id] = video
                self._emit_event(
                    DownloadEvent(
                        type=DownloadEventType.STARTED,
                        video=video,
                    )
                )

    def _handle_worker_event(self, event: DownloadEvent) -> None:
        if event.type == DownloadEventType.PROGRESS:
            self._emit_event(event)
            return

        with self._lock:
            for wid, vid in list(self._active_downloads.items()):
                if vid is event.video:
                    del self._active_downloads[wid]
                    break

        if event.type == DownloadEventType.ERROR:
            self._emit_event(
                DownloadEvent(
                    type=DownloadEventType.ERROR,
                    video=event.video,
                    error=event.video.error_message or "Download failed",
                )
            )
        elif event.type in (DownloadEventType.COMPLETED, DownloadEventType.CANCELLED):
            self._emit_event(event)

    def _emit_event(self, event: DownloadEvent) -> None:
        with self._callbacks_lock:
            callbacks = list(self._event_callbacks)
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                logger.exception("Event callback failed for %s", event.type.value)

    def download_now(
        self,
        video: Video,
        path: Path | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> Video:
        output_path = path or self._output_path
        result_video = self._adapter.download(video, output_path, progress_callback)

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
