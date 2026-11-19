"""Main window for YouMuDow.

Tkinter-based GUI layer with modern dark theme.
All business logic is delegated to the controller. Menu construction, startup
checks, file actions and settings persistence live in sibling modules; this
class composes them and wires the controller/state callbacks.
"""

import copy
import logging
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from youmudow import __version__
from youmudow.app.config import AppConfig
from youmudow.app.events import EventBus, EventType, get_event_bus
from youmudow.app.state import AppMode, AppState, AppStateData
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video
from youmudow.domain.validators import is_playlist_url, is_supported_url
from youmudow.i18n import t
from youmudow.paths import cache_dir
from youmudow.services.app_update_service import check_for_update
from youmudow.services.thumbnail_cache import ThumbnailCache
from youmudow.services.thumbnail_loader import ThumbnailLoader
from youmudow.services.thumbnail_service import ThumbnailService
from youmudow.ui.actions import choose_output_folder, export_logs, open_output_folder
from youmudow.ui.dnd import create_root, register_drop_target
from youmudow.ui.menubar import MenuCallbacks, create_menubar
from youmudow.ui.protocols import (
    AppControllerProtocol,
    DetailPanelLike,
    HistoryPanelLike,
    MainWindowProtocol,
    ResultsCardsWriter,
    SearchBarLike,
    StatusBarLike,
)
from youmudow.ui.startup_checks import (
    check_clipboard,
    check_ytdlp,
    install_ytdlp_update,
    repair_environment,
    show_about,
    show_ytdlp_version,
)
from youmudow.ui.styles.constants import FONT, SPACING, _c
from youmudow.ui.styles.styles import apply_theme
from youmudow.ui.styles.theme import ThemeName, get_theme_manager
from youmudow.ui.styles.theme_apply import apply_theme_colors
from youmudow.ui.tray import TrayIcon
from youmudow.ui.typed import readonly_property
from youmudow.ui.widgets.detail_panel import DetailPanel
from youmudow.ui.widgets.guide_panel import GuidePanel
from youmudow.ui.widgets.history_panel import HistoryPanel
from youmudow.ui.widgets.library_panel import LibraryPanel
from youmudow.ui.widgets.log_terminal import LogTerminal
from youmudow.ui.widgets.results_cards import ResultsCards
from youmudow.ui.widgets.search_bar import SearchBar
from youmudow.ui.widgets.status_bar import StatusBar
from youmudow.ui.window_settings import apply_settings, save_settings

if TYPE_CHECKING:
    from youmudow.app.controller import AppController

logger = logging.getLogger(__name__)


class MainWindow(MainWindowProtocol):
    def __init__(
        self,
        controller: "AppController",
        debug_mode: bool = True,
        config: Any = None,
        run_startup_checks: bool = True,
        restored_count: int = 0,
    ) -> None:
        self._config = config
        self._controller_impl: AppControllerProtocol = controller
        self._tk_root = create_root()
        self._tk_root.title(f"YouMuDow v{__version__}")
        self._tk_root.withdraw()
        self._tk_root.minsize(800, 600)
        saved_theme = self._config.get("theme", "dark") if self._config else "dark"
        theme: ThemeName = "light" if saved_theme == "light" else "dark"
        self._theme_manager = get_theme_manager()
        self._theme_manager.set_theme(theme)
        apply_theme(self._tk_root, self._theme_manager.colors)
        self._tk_root.configure(bg=_c("bg"))

        self._restored_count = restored_count
        self._tray: TrayIcon | None = None
        self._selected_video_impl: Video | None = None
        self._is_searching = False
        self._playlist_url = ""
        self._playlist_loaded: list[Video] = []
        self._playlist_has_more_impl = False
        self._playlist_page_size = 50
        self._guide_panel: GuidePanel | None = None
        self._guide_tab: tk.Frame | None = None
        self._is_downloading = False
        self._debug_mode = debug_mode
        self._debug_panel_visible = False
        self._event_bus: EventBus | None = None
        self._log_unsubscribe: Callable | None = None
        self._clear_unsubscribe: Callable | None = None

        self._log_terminal: LogTerminal | None = None
        self._log_frame: tk.Frame | None = None
        self._paned_window: ttk.PanedWindow | None = None
        self._main_content_frame_impl: tk.Frame | None = None
        self._menubar: tk.Menu | None = None
        self._notebook_widget: ttk.Notebook | None = None
        self._search_bar_impl: SearchBar | None = None
        self._results_cards_impl: ResultsCardsWriter | None = None
        self._detail_panel_widget: DetailPanel | None = None
        self._status_bar_impl: StatusBar | None = None
        self._history_panel_impl: HistoryPanel | None = None
        self._library_panel_impl: LibraryPanel | None = None
        self._thumbnail_loader: ThumbnailLoader | None = None
        self._thumbnail_cache: ThumbnailCache | None = None

        self._setup_ui()
        self._apply_config()
        self._setup_event_listeners()
        self._setup_controller_callbacks()
        self._setup_state_observer()
        if run_startup_checks:
            self._tk_root.after(500, self._check_clipboard_on_start)
            self._tk_root.after(3000, self._check_ytdlp_on_start)
            self._tk_root.after(4000, self._check_updates_on_start)
        try:
            from youmudow.ui.icon import get_icon_image

            icon = get_icon_image()
            if icon:
                self._tk_root.iconphoto(True, icon)
        except (ImportError, OSError, tk.TclError, ValueError) as e:
            logger.debug("Could not set window icon: %s", e)
        self._tk_root.deiconify()
        if self._restored_count:
            self._set_status(t("Restored {count} download(s)", count=self._restored_count))

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    _root: readonly_property[tk.Tk] = readonly_property("_tk_root")
    _controller: readonly_property[AppControllerProtocol] = readonly_property("_controller_impl")
    _search_bar: readonly_property[SearchBarLike | None] = readonly_property("_search_bar_impl")
    _results_cards: readonly_property[ResultsCardsWriter | None] = readonly_property(
        "_results_cards_impl"
    )
    _status_bar: readonly_property[StatusBarLike | None] = readonly_property("_status_bar_impl")
    _history_panel: readonly_property[HistoryPanelLike | None] = readonly_property(
        "_history_panel_impl"
    )
    _library_panel: readonly_property[LibraryPanel | None] = readonly_property(
        "_library_panel_impl"
    )
    _main_content_frame: readonly_property[tk.Frame | None] = readonly_property(
        "_main_content_frame_impl"
    )
    _detail_panel: readonly_property[DetailPanelLike | None] = readonly_property(
        "_detail_panel_widget"
    )

    @property
    def _selected_video(self) -> Video | None:
        return self._selected_video_impl

    @_selected_video.setter
    def _selected_video(self, video: Video | None) -> None:
        self._selected_video_impl = video

    @property
    def _notebook(self) -> ttk.Notebook:
        notebook = self._notebook_widget
        if notebook is None:
            raise RuntimeError("notebook is not built yet")
        return notebook

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self._tk_root.columnconfigure(0, weight=1)
        self._tk_root.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self._tk_root, style="Modern.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self._notebook_widget = notebook

        self._main_tab = tk.Frame(notebook, bg=_c("bg"))
        notebook.add(self._main_tab, text="  Search  ")

        self._history_tab = tk.Frame(notebook, bg=_c("bg"))
        notebook.add(self._history_tab, text="  History  ")

        self._library_tab = tk.Frame(notebook, bg=_c("bg"))
        notebook.add(self._library_tab, text="  Library  ")

        self._main_tab.columnconfigure(0, weight=1)
        self._main_tab.rowconfigure(0, weight=1)

        self._paned_window = ttk.PanedWindow(self._main_tab, orient=tk.VERTICAL)
        self._paned_window.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self._create_main_content()
        self._create_log_panel()
        self._create_menu()

        self._history_panel_impl = HistoryPanel(self._history_tab, self)
        self._history_panel_impl.pack(fill="both", expand=True)

        self._library_panel_impl = LibraryPanel(
            self._library_tab,
            stats_provider=self._controller.library_stats,
            on_check=self._on_check_library,
            on_requeue=self._on_requeue_missing,
            on_open_folder=self._on_open_folder,
        )
        self._library_panel_impl.pack(fill="both", expand=True)

        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._tk_root.bind("<F1>", lambda _event: self._open_guide_tab())

        self._update_debug_visibility()

    def _create_main_content(self) -> None:
        paned_window = self._paned_window
        if paned_window is None:
            return
        main_frame = tk.Frame(paned_window, bg=_c("bg"))
        self._main_content_frame_impl = main_frame
        paned_window.add(main_frame, weight=3)

        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)

        self._search_bar_impl = SearchBar(main_frame, self)
        self._thumbnail_cache = ThumbnailCache(cache_dir())
        self._formats_after_id: str | None = None
        self._thumbnail_loader = ThumbnailLoader(
            self._tk_root, self._thumbnail_cache, ThumbnailService()
        )
        self._results_cards_impl = ResultsCards(
            main_frame,
            self._controller.state,
            self._thumbnail_loader,
            on_select=self._on_result_select,
            on_double_click=self._on_download_now,
            on_open_in_browser=self._on_open_in_browser,
        )
        self._detail_panel_widget = DetailPanel(
            main_frame, self, thumbnail_loader=self._thumbnail_loader
        )
        self._status_bar_impl = StatusBar(self._main_tab, self)

        history = self._config.get_search_history() if self._config else []
        if history:
            self._search_bar_impl.update_history(history)

    def _create_log_panel(self) -> None:
        self._log_frame = tk.Frame(self._paned_window, bg=_c("bg"))
        label = tk.Label(
            self._log_frame,
            text="  OUTPUT",
            bg=_c("bg"),
            fg=_c("text_secondary"),
            font=FONT["label"],
            anchor="w",
        )
        label.pack(fill="x", pady=(SPACING["sm"], SPACING["xs"]))
        log_container = tk.Frame(self._log_frame, bg=_c("bg"))
        log_container.pack(fill="both", expand=True, padx=SPACING["sm"], pady=(0, SPACING["sm"]))
        self._log_terminal = LogTerminal(log_container)
        self._log_terminal.pack(fill="both", expand=True)

    def _create_menu(self) -> None:
        self._debug_var = tk.BooleanVar(value=self._debug_mode)
        tray_enabled = bool(self._config.get("minimize_to_tray", False)) if self._config else False
        self._tray_var = tk.BooleanVar(value=tray_enabled)
        language = self._config.get_str("language", "auto") if self._config else "auto"
        self._language_var = tk.StringVar(value=language)
        self._update_url: str | None = None
        callbacks = MenuCallbacks(
            set_output=self._on_set_output,
            open_output_folder=self._on_open_folder,
            export_logs=self._on_export_logs,
            import_urls=self._on_import_urls,
            clear_thumbnail_cache=self._on_clear_thumbnail_cache,
            close=self._on_close,
            quit=self._on_quit,
            start_queue=self._on_start_queue,
            clear_queue=self._on_clear_queue,
            toggle_debug=self._on_toggle_debug,
            open_guide=self._open_guide_tab,
            toggle_theme=self._on_toggle_theme,
            toggle_tray=self._on_toggle_tray,
            update_ytdlp=self._on_update_ytdlp,
            repair_youtube=self._on_repair_youtube,
            show_ytdlp_version=self._on_show_ytdlp_version,
            export_diagnostics=self._on_export_diagnostics,
            download_update=self._on_download_update,
            set_language=self._on_set_language,
            about=self._on_about,
        )
        self._menubar = create_menubar(
            self._tk_root, callbacks, self._debug_var, self._tray_var, self._language_var
        )

    def _on_set_language(self, code: str) -> None:
        if self._config is None:
            return
        self._config.set("language", code)
        self._config.save()
        self._set_status(t("Restart to apply"))

    def _on_download_update(self) -> None:
        if self._update_url:
            webbrowser.open(self._update_url)

    def _on_update_available(self, info: object) -> None:
        version = getattr(info, "version", "")
        self._update_url = getattr(info, "url", None)
        self._set_status(t("Update {version} available", version=version))

    def _check_updates_on_start(self) -> None:
        if self._config is None or not self._config.get("check_for_updates", True):
            return

        def worker() -> None:
            info = check_for_update(__version__)
            if info is not None:
                self._schedule(self._on_update_available, info)

        threading.Thread(target=worker, name="update-check", daemon=True).start()

    def _update_debug_visibility(self) -> None:
        paned_window = self._paned_window
        log_frame = self._log_frame
        log_terminal = self._log_terminal
        if paned_window is None or log_frame is None or log_terminal is None:
            return
        if self._debug_mode and not self._debug_panel_visible:
            paned_window.add(log_frame, weight=1)
            self._debug_panel_visible = True
            log_terminal.append("YouMuDow initialized", level="info")
        elif not self._debug_mode and self._debug_panel_visible:
            paned_window.forget(log_frame)
            self._debug_panel_visible = False

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _setup_event_listeners(self) -> None:
        self._event_bus = get_event_bus()

        def on_log(event) -> None:
            if self._log_terminal:
                self._schedule(
                    self._log_terminal.append,
                    event.message,
                    event.level,
                    event.timestamp,
                )

        def on_clear(event) -> None:
            if self._log_terminal:
                self._schedule(self._log_terminal.clear)

        self._log_unsubscribe = self._event_bus.subscribe(EventType.LOG_OUTPUT, on_log)
        self._clear_unsubscribe = self._event_bus.subscribe(EventType.LOG_CLEAR, on_clear)

        self._bind_shortcuts()
        self._dnd_enabled = register_drop_target(self._tk_root, self._accept_dropped_urls)

    def _bind_shortcuts(self) -> None:
        detail_panel = self._detail_panel_widget
        search_bar = self._search_bar
        self._tk_root.bind("<Control-d>", lambda _: self._on_download_now())
        self._tk_root.bind(
            "<Control-q>", lambda _: detail_panel.enqueue_selected() if detail_panel else None
        )
        self._tk_root.bind(
            "<Control-l>", lambda _: search_bar.search_entry.focus_set() if search_bar else None
        )
        self._tk_root.bind(
            "<Control-n>", lambda _: search_bar.search_entry.clear() if search_bar else None
        )
        self._tk_root.bind("<Escape>", lambda _: self._on_cancel_search())
        self._tk_root.bind("<Control-o>", lambda _: self._on_open_folder())
        self._tk_root.bind(
            "<Control-Shift-C>",
            lambda _: self._log_terminal.clear() if self._log_terminal else None,
        )
        self._tk_root.bind("<Control-t>", lambda _: self._on_toggle_theme())
        self._tk_root.bind("<Control-Shift-s>", lambda _: self._on_start_queue())

    def _setup_controller_callbacks(self) -> None:
        def on_search_complete(results: list[Video]) -> None:
            self._schedule(self._on_search_complete, results)

        def on_download_complete(video: Video) -> None:
            self._schedule(self._on_download_complete, video)

        def on_formats_ready(video: Video, size_bytes: int | None) -> None:
            self._schedule(self._on_formats_ready, video, size_bytes)

        self._controller.on_search_complete(on_search_complete)
        self._controller.on_download_complete(on_download_complete)
        self._controller.on_formats_ready(on_formats_ready)

    def _on_search_complete(self, results: list[Video]) -> None:
        try:
            self._is_searching = False
            results_cards = self._results_cards
            detail_panel = self._detail_panel_widget
            if results_cards is None:
                return
            results_cards.update_results(results)
            if results:
                self._selected_video_impl = results[0]
                if detail_panel is not None:
                    detail_panel.update_detail_panel(results[0])
                results_cards.select(0, notify=False)
                results_cards.focus_set()
                self._load_formats_for(results[0])
                self._set_status(t("Found: {title}", title=results[0].title))
            else:
                self._set_status(t("No results found"))
            self._update_button_states()
        except Exception as e:
            logger.exception("Search handler failed")
            self._set_status(t("Error: {message}", message=e))

    def _schedule_formats(self, video: Video) -> None:
        """Coalesce rapid selections into one lookup, so arrowing down a list
        does not spawn a yt-dlp probe per keystroke."""
        if self._formats_after_id is not None:
            try:
                self._tk_root.after_cancel(self._formats_after_id)
            except tk.TclError:
                pass
        self._formats_after_id = self._tk_root.after(200, lambda: self._load_formats_for(video))

    def _load_formats_for(self, video: Video) -> None:
        self._formats_after_id = None
        self._controller.load_formats(video)

    def _on_formats_ready(self, video: Video, size_bytes: int | None) -> None:
        if video is not self._selected_video:
            return
        detail_panel = self._detail_panel_widget
        if detail_panel is not None:
            detail_panel.set_estimate(size_bytes)

    def _on_download_complete(self, video: Video) -> None:
        if video.status is DownloadStatus.ERROR:
            reason = video.error_message or "Download failed"
            self._set_status(t("Error: {title} — {reason}", title=video.title, reason=reason))
        else:
            self._set_status(t("Downloaded: {title}", title=video.title))
        self._update_button_states()

    def _setup_state_observer(self) -> None:
        def on_state_change(snapshot: AppStateData) -> None:
            self._schedule(self._update_from_snapshot, snapshot)

        self._controller.state.on_change(on_state_change)

    def _update_from_snapshot(self, snapshot: AppStateData) -> None:
        try:
            self._apply_snapshot(snapshot)
        except Exception:
            logger.exception("Failed to apply state snapshot")

    def _apply_snapshot(self, snapshot: AppStateData) -> None:
        self._is_downloading = snapshot.state is AppState.DOWNLOADING
        status_bar = self._status_bar
        detail_panel = self._detail_panel_widget

        if snapshot.state is AppState.SEARCHING:
            self._is_searching = True
            self._set_status(t("Searching..."))
        elif snapshot.state is AppState.DOWNLOADING:
            self._is_searching = False
            if snapshot.active_downloads:
                active = snapshot.active_downloads[0]
                if status_bar is not None:
                    status_bar.progress_var.set(active.progress)
                speed_info = (
                    f" · {active.speed}"
                    if active.speed and active.speed != "Calculating..."
                    else ""
                )
                eta_info = f" · ETA {active.eta}" if active.eta and active.eta != "00:00" else ""
                self._set_status(
                    t(
                        "Downloading: {percent}",
                        percent=f"{active.progress:.1f}%{speed_info}{eta_info}",
                    )
                )
                if status_bar is not None:
                    status_bar.set_progress_color(_c("primary"))
            else:
                if status_bar is not None:
                    status_bar.progress_var.set(0)
                    status_bar.set_progress_color(_c("primary"))
                self._set_status(t("Downloading..."))
        elif snapshot.state is AppState.ERROR:
            search_failed = self._is_searching
            self._is_searching = False
            self._is_downloading = False
            if search_failed:
                results_cards = self._results_cards
                if results_cards is not None:
                    results_cards.clear_results()
            self._set_status(
                t("Error: {message}", message=snapshot.error_message)
                if snapshot.error_message
                else t("Error occurred")
            )
            if status_bar is not None:
                status_bar.progress_var.set(0)
                status_bar.set_progress_color(_c("error"))
        else:
            self._is_searching = False
            self._is_downloading = False
            self._set_status(t("Ready") if snapshot.state is AppState.IDLE else snapshot.state.name)
            if not snapshot.active_downloads and status_bar is not None:
                status_bar.progress_var.set(0)
                status_bar.set_progress_color(_c("border"))

        self._update_button_states()
        if detail_panel is not None and detail_panel.queue_panel_visible:
            detail_panel.update_queue(snapshot)
        if status_bar is not None:
            self._tk_root.after(50, status_bar.update_progress_bar)

        mode_is_debug = snapshot.mode is AppMode.DEBUG
        if mode_is_debug != self._debug_mode:
            self._debug_mode = mode_is_debug
            self._debug_var.set(mode_is_debug)
            self._update_debug_visibility()

    def _set_status(self, message: str) -> None:
        status_bar = self._status_bar
        if status_bar is not None:
            status_bar.set_status(message)

    def _update_button_states(self) -> None:
        search_bar = self._search_bar
        detail_panel = self._detail_panel_widget
        if search_bar is not None:
            search_bar.update_button_states(self._is_searching, self._is_downloading)
        if detail_panel is not None:
            detail_panel.update_button_states(self._is_searching, self._is_downloading)

    def _on_result_select(self) -> None:
        results_cards = self._results_cards
        if results_cards is None:
            return
        selected = results_cards.get_selected_videos()
        if selected:
            self._selected_video_impl = selected[0]
            detail_panel = self._detail_panel_widget
            if detail_panel is not None:
                detail_panel.update_detail_panel(selected[0])
            self._schedule_formats(selected[0])
            self._set_status(t("{count} selected", count=len(selected)))
        else:
            self._selected_video_impl = None
        self._update_button_states()

    def _accept_dropped_urls(self, urls: list[str]) -> None:
        search_bar = self._search_bar
        if not urls or search_bar is None:
            self._set_status(t("Drop a supported link to search it"))
            return
        search_bar.search_var.set(urls[0])
        self._on_search()

    def _on_check_library(self) -> list[str]:
        missing = self._controller.missing_downloads()
        self._set_status(t("Missing files: {count}", count=len(missing)))
        return [entry.title for entry in missing]

    def _on_requeue_missing(self) -> int:
        added = self._controller.requeue_missing()
        self._set_status(t("Queued {count} missing download(s)", count=added))
        self._update_button_states()
        return added

    def _import_urls_text(self, text: str) -> int:
        from youmudow.domain.url_batch import parse_url_list

        urls = parse_url_list(text)
        added = self._controller.enqueue_urls(urls)
        self._set_status(t("Added {count} link(s) to the queue", count=added))
        self._update_button_states()
        return added

    def _on_import_urls(self) -> None:
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            title=t("Import URLs"),
            filetypes=[(t("Text files"), "*.txt *.csv"), (t("All files"), "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as exc:
            self._set_status(t("Could not read the list: {message}", message=exc))
            return
        self._import_urls_text(text)

    def _on_open_in_browser(self, url: str) -> None:
        webbrowser.open(url)

    def _open_guide_tab(self) -> None:
        notebook = self._notebook
        if self._guide_tab is not None:
            notebook.select(self._guide_tab)
            return
        tab = tk.Frame(notebook, bg=_c("bg"))
        panel = GuidePanel(tab, on_close=self._close_guide_tab)
        panel.pack(fill="both", expand=True)
        notebook.add(tab, text="  Guide  ")
        notebook.select(tab)
        self._guide_tab = tab
        self._guide_panel = panel

    def _close_guide_tab(self) -> None:
        tab = self._guide_tab
        if tab is None:
            return
        try:
            self._notebook.forget(tab)
        except tk.TclError:
            pass
        tab.destroy()
        self._guide_tab = None
        self._guide_panel = None

    def _on_tab_changed(self, event: tk.Event | None = None) -> None:
        notebook = getattr(self, "_notebook", None)
        if notebook is None:
            return
        current = notebook.index(notebook.select())
        history_panel = self._history_panel
        if current == 1 and history_panel is not None:
            history_panel.refresh()
        library_panel = self._library_panel
        if current == 2 and library_panel is not None:
            library_panel.refresh()

    # ------------------------------------------------------------------
    # Search flow
    # ------------------------------------------------------------------

    def _on_search(self) -> None:
        search_bar = self._search_bar
        results_cards = self._results_cards
        if search_bar is None or results_cards is None:
            return
        query = search_bar.get_query()
        if not query or self._is_searching:
            return

        self._is_searching = True
        self._set_status(t("Searching..."))
        self._update_button_states()
        results_cards.is_playlist = False
        results_cards.playlist_videos = []
        results_cards.clear_results()
        self._playlist_url = ""
        self._playlist_loaded = []
        self._playlist_has_more_impl = False

        if self._config:
            self._config.add_search(query)
            search_bar.update_history(self._config.get_search_history())

        if is_supported_url(query):
            if is_playlist_url(query):
                results_cards.is_playlist = True
                self._handle_playlist_input(query)
            else:
                self._handle_url_input(query)
        else:
            results_cards.show_loading()
            self._controller.search(query)

    def _handle_url_input(self, url: str) -> None:
        self._set_status(t("Fetching video info..."))
        self._controller.search_url(url)

    def _on_cancel_download(self) -> None:
        self._controller.stop_downloads()
        self._is_downloading = False
        self._set_status(t("Downloads stopped"))
        self._update_button_states()

    def _on_cancel_search(self) -> None:
        self._controller.cancel_search()
        self._is_searching = False
        self._set_status(t("Search cancelled"))
        self._update_button_states()

    def _handle_playlist_input(self, url: str) -> None:
        self._playlist_url = url
        self._playlist_loaded = []
        self._playlist_has_more_impl = False
        self._playlist_page_size = self._config.playlist_limit if self._config else 50
        self._request_playlist_page(start=1)

    @property
    def _playlist_has_more(self) -> bool:
        return self._playlist_has_more_impl

    def _load_more_playlist(self) -> None:
        """Fetch the next page of the playlist currently on screen."""
        if not self._playlist_has_more or self._is_searching:
            return
        self._request_playlist_page(start=len(self._playlist_loaded) + 1)

    def _request_playlist_page(self, start: int) -> None:
        url = self._playlist_url
        page_size = self._playlist_page_size
        self._is_searching = True
        self._set_status("Loading more..." if start > 1 else "Fetching playlist...")
        self._update_button_states()

        def do_fetch() -> None:
            try:
                videos = self._controller.search_playlist(url, limit=page_size, start=start)
                self._schedule(self._on_playlist_page, start, videos)
            except (tk.TclError, RuntimeError):
                logger.debug("Window closed while fetching playlist for %s", url)

        thread = threading.Thread(target=do_fetch, daemon=True)
        thread.start()

    def _on_playlist_page(self, start: int, videos: list[Video]) -> None:
        if start <= 1:
            self._playlist_loaded = list(videos)
        else:
            known = {video.url for video in self._playlist_loaded}
            self._playlist_loaded.extend(v for v in videos if v.url not in known)
        # A full page means there may be more; yt-dlp gives no total upfront.
        self._playlist_has_more_impl = len(videos) == self._playlist_page_size
        self._on_playlist_complete(self._playlist_loaded)

    def _schedule(self, callback: Callable[..., Any], *args: Any) -> None:
        """Schedule a callback on the Tk main loop.

        Handles teardown races where a background thread tries to reach the
        main loop after the window has been destroyed or the loop has stopped.
        """
        try:
            self._tk_root.after(0, callback, *args)
        except (tk.TclError, RuntimeError):
            logger.debug(
                "Main window closed, dropping scheduled callback",
                exc_info=True,
            )

    def _on_playlist_complete(self, videos: list[Video]) -> None:
        results_cards = self._results_cards
        if videos:
            if results_cards is not None:
                results_cards.update_results(videos)
                results_cards.playlist_videos = videos
                results_cards.select(0, notify=False)
            self._selected_video_impl = videos[0]
            detail_panel = self._detail_panel_widget
            if detail_panel is not None:
                detail_panel.update_detail_panel(videos[0])
            self._load_formats_for(videos[0])
            self._set_status(t("Playlist: {count} videos", count=len(videos)))
        else:
            self._set_status(t("Failed to fetch playlist"))
        self._is_searching = False
        self._update_button_states()

    # ------------------------------------------------------------------
    # Startup and maintenance actions
    # ------------------------------------------------------------------

    def _check_clipboard_on_start(self) -> None:
        search_bar = self._search_bar
        if search_bar is not None:
            check_clipboard(self._tk_root, search_bar.search_var.set)

    def _check_ytdlp_on_start(self) -> None:
        check_ytdlp(self._schedule, self._set_status)

    def _on_repair_youtube(self) -> None:
        repair_environment(self._schedule, self._set_status)

    def _on_update_ytdlp(self) -> None:
        install_ytdlp_update(self._schedule, self._set_status)

    def _on_show_ytdlp_version(self) -> None:
        show_ytdlp_version(self._schedule, self._set_status)

    def _on_about(self) -> None:
        show_about(self._schedule, self._set_status)

    def _on_export_logs(self) -> None:
        if not self._log_terminal:
            return
        export_logs(self._log_terminal, self._set_status)

    def _on_clear_thumbnail_cache(self) -> None:
        """Drop the on-disk and in-memory thumbnails from the File menu."""
        cache = self._thumbnail_cache
        if cache is None:
            return
        cache.clear()
        self._set_status(t("Thumbnail cache cleared"))

    def _on_open_folder(self) -> None:
        path = self._controller.get_output_path()
        if not open_output_folder(path):
            self._set_status(t("Output: {path}", path=path))

    def _on_set_output(self) -> None:
        folder = choose_output_folder()
        if folder:
            self._controller.set_output_path(Path(folder))
            self._set_status(t("Output: {path}", path=folder))

    # ------------------------------------------------------------------
    # Downloads and queue
    # ------------------------------------------------------------------

    def _on_download_now(self) -> None:
        results_cards = self._results_cards
        detail_panel = self._detail_panel_widget
        if results_cards is None or detail_panel is None:
            return
        selected = results_cards.get_selected_videos()
        if selected:
            opts = detail_panel.get_current_options()
            if opts is None:
                return
            self._is_downloading = True
            self._update_button_states()
            for video in selected:
                video.options = copy.copy(opts)
            self._controller.enqueue_multiple(selected)
            self._controller.start_downloads()
            self._set_status(t("Downloading {count} videos...", count=len(selected)))
            return

        if results_cards.is_playlist and results_cards.playlist_videos:
            return

        target_video = self._selected_video
        if target_video is None:
            return

        self._is_downloading = True
        self._update_button_states()
        detail_panel.apply_options_to_video(target_video)
        self._controller.enqueue(target_video)
        self._controller.start_downloads()
        self._set_status(t("Downloading: {title}", title=target_video.title))

    def _on_start_queue(self) -> None:
        if self._is_downloading:
            return
        self._is_downloading = True
        self._update_button_states()
        self._controller.start_downloads()
        self._set_status(t("Starting downloads..."))

    def _on_clear_queue(self) -> None:
        self._controller.clear_queue()
        self._set_status(t("Queue cleared"))

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _on_toggle_debug(self) -> None:
        self._debug_mode = self._debug_var.get()
        self._controller.set_debug_mode(self._debug_mode)
        self._update_debug_visibility()

    def _on_toggle_theme(self) -> None:
        current = self._theme_manager.current.name
        new_theme: ThemeName = "light" if current == "dark" else "dark"
        self._theme_manager.set_theme(new_theme)
        self._apply_theme_colors()
        if self._log_terminal:
            self._log_terminal.set_dark_mode(new_theme == "dark")
        if self._config:
            self._config.set("theme", new_theme)

    def _apply_theme_colors(self) -> None:
        colors = self._theme_manager.colors
        self._tk_root.configure(bg=colors.BACKGROUND)
        apply_theme(self._tk_root, colors)
        menubar = self._menubar
        if menubar is not None:
            apply_theme_colors(menubar, colors)
        status_bar = self._status_bar
        if status_bar is not None:
            try:
                status_bar.set_progress_color(colors.PRIMARY)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # Settings and lifecycle
    # ------------------------------------------------------------------

    def _apply_config(self) -> None:
        detail_panel = self._detail_panel_widget
        if detail_panel is None:
            return
        apply_settings(self._config, detail_panel.options, self._tk_root)

    def _on_export_diagnostics(self) -> None:
        from tkinter import filedialog

        from youmudow.services.diagnostics_service import export_diagnostics

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="youmudow-diagnostics.txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        destination = Path(path)
        self._set_status(t("Writing diagnostics..."))

        def write() -> None:
            # The report shells out to yt-dlp and ffmpeg: never on the Tk thread.
            try:
                saved = export_diagnostics(destination, config=self._current_config())
            except OSError as e:
                logger.exception("Could not export diagnostics")
                self._schedule(self._set_status, f"Could not save diagnostics: {e}")
                return
            self._schedule(self._set_status, t("Diagnostics saved to {path}", path=saved))

        threading.Thread(target=write, name="diagnostics-export", daemon=True).start()

    def _on_close(self) -> None:
        self._save_settings()
        if self._should_use_tray():
            self._tk_root.withdraw()
            return
        self._shutdown()

    def _save_settings(self) -> None:
        detail_panel = self._detail_panel_widget
        if self._config and detail_panel is not None:
            try:
                output_path = self._controller.get_output_path()
            except (tk.TclError, KeyError, TypeError, ValueError) as e:
                logger.debug("Could not read output path: %s", e)
                output_path = None
            save_settings(self._config, detail_panel.options, self._tk_root, output_path)

    def _should_use_tray(self) -> bool:
        """True when closing must only hide the window and keep the queue alive."""
        if not self._config or not self._config.get("minimize_to_tray", False):
            return False
        if self._tray is None:
            self._tray = TrayIcon(
                on_show=self._show_from_tray,
                on_quit=self._quit_from_tray,
                on_start_queue=lambda: self._schedule(self._on_start_queue),
            )
        return self._tray.start()

    def _shutdown(self) -> None:
        self._save_settings()
        self._controller.stop_downloads()
        self.destroy()

    def _on_quit(self) -> None:
        """File > Exit: always leaves the application, tray or not."""
        self._shutdown()

    def _quit_from_tray(self) -> None:
        self._schedule(self._shutdown)

    def _show_from_tray(self) -> None:
        self._schedule(self._tk_root.deiconify)

    def _on_toggle_tray(self) -> None:
        if self._config is None:
            return
        enabled = bool(self._tray_var.get())
        self._config.set("minimize_to_tray", enabled)
        self._config.save()
        if enabled:
            # Show the icon now: waiting until the first close leaves the user
            # with no clue the option did anything.
            self._should_use_tray()

    def _current_config(self) -> dict[str, Any]:
        config = self._config
        if not isinstance(config, AppConfig):
            return {}
        return dict(config.snapshot())

    def run(self) -> None:
        self._tk_root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tk_root.mainloop()

    def destroy(self) -> None:
        if self._tray is not None:
            self._tray.stop()
            self._tray = None
        if self._log_unsubscribe:
            self._log_unsubscribe()
        if self._clear_unsubscribe:
            self._clear_unsubscribe()
        if self._thumbnail_loader:
            self._thumbnail_loader.shutdown()
        self._tk_root.destroy()
