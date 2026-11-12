"""Worker thread that performs a single download at a time."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video
from youmudow.services.download_events import DownloadEvent, DownloadEventType, DownloadProgress

logger = logging.getLogger(__name__)


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

            if self._shutdown.is_set():
                with self._video_lock:
                    self._current_video = None
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
                    unexpected_status = video.status
                    video.status = DownloadStatus.ERROR
                    if not video.error_message:
                        video.error_message = (
                            f"Download ended with unexpected status: {unexpected_status}"
                        )
                event_type = DownloadEventType.ERROR

            # Deliver the terminal event before the worker is reported idle. If
            # _current_video were cleared first, the dispatcher could dispatch a
            # new video to this worker and overwrite its _active_downloads entry
            # before the terminal event is applied, silently dropping it and
            # leaving a phantom active download in the UI.
            self._progress_callback(DownloadEvent(type=event_type, video=video))
            with self._video_lock:
                self._current_video = None
