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
from tkinter import ttk
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from youmudow.app.state import StateManager
    from youmudow.domain.models import Video
    from youmudow.services.history_service import HistoryService


class ResultsCardsLike(Protocol):
    """The result-card surface used by the detail panel and the window."""

    @property
    def is_playlist(self) -> bool: ...

    @property
    def playlist_videos(self) -> list[Video]: ...

    def get_selected_videos(self) -> list[Video]: ...


class SearchBarLike(Protocol):
    """The search surface used by the window and the history panel."""

    @property
    def search_var(self) -> tk.StringVar: ...


class AppControllerProtocol(Protocol):
    """The controller surface the widgets use."""

    state: StateManager
    history: HistoryService

    def enqueue(self, video: Video) -> None: ...

    def enqueue_multiple(self, videos: list[Video]) -> None: ...

    def remove_from_queue(self, video: Video) -> None: ...

    def clear_queue(self) -> None: ...

    def start_downloads(self) -> None: ...

    def stop_downloads(self) -> None: ...


@runtime_checkable
class MainWindowProtocol(Protocol):
    """The window surface the widgets use."""

    _root: tk.Misc
    _controller: AppControllerProtocol
    _selected_video: Video | None
    _results_cards: ResultsCardsLike
    _search_bar: SearchBarLike
    _notebook: ttk.Notebook
    _main_content_frame: tk.Frame

    def _on_search(self) -> None: ...

    def _on_cancel_search(self) -> None: ...

    def _on_cancel_download(self) -> None: ...

    def _on_download_now(self) -> None: ...

    def _on_open_folder(self) -> None: ...

    def _set_status(self, message: str) -> None: ...
