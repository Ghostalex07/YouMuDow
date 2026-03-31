"""Application controller for YouMuDow.

Coordinates between UI layer and services layer.
Handles user actions and state management.
"""

import threading
from pathlib import Path
from typing import Callable, Protocol

from youmudow.domain.models import Video
from youmudow.domain.enums import DownloadStatus
from youmudow.services.search_service import SearchService
from youmudow.services.download_service import DownloadService
from youmudow.services.metadata_service import MetadataService
from youmudow.services.thumbnail_service import ThumbnailService
from youmudow.app.state import StateManager, AppState
from youmudow.app.events import get_event_bus, emit_log, clear_logs


class ControllerProtocol(Protocol):
    """Protocol defining the controller interface for UI layer."""

    def search(self, query: str) -> None: ...
    def enqueue(self, video: Video) -> None: ...
    def start_downloads(self) -> None: ...
    def stop_downloads(self) -> None: ...


class DownloadCompleteCallback(Protocol):
    """Callback for download completion."""

    def __call__(self, video: Video) -> None: ...


class SearchCompleteCallback(Protocol):
    """Callback for search completion."""

    def __call__(self, results: list[Video]) -> None: ...


class AppController:
    """Main application controller.

    Acts as intermediary between UI and services.
    Does not contain yt-dlp logic directly.
    """

    def __init__(
        self,
        search_service: SearchService | None = None,
        download_service: DownloadService | None = None,
        metadata_service: MetadataService | None = None,
        thumbnail_service: ThumbnailService | None = None,
        state_manager: StateManager | None = None,
    ) -> None:
        self._search_service = search_service or SearchService()
        self._download_service = download_service or DownloadService()
        self._metadata_service = metadata_service or MetadataService()
        self._thumbnail_service = thumbnail_service or ThumbnailService()
        self._state_manager = state_manager or StateManager()

        self._search_thread: threading.Thread | None = None
        self._download_complete_callback: DownloadCompleteCallback | None = None
        self._search_complete_callback: SearchCompleteCallback | None = None
        self._debug_mode = False

        self._setup_download_callbacks()
        self._setup_log_callback()

    @property
    def state(self) -> StateManager:
        return self._state_manager

    def set_output_path(self, path: Path) -> None:
        self._download_service.set_output_path(path)

    def on_download_complete(self, callback: DownloadCompleteCallback) -> None:
        self._download_complete_callback = callback

    def on_search_complete(self, callback: SearchCompleteCallback) -> None:
        self._search_complete_callback = callback

    def search(self, query: str) -> None:
        if not query or not query.strip():
            return

        self._state_manager.set_state(AppState.SEARCHING)
        self._state_manager.clear_search_results()

        self._search_thread = threading.Thread(
            target=self._perform_search,
            args=(query,),
            daemon=True,
        )
        self._search_thread.start()

    def _perform_search(self, query: str) -> None:
        try:
            results = self._search_service.search(query)
            
            for video in results:
                if video.thumbnail:
                    continue
                thumb_url = self._thumbnail_service.get_thumbnail_url(video.url)
                video.thumbnail = thumb_url

            self._state_manager.set_search_results(results)
            self._state_manager.set_state(AppState.IDLE)

            if self._search_complete_callback:
                self._search_complete_callback(results)

        except Exception as e:
            self._state_manager.set_error(f"Search failed: {e}")

    def search_url(self, url: str) -> Video | None:
        if not url:
            return None

        self._state_manager.set_state(AppState.SEARCHING)
        
        try:
            video = self._search_service.get_metadata(url)
            if video:
                video.thumbnail = self._thumbnail_service.get_thumbnail_url(url)
            self._state_manager.set_state(AppState.IDLE)
            return video
        except Exception as e:
            self._state_manager.set_error(f"Failed to fetch URL: {e}")
            return None

    def select_video(self, video: Video) -> dict[str, str]:
        return self._metadata_service.format_for_display(video)

    def enqueue(self, video: Video) -> None:
        self._state_manager.add_to_queue(video)

    def enqueue_multiple(self, videos: list[Video]) -> None:
        for video in videos:
            self._state_manager.add_to_queue(video)

    def remove_from_queue(self, video: Video) -> None:
        self._state_manager.remove_from_queue(video)

    def clear_queue(self) -> None:
        self._state_manager.clear_queue()

    def start_downloads(self) -> None:
        queue = self._state_manager.get_queue()
        if not queue:
            return

        for video in queue:
            self._state_manager.start_download(video)

        self._download_service.add_multiple(queue)
        self._download_service.start()

    def stop_downloads(self) -> None:
        self._download_service.stop()
        self._state_manager.set_state(AppState.IDLE)

    def download_now(self, video: Video, path: Path | None = None) -> Video:
        self._state_manager.start_download(video)
        return self._download_service.download_now(video, path)

    def cancel_download(self, video: Video) -> None:
        self._state_manager.cancel_download(video)

    def set_format(self, video: Video, fmt: str) -> None:
        video.format = fmt

    def set_debug_mode(self, enabled: bool) -> None:
        from youmudow.app.state import AppMode
        self._debug_mode = enabled
        mode = AppMode.DEBUG if enabled else AppMode.NORMAL
        self._state_manager.set_mode(mode)

    def reset(self) -> None:
        self._search_thread = None
        self._download_service.stop()
        self._download_service = DownloadService()
        self._setup_download_callbacks()
        self._state_manager.reset()

    def _setup_download_callbacks(self) -> None:
        from youmudow.services.download_service import DownloadProgress

        def on_progress(progress: DownloadProgress) -> None:
            if progress.video:
                self._state_manager.update_progress(progress.video, progress.progress)
            if self._debug_mode and progress.video:
                emit_log(f"[download] {progress.progress:.1f}% - {progress.video.title}", level="debug")

        def on_complete(video: Video) -> None:
            self._state_manager.finish_download(video)
            emit_log(f"[DONE] {video.title} - Download completed", level="success")
            if self._download_complete_callback:
                self._download_complete_callback(video)

        def on_started(video: Video) -> None:
            emit_log(f"[DOWNLOAD] Starting: {video.title}", level="info")

        self._download_service.on_progress(on_progress)
        self._download_service.on_complete(on_complete)
        self._download_service.on_event(lambda e: on_started(e.video) if e.type.name == "STARTED" else None)

    def _setup_log_callback(self) -> None:
        def on_log_message(message: str) -> None:
            level = "info"
            if "Error" in message or "error" in message.lower() or "[ERROR]" in message:
                level = "error"
            elif "warning" in message.lower() or "[WARNING]" in message:
                level = "warning"
            elif "[DONE]" in message:
                level = "success"
            elif "[download]" in message:
                level = "debug"
            emit_log(message, level)

        search_adapter = getattr(self._search_service, '_adapter', None)
        if search_adapter:
            search_adapter.set_log_callback(on_log_message)

        download_adapter = getattr(self._download_service, '_adapter', None)
        if download_adapter:
            download_adapter.set_log_callback(on_log_message)
