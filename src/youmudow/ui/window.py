"""Main window for YouMuDow.

Tkinter-based GUI layer with modern dark theme.
All business logic is delegated to the controller.
"""

import logging
import platform
import subprocess
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any

from youmudow import __version__
from youmudow.adapters.browser_profiles import get_available_browsers
from youmudow.app.events import EventBus, EventType, get_event_bus
from youmudow.app.state import AppMode, AppState, AppStateData
from youmudow.domain.models import Video
from youmudow.domain.validators import (
    is_playlist_url,
    is_supported_url,
    is_valid_rate_limit,
)
from youmudow.services.updater_service import get_ytdlp_version, update_ytdlp
from youmudow.ui.styles.constants import _COLOR_MAP, FONT, SPACING, _c
from youmudow.ui.styles.styles import configure_styles
from youmudow.ui.styles.theme import ThemeName, get_theme_manager
from youmudow.ui.widgets.detail_panel import DetailPanel
from youmudow.ui.widgets.history_panel import HistoryPanel
from youmudow.ui.widgets.log_terminal import LogTerminal
from youmudow.ui.widgets.results_table import ResultsTable
from youmudow.ui.widgets.search_bar import SearchBar
from youmudow.ui.widgets.status_bar import StatusBar

if TYPE_CHECKING:
    from youmudow.app.controller import AppController

logger = logging.getLogger(__name__)


class MainWindow:
    def __init__(
        self, controller: "AppController", debug_mode: bool = False, config: Any = None
    ) -> None:
        self._config = config
        self._controller = controller
        self._root = tk.Tk()
        self._root.title(f"YouMuDow v{__version__}")
        self._root.withdraw()
        self._root.minsize(800, 600)
        saved_theme = self._config.get("theme", "dark") if self._config else "dark"
        self._theme_manager = get_theme_manager()
        self._theme_manager.set_theme(saved_theme)
        configure_styles(self._theme_manager.colors)
        self._root.configure(bg=_c("bg"))

        self._selected_video: Video | None = None
        self._is_searching = False
        self._is_downloading = False
        self._debug_mode = debug_mode
        self._debug_panel_visible = False
        self._event_bus: EventBus | None = None
        self._log_unsubscribe: Callable | None = None
        self._clear_unsubscribe: Callable | None = None

        self._log_terminal: LogTerminal | None = None
        self._log_frame: tk.Frame | None = None
        self._paned_window: ttk.PanedWindow | None = None
        self._main_content_frame: tk.Frame | None = None
        self._menubar: tk.Menu | None = None
        self._search_bar: SearchBar | None = None
        self._results_table: ResultsTable | None = None
        self._detail_panel: DetailPanel | None = None
        self._status_bar: StatusBar | None = None

        self._setup_ui()
        self._apply_config()
        self._setup_event_listeners()
        self._setup_controller_callbacks()
        self._setup_state_observer()
        self._root.after(500, self._check_clipboard_on_start)
        self._root.after(3000, self._check_ytdlp_on_start)
        try:
            from youmudow.ui.icon import get_icon_image

            icon = get_icon_image()
            if icon:
                self._root.iconphoto(True, icon)
        except (ImportError, OSError, tk.TclError, ValueError) as e:
            logger.debug("Could not set window icon: %s", e)
        self._root.deiconify()

    def _setup_ui(self) -> None:
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)

        self._notebook = ttk.Notebook(self._root, style="Modern.TNotebook")
        self._notebook.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        self._main_tab = tk.Frame(self._notebook, bg=_c("bg"))
        self._notebook.add(self._main_tab, text="  Search  ")

        self._history_tab = tk.Frame(self._notebook, bg=_c("bg"))
        self._notebook.add(self._history_tab, text="  History  ")

        self._main_tab.columnconfigure(0, weight=3)
        self._main_tab.columnconfigure(1, weight=2)
        self._main_tab.rowconfigure(1, weight=1)
        self._main_tab.rowconfigure(2, weight=0)

        self._paned_window = ttk.PanedWindow(self._main_tab, orient=tk.VERTICAL)
        self._paned_window.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self._create_main_content()
        self._create_log_panel()
        self._create_menu()

        self._history_panel = HistoryPanel(self._history_tab, self)
        self._history_panel.pack(fill="both", expand=True)

        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._update_debug_visibility()

    def _create_main_content(self) -> None:
        main_frame = tk.Frame(self._paned_window, bg=_c("bg"))
        self._main_content_frame = main_frame
        self._paned_window.add(main_frame, weight=3)

        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)

        self._search_bar = SearchBar(main_frame, self)
        self._results_table = ResultsTable(main_frame, self)
        self._detail_panel = DetailPanel(main_frame, self)
        self._status_bar = StatusBar(self._main_tab, self)

        history = self._config.get_search_history() if self._config else []
        if history:
            self._search_bar.update_history(history)

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
        self._menubar = tk.Menu(self._root, bg=_c("bg"), fg=_c("text"), bd=0, relief="flat")
        self._root.configure(menu=self._menubar)

        file_menu = tk.Menu(self._menubar, tearoff=0, bg=_c("surface"), fg=_c("text"), bd=1)
        self._menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Output Folder", command=self._on_set_output)
        file_menu.add_command(label="Open Output Folder    Ctrl+O", command=self._on_open_folder)
        file_menu.add_command(label="Export Logs...", command=self._on_export_logs)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._root.quit)

        queue_menu = tk.Menu(self._menubar, tearoff=0, bg=_c("surface"), fg=_c("text"), bd=1)
        self._menubar.add_cascade(label="Queue", menu=queue_menu)
        queue_menu.add_command(label="Start Downloads", command=self._on_start_queue)
        queue_menu.add_command(label="Clear Queue", command=self._on_clear_queue)

        view_menu = tk.Menu(self._menubar, tearoff=0, bg=_c("surface"), fg=_c("text"), bd=1)
        self._menubar.add_cascade(label="View", menu=view_menu)
        self._debug_var = tk.BooleanVar(value=self._debug_mode)
        view_menu.add_checkbutton(
            label="Debug Mode", variable=self._debug_var, command=self._on_toggle_debug
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Toggle Light/Dark Theme    Ctrl+T", command=self._on_toggle_theme
        )

        help_menu = tk.Menu(self._menubar, tearoff=0, bg=_c("surface"), fg=_c("text"), bd=1)
        self._menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Update yt-dlp", command=self._on_update_ytdlp)
        help_menu.add_command(label="yt-dlp version", command=self._on_show_ytdlp_version)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._on_about)

    def _update_debug_visibility(self) -> None:
        if not self._paned_window or not self._log_frame:
            return
        if self._debug_mode and not self._debug_panel_visible:
            self._paned_window.add(self._log_frame, weight=1)
            self._debug_panel_visible = True
            self._log_terminal.append("YouMuDow initialized", level="info")
        elif not self._debug_mode and self._debug_panel_visible:
            self._paned_window.forget(self._log_frame)
            self._debug_panel_visible = False

    def _setup_event_listeners(self) -> None:
        self._event_bus = get_event_bus()

        def on_log(event) -> None:
            if self._log_terminal:
                self._log_terminal.append(
                    event.message, level=event.level, timestamp=event.timestamp
                )

        def on_clear(event) -> None:
            if self._log_terminal:
                self._log_terminal.clear()

        self._log_unsubscribe = self._event_bus.subscribe(EventType.LOG_OUTPUT, on_log)
        self._clear_unsubscribe = self._event_bus.subscribe(EventType.LOG_CLEAR, on_clear)

        self._root.bind("<Control-d>", lambda _: self._on_download_now())
        self._root.bind("<Control-q>", lambda _: self._detail_panel._on_enqueue())
        self._root.bind("<Control-l>", lambda _: self._search_bar.search_entry.focus_set())
        self._root.bind("<Control-n>", lambda _: self._search_bar.search_var.set(""))
        self._root.bind("<Escape>", lambda _: self._on_cancel_search())
        self._root.bind("<Control-o>", lambda _: self._on_open_folder())
        self._root.bind(
            "<Control-Shift-C>",
            lambda _: self._log_terminal.clear() if self._log_terminal else None,
        )
        self._root.bind("<Control-t>", lambda _: self._on_toggle_theme())

    def _setup_controller_callbacks(self) -> None:
        def on_search_complete(results: list[Video]) -> None:
            self._root.after(0, self._on_search_complete, results)

        def on_download_complete(video: Video) -> None:
            self._root.after(0, self._on_download_complete, video)

        self._controller.on_search_complete(on_search_complete)
        self._controller.on_download_complete(on_download_complete)

    def _on_search_complete(self, results: list[Video]) -> None:
        try:
            self._is_searching = False
            self._results_table.update_results(results)
            if results:
                self._selected_video = results[0]
                self._detail_panel.update_detail_panel(results[0])
                self._set_status(f"Found: {results[0].title}")
            else:
                self._set_status("No results found")
            self._update_button_states()
        except Exception as e:
            logger.exception("Search handler failed")
            self._set_status(f"Error: {e}")

    def _on_download_complete(self, video: Video) -> None:
        self._is_downloading = False
        self._set_status(f"Downloaded: {video.title}")
        self._update_button_states()

    def _setup_state_observer(self) -> None:
        def on_state_change(snapshot: AppStateData) -> None:
            self._root.after(0, self._update_from_snapshot, snapshot)

        self._controller.state.on_change(on_state_change)

    def _update_from_snapshot(self, snapshot: AppStateData) -> None:
        self._is_downloading = snapshot.state is AppState.DOWNLOADING

        if snapshot.state is AppState.SEARCHING:
            self._is_searching = True
            self._set_status("Searching...")
        elif snapshot.state is AppState.DOWNLOADING:
            self._is_searching = False
            if snapshot.active_downloads:
                active = snapshot.active_downloads[0]
                self._status_bar.progress_var.set(active.progress)
                speed_info = (
                    f" · {active.speed}"
                    if active.speed and active.speed != "Calculating..."
                    else ""
                )
                eta_info = f" · ETA {active.eta}" if active.eta and active.eta != "00:00" else ""
                self._set_status(f"Downloading: {active.progress:.1f}%{speed_info}{eta_info}")
                self._status_bar.set_progress_color(_c("primary"))
            else:
                self._status_bar.progress_var.set(0)
                self._status_bar.set_progress_color(_c("primary"))
                self._set_status("Downloading...")
        elif snapshot.state is AppState.ERROR:
            self._is_searching = False
            self._is_downloading = False
            self._set_status(
                f"Error: {snapshot.error_message}" if snapshot.error_message else "Error occurred"
            )
            self._status_bar.progress_var.set(0)
            self._status_bar.set_progress_color(_c("error"))
        else:
            self._is_searching = False
            self._is_downloading = False
            self._set_status("Ready" if snapshot.state is AppState.IDLE else snapshot.state.name)
            if not snapshot.active_downloads:
                self._status_bar.progress_var.set(0)
                self._status_bar.set_progress_color(_c("border"))

        self._update_button_states()
        if self._detail_panel._queue_panel_visible:
            self._detail_panel._update_queue_display(snapshot)
        self._root.after(50, self._status_bar.update_progress_bar)

        mode_is_debug = snapshot.mode is AppMode.DEBUG
        if mode_is_debug != self._debug_mode:
            self._debug_mode = mode_is_debug
            self._debug_var.set(mode_is_debug)
            self._update_debug_visibility()

    def _set_status(self, message: str) -> None:
        if self._status_bar:
            self._status_bar.set_status(message)

    def _update_button_states(self) -> None:
        if self._search_bar:
            self._search_bar.update_button_states(self._is_searching, self._is_downloading)
        if self._detail_panel:
            self._detail_panel.update_button_states(self._is_searching, self._is_downloading)

    def _on_tab_changed(self, event: tk.Event | None = None) -> None:
        if not hasattr(self, "_notebook"):
            return
        current = self._notebook.index(self._notebook.select())
        if current == 1 and self._history_panel:
            self._history_panel.refresh()

    def _on_search(self) -> None:
        query = self._search_bar.get_query()
        if not query or self._is_searching:
            return

        self._is_searching = True
        self._set_status("Searching...")
        self._update_button_states()
        self._results_table.is_playlist = False
        self._results_table.playlist_videos = []
        self._results_table.clear_results()

        if self._config:
            self._config.add_search(query)
            self._search_bar.update_history(self._config.get_search_history())

        if is_supported_url(query):
            if is_playlist_url(query):
                self._results_table.is_playlist = True
                self._handle_playlist_input(query)
            else:
                self._handle_url_input(query)
        else:
            self._results_table.results_tree.insert("", "end", values=("Searching...", "", ""))
            self._controller.search(query)

    def _handle_url_input(self, url: str) -> None:
        self._set_status("Fetching video info...")
        self._controller.search_url(url)

    def _on_cancel_download(self) -> None:
        self._controller.stop_downloads()
        self._is_downloading = False
        self._set_status("Downloads stopped")
        self._update_button_states()

    def _on_cancel_search(self) -> None:
        self._controller.cancel_search()
        self._is_searching = False
        self._set_status("Search cancelled")
        self._update_button_states()

    def _handle_playlist_input(self, url: str) -> None:
        self._set_status("Fetching playlist...")

        def do_fetch() -> None:
            videos = self._controller.search_playlist(url)
            self._root.after(0, self._on_playlist_complete, videos)

        thread = threading.Thread(target=do_fetch, daemon=True)
        thread.start()

    def _on_playlist_complete(self, videos: list[Video]) -> None:
        if videos:
            self._results_table.update_results(videos)
            self._results_table.playlist_videos = videos
            self._set_status(f"Playlist: {len(videos)} videos")
        else:
            self._set_status("Failed to fetch playlist")
        self._is_searching = False
        self._update_button_states()

    def _check_clipboard_on_start(self) -> None:
        try:
            clipboard = self._root.clipboard_get()
            if clipboard and is_supported_url(clipboard.strip()):
                self._search_bar.search_var.set(clipboard.strip())
        except tk.TclError as e:
            logger.debug("Clipboard check failed: %s", e)

    def _check_ytdlp_on_start(self) -> None:
        version = get_ytdlp_version()
        if not version:
            self._set_status("⚠ yt-dlp not found. Install it with: pip install yt-dlp")

    def _on_update_ytdlp(self) -> None:
        self._set_status("Updating yt-dlp...")

        def on_success(version: str) -> None:
            self._root.after(0, lambda: self._set_status(f"yt-dlp updated to {version}"))

        def on_error(error: str) -> None:
            self._root.after(0, lambda: self._set_status(f"Update failed: {error}"))

        update_ytdlp(on_success, on_error)

    def _on_show_ytdlp_version(self) -> None:
        version = get_ytdlp_version()
        messagebox.showinfo("yt-dlp version", f"Installed version: {version or 'not found'}")

    def _on_about(self) -> None:
        messagebox.showinfo(
            "About YouMuDow",
            f"YouMuDow v{__version__}\n"
            f"yt-dlp: {get_ytdlp_version() or 'not found'}\n\n"
            "Music & Video Downloader\n"
            "Supports YouTube, SoundCloud, Vimeo, Twitter and 1000+ sites via yt-dlp\n"
            "github.com/Ghostalex07/YouMuDow",
        )

    def _on_export_logs(self) -> None:
        if not self._log_terminal:
            return
        default_name = f"youmudow_logs_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            title="Export Logs",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                self._log_terminal.export_to_file(Path(path))
                self._set_status(f"Logs exported to {path}")
            except (OSError, ValueError) as e:
                self._set_status(f"Export failed: {e}")

    def _on_open_folder(self) -> None:
        path = self._controller.get_output_path()
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(["explorer", str(path)])
            elif system == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except (OSError, ValueError) as e:
            logger.debug("Could not open folder: %s", e)
            self._set_status(f"Output: {path}")

    def _on_download_now(self) -> None:
        selected = self._results_table.get_selected_videos()
        if selected:
            opts = self._detail_panel.get_current_options()
            if opts is None:
                return
            self._is_downloading = True
            self._update_button_states()
            for video in selected:
                video.options = opts
            self._controller.enqueue_multiple(selected)
            self._controller.start_downloads()
            self._set_status(f"Downloading {len(selected)} videos...")
            return

        if self._results_table.is_playlist and self._results_table.playlist_videos:
            return

        video = self._selected_video
        if video is None:
            return

        self._is_downloading = True
        self._update_button_states()
        self._detail_panel.apply_options_to_video(video)
        self._controller.enqueue(video)
        self._controller.start_downloads()
        self._set_status(f"Downloading: {video.title}")

    def _on_start_queue(self) -> None:
        if self._is_downloading:
            return
        self._is_downloading = True
        self._update_button_states()
        self._controller.start_downloads()
        self._set_status("Starting downloads...")

    def _on_clear_queue(self) -> None:
        self._controller.clear_queue()
        self._set_status("Queue cleared")

    def _on_set_output(self) -> None:
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self._controller.set_output_path(Path(folder))
            self._set_status(f"Output: {folder}")

    def _on_toggle_debug(self) -> None:
        self._debug_mode = self._debug_var.get()
        self._controller.set_debug_mode(self._debug_mode)
        self._update_debug_visibility()

    def _on_toggle_theme(self) -> None:
        current = self._theme_manager.current.name
        new_theme: ThemeName = "light" if current == "dark" else "dark"
        self._theme_manager.set_theme(new_theme)
        configure_styles(self._theme_manager.colors)
        self._results_table._style_treeview()
        self._apply_theme_colors()
        if self._log_terminal:
            self._log_terminal.set_dark_mode(new_theme == "dark")
        if self._config:
            self._config.set("theme", new_theme)

    def _apply_theme_colors(self) -> None:
        colors = self._theme_manager.colors
        self._root.configure(bg=colors.BACKGROUND)
        self._update_widget_colors(self._root, colors)
        if self._menubar:
            self._update_widget_colors(self._menubar, colors)
        try:
            self._status_bar.set_progress_color(colors.PRIMARY)
        except tk.TclError:
            pass

    def _update_widget_colors(self, widget: tk.Widget, colors: Any) -> None:
        cls = widget.winfo_class()

        def _cv(key: str) -> str:
            return (
                key
                if key.startswith("#")
                else getattr(colors, _COLOR_MAP.get(key, key.upper()), "#000000")
            )

        try:
            if cls in ("Frame", "Labelframe"):
                bg_key = getattr(widget, "_bg_key", "bg")
                widget.configure(bg=_cv(bg_key))
            elif cls == "Label":
                try:
                    parent_bg = widget.master.cget("bg")
                    widget.configure(bg=parent_bg, fg=colors.TEXT)
                except tk.TclError:
                    widget.configure(bg=colors.BACKGROUND, fg=colors.TEXT)
            elif cls == "Button":
                theme = getattr(widget, "_theme", None)
                if theme:
                    widget.configure(
                        bg=_cv(theme.get("bg", "surface")),
                        fg=_cv(theme.get("fg", "text")),
                        activebackground=_cv(theme.get("activebg", theme.get("bg", "surface"))),
                        activeforeground=_cv(theme.get("activefg", theme.get("fg", "text"))),
                    )
                else:
                    widget.configure(
                        bg=colors.SURFACE,
                        fg=colors.TEXT,
                        activebackground=colors.HOVER,
                        activeforeground=colors.TEXT,
                    )
            elif cls == "Entry":
                widget.configure(bg=colors.SURFACE, fg=colors.TEXT, insertbackground=colors.TEXT)
            elif cls in ("Checkbutton", "Radiobutton"):
                try:
                    parent_bg = widget.master.cget("bg")
                    widget.configure(
                        bg=parent_bg,
                        fg=colors.TEXT,
                        selectcolor=parent_bg,
                        activebackground=parent_bg,
                        activeforeground=colors.TEXT,
                    )
                except tk.TclError:
                    widget.configure(
                        bg=colors.SURFACE,
                        fg=colors.TEXT,
                        selectcolor=colors.SURFACE,
                        activebackground=colors.SURFACE,
                        activeforeground=colors.TEXT,
                    )
            elif cls == "Canvas":
                bg_key = getattr(widget, "_bg_key", "bg")
                widget.configure(bg=_cv(bg_key))
            elif cls == "Menu":
                widget.configure(bg=colors.SURFACE, fg=colors.TEXT)
        except tk.TclError:
            pass
        try:
            for child in widget.winfo_children():
                self._update_widget_colors(child, colors)
        except tk.TclError:
            pass

    def _on_close(self) -> None:
        if self._config:
            try:
                self._config.window_geometry = self._root.geometry()
                dp = self._detail_panel
                rate = dp._rate_limit_var.get().strip()
                if rate and not is_valid_rate_limit(rate):
                    rate = ""
                self._config.set("format", dp._format_var.get())
                self._config.set("quality", dp._quality_var.get())
                self._config.set("subtitles", dp._subtitles_var.get())
                self._config.set("subtitle_lang", dp._subtitle_lang_var.get())
                self._config.set("embed_subtitles", dp._embed_subs_var.get())
                self._config.set("use_cookies", dp._use_cookies_var.get())
                self._config.set("cookies_source", dp._cookies_source_var.get())
                self._config.set("cookies_file", dp._cookies_file_var.get())
                self._config.set("browser", dp._browser_var.get())
                self._config.set("profile", dp._profile_var.get())
                self._config.set("rate_limit", rate)
                self._config.set("split_chapters", dp._split_chapters_var.get())
                self._config.set("options_panel_open", dp._options_frame.winfo_ismapped())
                self._config.set("concurrent_downloads", dp._concurrent_var.get())
                self._config.output_path = self._controller.get_output_path()
                self._config.save()
            except (tk.TclError, KeyError, TypeError, ValueError) as e:
                logger.debug("Could not save config on close: %s", e)
        self.destroy()

    def _apply_config(self) -> None:
        if not self._config:
            return
        try:
            dp = self._detail_panel
            dp._format_var.set(self._config.get("format", "mp3"))
            dp._quality_var.set(self._config.get("quality", "best"))
            dp._subtitles_var.set(self._config.get("subtitles", False))
            dp._subtitle_lang_var.set(self._config.get("subtitle_lang", "en"))
            dp._embed_subs_var.set(self._config.get("embed_subtitles", False))
            dp._use_cookies_var.set(self._config.get("use_cookies", False))
            dp._cookies_source_var.set(self._config.get("cookies_source", "browser"))
            dp._cookies_file_var.set(self._config.get("cookies_file", ""))

            saved_browser = self._config.get("browser", "chrome")
            available = get_available_browsers()
            if available:
                browser_to_use = saved_browser if saved_browser in available else available[0]
                dp._browser_var.set(browser_to_use)
            else:
                dp._browser_var.set("chrome")
            dp._on_browser_changed()

            current_profiles = list(dp._profile_combo["values"])
            saved_profile = self._config.get("profile", "Default")
            if saved_profile in current_profiles:
                dp._profile_var.set(saved_profile)
            elif current_profiles:
                dp._profile_var.set(current_profiles[0])
            else:
                dp._profile_var.set("Default")
            dp._rate_limit_var.set(self._config.get("rate_limit", ""))
            dp._split_chapters_var.set(self._config.get("split_chapters", False))
            dp._concurrent_var.set(self._config.get("concurrent_downloads", 1))

            if self._config.get("options_panel_open", False):
                dp._options_frame.pack(
                    fill="both", expand=True, padx=SPACING["md"], pady=(0, SPACING["md"])
                )
                dp._detail_toggle_btn.configure(text="▼ OPTIONS")

            geo = self._config.window_geometry
            if geo:
                try:
                    self._root.geometry(geo)
                    self._root.update_idletasks()
                    x = self._root.winfo_x()
                    y = self._root.winfo_y()
                    w = self._root.winfo_width()
                    h = self._root.winfo_height()
                    sw = self._root.winfo_screenwidth()
                    sh = self._root.winfo_screenheight()
                    if x + w < 0 or y + h < 0 or x > sw or y > sh:
                        self._root.geometry(f"{min(sw, 1200)}x{min(sh, 800)}+0+0")
                except tk.TclError as e:
                    logger.debug("Could not restore window geometry: %s", e)
        except (tk.TclError, KeyError, TypeError, ValueError) as e:
            logger.warning("Could not apply saved config: %s", e)

    def run(self) -> None:
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.mainloop()

    def destroy(self) -> None:
        if self._log_unsubscribe:
            self._log_unsubscribe()
        if self._clear_unsubscribe:
            self._clear_unsubscribe()
        self._root.destroy()
