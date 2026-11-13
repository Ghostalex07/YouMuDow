"""Structural protocols describing what UI widgets may use from their host.

The widgets never import :class:`youmudow.ui.window.MainWindow` directly: that
module imports the widgets, so the dependency would be circular. Instead each
widget declares the narrow slice of the window it actually touches, and the
window satisfies those protocols structurally.

Only ``TYPE_CHECKING`` imports are used so importing this module pulls in no
widget or application code at runtime.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from youmudow.app.controller import DownloadCompleteCallback, SearchCompleteCallback
    from youmudow.app.state import StateManager
    from youmudow.domain.models import DownloadOptions, Video
    from youmudow.services.history_service import HistoryService


class ResultsCardsLike(Protocol):
    """The result-card surface used by the detail panel and the window.

    ``is_playlist`` and ``playlist_videos`` are writable in the concrete
    widget but are declared read-only here: the panel only reads them, and a
    read-only protocol member keeps the assignment covariant.
    """

    @property
    def is_playlist(self) -> bool: ...

    @property
    def playlist_videos(self) -> list[Video]: ...

    def get_selected_videos(self) -> list[Video]: ...

    def update_results(self, videos: list[Video]) -> None: ...

    def clear_results(self) -> None: ...

    def show_loading(self, message: str = "Searching...") -> None: ...

    def select(self, index: int, notify: bool = True) -> None: ...

    def focus_set(self) -> None: ...


class ResultsCardsWriter(ResultsCardsLike, Protocol):
    """The writable view of the card surface that the window drives.

    Split from :class:`ResultsCardsLike` because a protocol member with a
    setter is invariant: declaring ``is_playlist`` writable there would make
    ``ResultsCards`` (whose ``__getattr__`` mypy models as ``Any``) fail the
    protocol check. The window holds the writer view; the widgets read
    through the covariant read-only view.
    """

    @property
    def is_playlist(self) -> bool: ...

    @is_playlist.setter
    def is_playlist(self, value: bool) -> None: ...

    @property
    def playlist_videos(self) -> list[Video]: ...

    @playlist_videos.setter
    def playlist_videos(self, value: list[Video]) -> None: ...


class DetailPanelLike(Protocol):
    """The detail-panel surface used by the window and the history panel."""

    @property
    def options(self) -> OptionsPanelLike: ...

    @property
    def queue_panel_visible(self) -> bool: ...

    def update_detail_panel(self, video: Video) -> None: ...

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None: ...

    def enqueue_selected(self) -> None: ...

    def apply_options_to_video(self, video: Video) -> None: ...

    def get_current_options(self) -> DownloadOptions | None: ...


class OptionsPanelLike(Protocol):
    """The options-panel surface the window configures on startup."""

    def get_options(self) -> DownloadOptions | None: ...

    def apply_to_video(self, video: Video) -> None: ...

    def update_for_video(self, video: Video) -> None: ...

    def load_settings(self, config: Any) -> None: ...

    def save_settings(self, config: Any) -> None: ...

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None: ...


class StatusBarLike(Protocol):
    """The status-bar surface used by the window."""

    @property
    def progress_var(self) -> tk.DoubleVar: ...

    def set_status(self, message: str) -> None: ...

    def set_progress_color(self, color: str) -> None: ...

    def update_progress_bar(self) -> None: ...


class HistoryPanelLike(Protocol):
    """The history-panel surface used by the window."""

    def refresh(self) -> None: ...


class SearchEntryLike(Protocol):
    """The text-entry surface the window drives directly."""

    def get(self) -> str: ...

    def clear(self) -> None: ...

    def focus_set(self) -> None: ...


class SearchBarLike(Protocol):
    """The search surface used by the window and the history panel."""

    @property
    def search_var(self) -> tk.StringVar: ...

    @property
    def search_entry(self) -> SearchEntryLike: ...

    def get_query(self) -> str: ...

    def update_history(self, history: list[str]) -> None: ...

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None: ...


class AppControllerProtocol(Protocol):
    """The controller surface the widgets use."""

    @property
    def state(self) -> StateManager: ...

    @property
    def history(self) -> HistoryService: ...

    def enqueue(self, video: Video) -> None: ...

    def enqueue_multiple(self, videos: list[Video]) -> None: ...

    def remove_from_queue(self, video: Video) -> None: ...

    def clear_queue(self) -> None: ...

    def start_downloads(self) -> None: ...

    def stop_downloads(self) -> None: ...

    def search(self, query: str) -> None: ...

    def search_url(self, url: str) -> None: ...

    def cancel_search(self) -> None: ...

    def search_playlist(self, url: str, limit: int = 50) -> list[Video]: ...

    def get_output_path(self) -> Path: ...

    def set_output_path(self, path: Path) -> None: ...

    def set_debug_mode(self, enabled: bool) -> None: ...

    def on_search_complete(self, callback: SearchCompleteCallback) -> None: ...

    def on_download_complete(self, callback: DownloadCompleteCallback) -> None: ...


@runtime_checkable
class MainWindowProtocol(Protocol):
    """The window surface the widgets use.

    Every attribute is declared as a read-only property. Protocol attributes
    are invariant, so a mutable member would demand the exact concrete type
    (``SearchBar``) instead of accepting any implementation of the narrower
    protocol. Widgets that inherit from ``tk.Misc`` also carry a dynamic
    ``__getattr__``, which mypy models as ``Any`` and therefore never
    satisfies an invariant attribute. Read-only properties are covariant, so
    ``SearchBar`` (a ``tk.Frame``) satisfies ``SearchBarLike`` cleanly.
    """

    @property
    def _root(self) -> tk.Tk: ...

    @property
    def _controller(self) -> AppControllerProtocol: ...

    @property
    def _selected_video(self) -> Video | None: ...

    @_selected_video.setter
    def _selected_video(self, video: Video | None) -> None: ...

    @property
    def _results_cards(self) -> ResultsCardsWriter | None: ...

    @property
    def _search_bar(self) -> SearchBarLike | None: ...

    @property
    def _notebook(self) -> ttk.Notebook: ...

    @property
    def _main_content_frame(self) -> tk.Frame | None: ...

    @property
    def _detail_panel(self) -> DetailPanelLike | None: ...

    @property
    def _status_bar(self) -> StatusBarLike | None: ...

    @property
    def _history_panel(self) -> HistoryPanelLike | None: ...

    def _on_search(self) -> None: ...

    def _on_cancel_search(self) -> None: ...

    def _on_cancel_download(self) -> None: ...

    def _on_download_now(self) -> None: ...

    def _on_open_folder(self) -> None: ...

    def _set_status(self, message: str) -> None: ...
