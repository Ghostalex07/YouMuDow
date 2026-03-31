"""Main window for YouMuDow.

Tkinter-based GUI layer. All business logic is delegated to the controller.
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import TYPE_CHECKING

from youmudow.domain.models import Video
from youmudow.app.state import AppStateData
from youmudow.app.events import EventType, EventBus, get_event_bus
from youmudow.ui.widgets.log_terminal import LogTerminal

if TYPE_CHECKING:
    from youmudow.app.controller import AppController


class MainWindow:
    """Main application window using tkinter."""

    def __init__(self, controller: "AppController", debug_mode: bool = False) -> None:
        self._controller = controller
        self._root = tk.Tk()
        self._root.title("YouMuDow")
        self._root.geometry("900x700")
        self._root.minsize(800, 600)

        self._selected_video: Video | None = None
        self._is_searching = False
        self._debug_mode = debug_mode
        self._event_bus: EventBus | None = None
        self._log_unsubscribe: callable | None = None
        self._clear_unsubscribe: callable | None = None
        
        self._log_terminal: LogTerminal | None = None
        self._log_frame: ttk.Frame | None = None
        self._paned_window: ttk.PanedWindow | None = None

        self._setup_ui()
        self._setup_event_listeners()
        self._setup_controller_callbacks()
        self._setup_state_observer()

    def _setup_ui(self) -> None:
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        self._root.rowconfigure(1, weight=0)

        self._paned_window = ttk.PanedWindow(self._root, orient=tk.VERTICAL)
        self._paned_window.grid(row=0, column=0, sticky="nsew")

        self._create_main_content()
        self._create_log_panel()
        self._create_status_bar()
        self._create_menu()
        
        self._update_debug_visibility()

    def _create_main_content(self) -> None:
        main_frame = ttk.Frame(self._paned_window)
        self._paned_window.add(main_frame, weight=3)

        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(1, weight=1)

        self._create_search_bar(main_frame)
        self._create_results_panel(main_frame)
        self._create_detail_panel(main_frame)

    def _create_log_panel(self) -> None:
        self._log_frame = ttk.Frame(self._paned_window)
        log_label_frame = ttk.LabelFrame(self._log_frame, text="Output Log", padding=5)
        log_label_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._log_terminal = LogTerminal(log_label_frame)
        self._log_terminal.pack(fill="both", expand=True)

    def _create_search_bar(self, parent: ttk.Frame) -> None:
        search_frame = ttk.Frame(parent, padding=10)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        search_frame.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(
            search_frame,
            textvariable=self._search_var,
            font=("TkDefaultFont", 12),
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._search_entry.bind("<Return>", lambda _: self._on_search())

        self._search_btn = ttk.Button(
            search_frame,
            text="Search",
            command=self._on_search,
        )
        self._search_btn.grid(row=0, column=1)

        self._search_entry.focus()

    def _create_results_panel(self, parent: ttk.Frame) -> None:
        results_frame = ttk.Frame(parent, padding=(10, 0, 10, 10))
        results_frame.grid(row=1, column=0, sticky="nsew")
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)

        columns = ("title", "uploader", "duration")
        self._results_tree = ttk.Treeview(
            results_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self._results_tree.heading("title", text="Title")
        self._results_tree.heading("uploader", text="Uploader")
        self._results_tree.heading("duration", text="Duration")
        self._results_tree.column("title", width=300)
        self._results_tree.column("uploader", width=150)
        self._results_tree.column("duration", width=80)

        scrollbar = ttk.Scrollbar(results_frame, orient="vertical")
        scrollbar.configure(command=self._results_tree.yview)
        self._results_tree.configure(yscrollcommand=scrollbar.set)

        self._results_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._results_tree.bind("<<TreeviewSelect>>", self._on_result_select)
        self._results_tree.bind("<Double-Button-1>", lambda _: self._on_enqueue())

    def _create_detail_panel(self, parent: ttk.Frame) -> None:
        detail_frame = ttk.LabelFrame(
            parent,
            text="Details",
            padding=10,
        )
        detail_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 10), pady=(10, 10))
        detail_frame.rowconfigure(3, weight=1)

        ttk.Label(detail_frame, text="Title:", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="nw", pady=(0, 5)
        )
        self._detail_title = ttk.Label(detail_frame, text="-", wraplength=200)
        self._detail_title.grid(row=0, column=1, sticky="nw", padx=(5, 0), pady=(0, 5))

        ttk.Label(detail_frame, text="Uploader:", font=("TkDefaultFont", 10, "bold")).grid(
            row=1, column=0, sticky="nw", pady=(0, 5)
        )
        self._detail_uploader = ttk.Label(detail_frame, text="-")
        self._detail_uploader.grid(row=1, column=1, sticky="nw", padx=(5, 0), pady=(0, 5))

        ttk.Label(detail_frame, text="Format:", font=("TkDefaultFont", 10, "bold")).grid(
            row=2, column=0, sticky="nw", pady=(0, 10)
        )
        self._format_var = tk.StringVar(value="mp3")
        format_combo = ttk.Combobox(
            detail_frame,
            textvariable=self._format_var,
            values=["mp3", "mp4", "wav", "m4a"],
            state="readonly",
            width=10,
        )
        format_combo.grid(row=2, column=1, sticky="w", padx=(5, 0), pady=(0, 10))

        button_frame = ttk.Frame(detail_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self._enqueue_btn = ttk.Button(
            button_frame,
            text="Add to Queue",
            command=self._on_enqueue,
        )
        self._enqueue_btn.pack(side="left", padx=(0, 5))

        self._download_btn = ttk.Button(
            button_frame,
            text="Download Now",
            command=self._on_download_now,
        )
        self._download_btn.pack(side="left")

    def _create_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self._root,
            textvariable=self._status_var,
            relief="sunken",
            anchor="w",
            padding=(5, 2),
        )
        status_bar.grid(row=1, column=0, sticky="ew")

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            self._root,
            variable=self._progress_var,
            maximum=100,
        )
        self._progress_bar.grid(row=2, column=0, sticky="ew")

    def _create_menu(self) -> None:
        menubar = tk.Menu(self._root)
        self._root.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Output Folder", command=self._on_set_output)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._root.quit)

        queue_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Queue", menu=queue_menu)
        queue_menu.add_command(label="Start Downloads", command=self._on_start_queue)
        queue_menu.add_command(label="Clear Queue", command=self._on_clear_queue)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        self._debug_var = tk.BooleanVar(value=self._debug_mode)
        view_menu.add_checkbutton(
            label="Debug Mode",
            variable=self._debug_var,
            command=self._on_toggle_debug,
        )

    def _update_debug_visibility(self) -> None:
        if self._paned_window and self._log_frame:
            if self._debug_mode:
                panes = self._paned_window.panes()
                if self._log_frame not in panes:
                    self._paned_window.add(self._log_frame, weight=1)
                    self._log_terminal.append("Debug Mode enabled", level="info")
            else:
                panes = self._paned_window.panes()
                if self._log_frame in panes:
                    self._paned_window.forget(self._log_frame)

    def _setup_event_listeners(self) -> None:
        self._event_bus = get_event_bus()

        def on_log(event) -> None:
            if self._log_terminal:
                self._root.after(0, lambda: self._log_terminal.append(
                    event.message,
                    level=event.level,
                    timestamp=event.timestamp,
                ))

        def on_clear(event) -> None:
            if self._log_terminal:
                self._root.after(0, lambda: self._log_terminal.clear())

        self._log_unsubscribe = self._event_bus.subscribe(EventType.LOG_OUTPUT, on_log)
        self._clear_unsubscribe = self._event_bus.subscribe(EventType.LOG_CLEAR, on_clear)

    def _setup_controller_callbacks(self) -> None:
        def on_search_complete(results: list[Video]) -> None:
            self._is_searching = False
            self._update_results(results)
            self._set_status(f"Found {len(results)} results")

        def on_download_complete(video: Video) -> None:
            self._set_status(f"Downloaded: {video.title}")

        self._controller.on_search_complete(on_search_complete)
        self._controller.on_download_complete(on_download_complete)

    def _setup_state_observer(self) -> None:
        def on_state_change(snapshot: AppStateData) -> None:
            self._update_from_snapshot(snapshot)

        self._controller.state.on_change(on_state_change)

    def _update_from_snapshot(self, snapshot: AppStateData) -> None:
        if snapshot.state.name == "SEARCHING":
            self._set_status("Searching...")
            self._search_btn.configure(state="disabled")
        else:
            self._set_status("Ready" if snapshot.state.name == "IDLE" else snapshot.state.name)
            self._search_btn.configure(state="normal")

        if snapshot.active_downloads:
            active = snapshot.active_downloads[0]
            self._progress_var.set(active.progress)
            self._set_status(f"Downloading: {active.progress:.1f}%")
        else:
            self._progress_var.set(0)

    def _update_results(self, results: list[Video]) -> None:
        for item in self._results_tree.get_children():
            self._results_tree.delete(item)

        for video in results:
            duration = self._format_duration(video.duration)
            self._results_tree.insert("", "end", values=(video.title, video.uploader, duration))

    def _format_duration(self, seconds: int) -> str:
        if seconds == 0:
            return "-"
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _set_status(self, message: str) -> None:
        self._status_var.set(message)

    def _on_search(self) -> None:
        query = self._search_var.get().strip()
        if not query:
            return

        if self._is_searching:
            return

        self._is_searching = True
        self._set_status("Searching...")
        self._search_btn.configure(state="disabled")
        self._controller.search(query)

    def _on_result_select(self, event: tk.Event) -> None:
        selection = self._results_tree.selection()
        if not selection:
            return

        results = self._controller.state.get_search_results()
        index = self._results_tree.index(selection[0])

        if index < len(results):
            self._selected_video = results[index]
            self._update_detail_panel(self._selected_video)

    def _update_detail_panel(self, video: Video) -> None:
        self._detail_title.configure(text=video.title or "-")
        self._detail_uploader.configure(text=video.uploader or "-")
        self._format_var.set(video.format)

    def _on_enqueue(self) -> None:
        video = self._selected_video
        if video is None:
            return

        video.format = self._format_var.get()
        self._controller.enqueue(video)
        self._set_status(f"Added to queue: {video.title}")

    def _on_download_now(self) -> None:
        video = self._selected_video
        if video is None:
            return

        video.format = self._format_var.get()
        self._controller.download_now(video)
        self._set_status(f"Downloading: {video.title}")

    def _on_start_queue(self) -> None:
        self._controller.start_downloads()
        self._set_status("Starting downloads...")

    def _on_clear_queue(self) -> None:
        self._controller.clear_queue()
        self._set_status("Queue cleared")

    def _on_set_output(self) -> None:
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self._controller.set_output_path(Path(folder))
            self._set_status(f"Output: {folder}")

    def _on_toggle_debug(self) -> None:
        self._debug_mode = self._debug_var.get()
        self._controller.set_debug_mode(self._debug_mode)
        self._update_debug_visibility()

    def run(self) -> None:
        self._root.mainloop()

    def destroy(self) -> None:
        if self._log_unsubscribe:
            self._log_unsubscribe()
        if self._clear_unsubscribe:
            self._clear_unsubscribe()
        self._root.destroy()
