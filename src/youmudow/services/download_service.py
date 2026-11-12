"""Download service: worker pool, dispatch loop and lifecycle management."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from youmudow.adapters.ytdlp_adapter import ProgressCallback, YtdlpAdapter
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video

# Re-exported so historical imports from this module keep working; the
# implementations live in the focused modules below.
from youmudow.services.download_events import (
    DownloadEvent,
    DownloadEventType,
    DownloadProgress,
)
from youmudow.services.download_queue import (
    DownloadQueue,
    find_entry_index,
    find_video_index,
    is_same_video,
)
from youmudow.services.download_worker import DownloadWorker, _format_speed

__all__ = [
    "DownloadEvent",
    "DownloadEventType",
    "DownloadProgress",
    "DownloadQueue",
    "DownloadService",
    "DownloadWorker",
    "_format_speed",
    "find_entry_index",
    "find_video_index",
    "is_same_video",
]

logger = logging.getLogger(__name__)


class DownloadService:
    """Service for downloading videos with queue and progress tracking.

    Supports multiple concurrent downloads and detailed progress events, fully
    decoupled from the UI layer. Lifecycle is event-based: the service is
    *running* while ``_run_event`` is set; ``start()`` is idempotent and
    ``stop()`` is safe to call repeatedly and from any thread.
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
        self._on_terminal(DownloadEventType.COMPLETED, callback)

    def on_error(self, callback: Callable[[Video], None]) -> None:
        self._on_terminal(DownloadEventType.ERROR, callback)

    def on_cancelled(self, callback: Callable[[Video], None]) -> None:
        """Register a callback invoked when a worker confirms a cancellation."""
        self._on_terminal(DownloadEventType.CANCELLED, callback)

    def _on_terminal(self, event_type: DownloadEventType, emit: Callable[[Video], None]) -> None:
        """Register a callback receiving the video of one terminal event type."""

        def wrapper(event: DownloadEvent) -> None:
            if event.type == event_type:
                emit(event.video)

        with self._callbacks_lock:
            self._event_callbacks.append(wrapper)

    def clear_queue(self) -> None:
        self._queue.clear()
        self._queue_event.set()

    def add_to_queue(self, video: Video) -> None:
        if self._is_known(video):
            # A duplicate would download twice and emit two terminal events for
            # one URL; a finished download is no longer "known".
            logger.debug("Ignoring duplicate queue entry for %s", video.url)
            return
        self._queue.add(video)
        self._queue_event.set()
        self._emit_event(DownloadEvent(type=DownloadEventType.QUEUED, video=video))

    def add_multiple(self, videos: list[Video]) -> None:
        for video in videos:
            self.add_to_queue(video)

    def _is_known(self, video: Video) -> bool:
        """True when a video with the same URL is queued or active."""
        with self._lock:
            return self._queue.is_known(self._active_downloads.values(), video)

    def start(self) -> None:
        """Start the dispatch loop and spawn workers. Idempotent.

        Serialized with ``stop()`` through ``_lifecycle_lock``, so a racing
        ``start()`` either wins completely or is shut down by ``stop()``.
        """
        with self._lifecycle_lock:
            if self._run_event.is_set():
                # Already running (or a caller raced with us).
                return
            previous_thread = self._queue_thread
            if previous_thread is not None and previous_thread.is_alive():
                # Only after an abnormal stop(); avoid two queue threads.
                previous_thread.join(timeout=1.0)
            self._run_event.set()
            self._workers.clear()
            with self._lock:
                max_concurrent = self._max_concurrent
            for i in range(max_concurrent):
                worker = DownloadWorker(
                    worker_id=i,
                    adapter=self._adapter,
                    output_path_getter=self.get_output_path,
                    progress_callback=self._handle_worker_event,
                )
                self._workers.append(worker)
                worker.start()

            self._queue_thread = threading.Thread(target=self._process_queue, daemon=True)
            self._queue_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the service and wait for workers and subprocesses to finish.

        Workers are signalled to cancel and stop and joined for up to
        ``timeout`` seconds each; one that refuses to terminate is logged. No
        further download events are broadcast once stopped. Serialized with
        ``start()`` through ``_lifecycle_lock``, so a concurrent ``start()``
        cannot leave workers half-stopped or leak threads.
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
                    # A callback may call stop() from the worker's own thread.
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
            # joining; that set becomes the live one. Otherwise any leftover
            # workers are shut down so none can be orphaned.
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

        # Wake the dispatcher so it observes the stop at once.
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
        emitting one ``CANCELLED`` event. If a worker is processing it, the
        worker is signalled and removal happens on its terminal event.

        Returns True if the video was cancelled synchronously (still queued);
        False if the worker will confirm cancellation via an event.
        """
        removed = self._queue.remove(video)
        with self._lock:
            for worker in self._workers:
                if is_same_video(worker.current_video, video):
                    worker.cancel()
                    return False
        if removed is not None:
            removed.status = DownloadStatus.CANCELLED
            removed.error_message = "Cancelled by user"
            self._emit_event(DownloadEvent(type=DownloadEventType.CANCELLED, video=removed))
        return True

    def _process_queue(self) -> None:
        while self._run_event.is_set():
            if self._queue.is_empty():
                # Woken by add_to_queue/clear_queue/stop; the timeout is a net.
                self._queue_event.wait(timeout=0.1)
                self._queue_event.clear()
                continue

            with self._lock:
                idle_workers = [w for w in self._workers if not w.is_busy]
            if not idle_workers:
                # Woken when a worker finishes; the timeout is only a net.
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
            self._emit_event(DownloadEvent(type=DownloadEventType.STARTED, video=video))

    def _handle_worker_event(self, event: DownloadEvent) -> None:
        if not self._run_event.is_set():
            # Service stopped: no event from a lingering worker may reach
            # callbacks or mutate state again.
            logger.debug(
                "Ignoring %s event for %s: service stopped",
                event.type.value,
                event.video.url,
            )
            return

        if event.type == DownloadEventType.PROGRESS:
            self._emit_event(event)
            return

        with self._lock:
            found = False
            for wid, vid in list(self._active_downloads.items()):
                if vid is event.video:
                    del self._active_downloads[wid]
                    found = True
                    break

        if not found:
            # Terminal event for a video that is no longer active: a duplicate
            # broadcast or a leftover from an earlier run. Broadcasting it could
            # corrupt state (e.g. a COMPLETED for a retry of the same URL), so
            # identity matching is used and the event is dropped.
            logger.debug(
                "Ignoring %s event for %s: video is not active",
                event.type.value,
                event.video.url,
            )
            return

        # The emitting worker is free for the next dispatch: wake the queue
        # thread immediately instead of letting it poll.
        self._queue_event.set()

        if event.type == DownloadEventType.ERROR:
            self._emit_event(self._error_event(event.video))
        elif event.type in (DownloadEventType.COMPLETED, DownloadEventType.CANCELLED):
            self._emit_event(event)

    @staticmethod
    def _error_event(video: Video) -> DownloadEvent:
        """Build the canonical error event for a failed video."""
        message = video.error_message or "Download failed"
        return DownloadEvent(type=DownloadEventType.ERROR, video=video, error=message)

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

        if result_video.status == DownloadStatus.DONE:
            self._emit_event(DownloadEvent(type=DownloadEventType.COMPLETED, video=result_video))
        else:
            self._emit_event(self._error_event(result_video))

        return result_video
