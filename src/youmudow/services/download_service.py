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

            if self._shutdown.is_set():
                # Service is shutting down: the terminal state is managed by
                # DownloadService.stop() itself, so no event is broadcast.
                logger.debug("Worker %s bailing during shutdown for %s", self._worker_id, video.url)
                continue

            # Explicit terminal-state mapping. COMPLETED is only emitted when the
            # adapter reported a successful download (status DONE). Any other
            # outcome (exception, cancellation, or an unexpected status) maps to
            # a distinct event; an unknown status is never silently COMPLETED.
            if video.status == DownloadStatus.DONE:
                event_type = DownloadEventType.COMPLETED
            elif video.status == DownloadStatus.CANCELLED:
                event_type = DownloadEventType.CANCELLED
            else:
                if video.status != DownloadStatus.ERROR:
                    logger.warning(
                        "Download of %s ended with unexpected status %s; treating as error",
                        video.url,
                        video.status,
                    )
                    video.status = DownloadStatus.ERROR
                    if not video.error_message:
                        video.error_message = (
                            f"Download ended with unexpected status: {video.status}"
                        )
                event_type = DownloadEventType.ERROR

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

    def remove(self, video: Video) -> Video | None:
        """Remove a video from the queue, matching by identity or URL.

        Returns the removed video, or ``None`` if it was not present. Matching
        mirrors ``StateManager._find_index`` so a deep-copied snapshot entry
        can still cancel the original.
        """
        with self._lock:
            n = len(self._queue)
            for i in range(n):
                item = self._queue[i]
                if item is video or item.url == video.url:
                    del self._queue[i]
                    return item
            return None


class DownloadService:
    """Service for downloading videos with queue and progress tracking.

    Supports multiple concurrent downloads and detailed progress events.
    Fully decoupled from UI layer.

    Lifecycle is event-based: the service is *running* while ``_run_event`` is
    set. ``start()`` is idempotent (safe to call while running, or after a
    ``stop()``), and ``stop()`` is safe to call repeatedly and from any thread.
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
        self._run_event = threading.Event()
        self._event_callbacks: list[Callable[[DownloadEvent], None]] = []
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
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
        return self._run_event.is_set()

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
        self._queue_event.set()

    def add_to_queue(self, video: Video) -> None:
        if self._is_known(video):
            # Same URL is already queued or actively downloading: duplicates
            # would double-download and emit two terminal events for one URL.
            # Nothing to do; a finished download is no longer "known".
            logger.debug("Ignoring duplicate queue entry for %s", video.url)
            return
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

    def _is_known(self, video: Video) -> bool:
        """True when a video with the same URL is queued or active."""
        with self._lock:
            for item in self._queue.peek():
                if item.url == video.url:
                    return True
            for item in self._active_downloads.values():
                if item.url == video.url:
                    return True
        return False

    def _get_output_path(self) -> Path:
        with self._lock:
            return self._output_path

    def start(self) -> None:
        """Start the dispatch loop and spawn workers. Idempotent.

        Serialized with ``stop()`` through ``_lifecycle_lock``: a ``start()``
        racing a ``stop()`` either wins completely (fresh workers, service
        running) or loses completely (the fresh workers are shut down by the
        stop), so no worker thread is ever orphaned.
        """
        with self._lifecycle_lock:
            if self._run_event.is_set():
                # Already running (or a caller raced with us): do not spawn a
                # second set of workers or a second queue thread.
                return
            previous_thread = self._queue_thread
            if previous_thread is not None and previous_thread.is_alive():
                # Only possible after an abnormal stop(); wait briefly so we do
                # not end up with two queue threads draining the same queue.
                previous_thread.join(timeout=1.0)
            self._run_event.set()
            self._workers.clear()
            with self._lock:
                max_concurrent = self._max_concurrent
            for i in range(max_concurrent):
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

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the service and wait for workers and subprocesses to finish.

        Workers are signalled to cancel and stop; each worker is joined for up
        to ``timeout`` seconds. A worker (or its subprocess) that refuses to
        terminate is reported with a clear log message instead of being hidden.
        No further download events are broadcast once the service is stopped.

        Serialized with ``start()`` through ``_lifecycle_lock``. Workers and the
        queue thread are joined while the lock is held (with bounded timeouts),
        which guarantees a concurrent ``start()`` can never leave workers in a
        half-stopped state or leak threads.
        """
        with self._lifecycle_lock:
            if not self._run_event.is_set() and not self._workers:
                return

            self._run_event.clear()
            workers = list(self._workers)

            for worker in workers:
                worker.cancel()
                worker.stop()
            for worker in workers:
                if worker is threading.current_thread():
                    # A callback running on the worker's own thread may call
                    # stop().
                    continue
                worker.join(timeout=timeout)
                if worker.is_alive():
                    logger.error(
                        "Worker %s did not terminate within %.1fs; its subprocess "
                        "may have ignored the terminate/cancel request. It can no "
                        "longer affect application state.",
                        worker.worker_id,
                        timeout,
                    )

            # A racing start() may have spawned a fresh worker set while we were
            # joining. If it did, that set becomes the live one; otherwise any
            # leftover workers are shut down so none can be orphaned.
            if self._workers and not self._run_event.is_set():
                stray = [w for w in self._workers if w not in workers]
                self._workers.clear()
                for worker in stray:
                    worker.stop()
                for worker in stray:
                    if worker is not threading.current_thread():
                        worker.join(timeout=min(timeout, 1.0))
            else:
                self._workers = [w for w in self._workers if w not in workers]

        with self._lock:
            still_active = list(self._active_downloads.values())
            self._active_downloads.clear()

        for video in still_active:
            if video.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED):
                video.status = DownloadStatus.CANCELLED
                video.error_message = "Cancelled by shutdown"

        # Wake the dispatcher so it observes the stop immediately instead of
        # finishing its current wait cycle.
        self._queue_event.set()

        queue_thread = self._queue_thread
        if queue_thread is not None and queue_thread is not threading.current_thread():
            queue_thread.join(timeout=max(0.5, min(timeout, 1.0)))
            if queue_thread.is_alive():
                logger.error(
                    "Queue thread still alive after stop(); it will exit after its "
                    "current wait cycle and cannot dispatch further downloads."
                )
        self._queue_thread = None

    def cancel_video(self, video: Video) -> bool:
        """Cancel a video.

        Removes it from the pending queue if present, marking it CANCELLED and
        emitting a single ``CANCELLED`` event. If a worker is currently
        processing it, the worker is signalled and the video is only removed
        from ``active_downloads`` once the worker emits its terminal event.

        Returns True if the video was cancelled synchronously (was still
        queued); False if the worker will confirm cancellation via an event.
        """
        removed = self._queue.remove(video)
        with self._lock:
            for worker in self._workers:
                current = worker.current_video
                if current is video or (current is not None and current.url == video.url):
                    worker.cancel()
                    return False
        if removed is not None:
            removed.status = DownloadStatus.CANCELLED
            removed.error_message = "Cancelled by user"
            self._emit_event(
                DownloadEvent(
                    type=DownloadEventType.CANCELLED,
                    video=removed,
                )
            )
        return True

    def _process_queue(self) -> None:
        while self._run_event.is_set():
            if self._queue.is_empty():
                # Woken immediately by add_to_queue/clear_queue/stop; the
                # timeout is only a safety net if a signal is missed.
                self._queue_event.wait(timeout=0.1)
                self._queue_event.clear()
                continue

            with self._lock:
                idle_workers = [w for w in self._workers if not w.is_busy]
            if not idle_workers:
                # Woken immediately when a worker finishes its current video
                # (_handle_worker_event sets the event); the timeout is only a
                # safety net, not a poll interval.
                self._queue_event.wait(timeout=0.05)
                self._queue_event.clear()
                continue

            with self._lock:
                if not self._run_event.is_set():
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
            if not self._run_event.is_set():
                # stop() ran between dispatch and the broadcast below; the
                # worker was already signalled, so do not announce a stale start.
                continue
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

        if not self._run_event.is_set():
            # The service has been stopped: no terminal (or late) event from a
            # lingering worker may reach callbacks or mutate state again.
            logger.debug(
                "Ignoring %s event for %s: service stopped",
                event.type.value,
                event.video.url,
            )
            return

        with self._lock:
            found = False
            for wid, vid in list(self._active_downloads.items()):
                if vid is event.video or vid.url == event.video.url:
                    del self._active_downloads[wid]
                    found = True
                    break

        if not found:
            # A terminal event for a video that is no longer active: either a
            # duplicate broadcast or a leftover from an earlier run (after a
            # stop/start restart). Broadcasting it could corrupt the state (e.g.
            # a COMPLETED for a fresh retry of the same URL), so drop it.
            # A same-URL collision cannot be legitimate because duplicate URLs
            # are rejected while queued/active.
            logger.debug(
                "Ignoring %s event for %s: video is not active",
                event.type.value,
                event.video.url,
            )
            return

        # The emitting worker has finished its current video, so it is free for
        # the next dispatch. Wake the queue thread immediately instead of
        # letting it poll (it also re-checks on the next add/stop signal).
        self._queue_event.set()

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
        try:
            result_video = self._adapter.download(video, output_path, progress_callback)
        except Exception as e:
            video.status = DownloadStatus.ERROR
            video.error_message = str(e)
            logger.exception("download_now failed for %s", video.url)
            result_video = video
            self._emit_event(
                DownloadEvent(
                    type=DownloadEventType.ERROR,
                    video=result_video,
                    error=result_video.error_message or "Download failed",
                )
            )
            return result_video

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
