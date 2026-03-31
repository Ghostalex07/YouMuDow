"""Main window for YouMuDow.

Tkinter-based GUI layer with modern dark theme.
All business logic is delegated to the controller.
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


SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 32,
}

FONT = {
    "h1": ("Segoe UI", 12, "bold"),
    "h2": ("Segoe UI", 10, "bold"),
    "body": ("Segoe UI", 10),
    "small": ("Segoe UI", 9),
    "label": ("Segoe UI", 9, "bold"),
    "mono": ("Cascadia Code", 10, "normal"),
}

COLORS = {
    "bg": "#121218",
    "surface": "#1E1E26",
    "primary": "#7C5CFC",
    "secondary": "#9B85FD",
    "accent": "#A78BFA",
    "text": "#ECECF1",
    "text_secondary": "#8A8A99",
    "border": "#2E2E38",
    "success": "#34D399",
    "warning": "#FBBF24",
    "error": "#F87171",
    "info": "#60A5FA",
    "hover": "#2A2A36",
    "selection": "#4C3D8C",
}


class MainWindow:
    """Main application window using tkinter with modern styling."""

    def _add_hover_effect(self, widget: tk.Widget, enter_color: str, leave_color: str, enter_fg: str | None = None, leave_fg: str | None = None) -> None:
        """Add hover effect to a widget."""
        def on_enter(e: tk.Event) -> None:
            widget.configure(bg=enter_color)
            if enter_fg:
                widget.configure(fg=enter_fg)
        def on_leave(e: tk.Event) -> None:
            widget.configure(bg=leave_color)
            if leave_fg:
                widget.configure(fg=leave_fg)
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def __init__(self, controller: "AppController", debug_mode: bool = False) -> None:
        self._controller = controller
        self._root = tk.Tk()
        self._root.title("YouMuDow")
        self._root.geometry("1000x700")
        self._root.minsize(800, 600)
        self._root.configure(bg=COLORS["bg"])

        self._selected_video: Video | None = None
        self._is_searching = False
        self._is_downloading = False
        self._debug_mode = debug_mode
        self._debug_panel_visible = False
        self._event_bus: EventBus | None = None
        self._log_unsubscribe: callable | None = None
        self._clear_unsubscribe: callable | None = None
        
        self._log_terminal: LogTerminal | None = None
        self._log_frame: tk.Frame | None = None
        self._paned_window: ttk.PanedWindow | None = None
        self._main_content_frame: tk.Frame | None = None

        self._setup_ui()
        self._setup_event_listeners()
        self._setup_controller_callbacks()
        self._setup_state_observer()

    def _setup_ui(self) -> None:
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)

        self._paned_window = ttk.PanedWindow(self._root, orient=tk.VERTICAL)
        self._paned_window.grid(row=0, column=0, sticky="nsew")

        self._create_main_content()
        self._create_log_panel()
        self._create_status_bar()
        self._create_menu()
        
        self._update_debug_visibility()

    def _create_main_content(self) -> None:
        main_frame = tk.Frame(self._paned_window, bg=COLORS["bg"])
        self._main_content_frame = main_frame
        self._paned_window.add(main_frame, weight=3)

        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(1, weight=1)

        self._create_search_bar(main_frame)
        self._create_results_panel(main_frame)
        self._create_detail_panel(main_frame)

    def _create_log_panel(self) -> None:
        self._log_frame = tk.Frame(self._paned_window, bg=COLORS["bg"])
        
        label = tk.Label(
            self._log_frame,
            text="  OUTPUT",
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"],
            font=FONT["label"],
            anchor="w",
        )
        label.pack(fill="x", pady=(SPACING["sm"], SPACING["xs"]))
        
        log_container = tk.Frame(self._log_frame, bg=COLORS["bg"])
        log_container.pack(fill="both", expand=True, padx=SPACING["sm"], pady=(0, SPACING["sm"]))
        
        self._log_terminal = LogTerminal(log_container)
        self._log_terminal.pack(fill="both", expand=True)

    def _create_search_bar(self, parent: tk.Frame) -> None:
        search_frame = tk.Frame(parent, bg=COLORS["bg"])
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=SPACING["md"], pady=SPACING["md"])
        
        entry_frame = tk.Frame(
            search_frame,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        entry_frame.pack(side="left", fill="both", expand=True, padx=(0, SPACING["sm"]))
        entry_frame.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            entry_frame,
            textvariable=self._search_var,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 12),
            relief="flat",
            bd=0,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=SPACING["md"], pady=SPACING["md"])
        self._search_entry.bind("<Return>", lambda _: self._on_search())

        self._search_btn = tk.Button(
            search_frame,
            text="Search",
            bg=COLORS["primary"],
            fg="#FFFFFF",
            activebackground=COLORS["secondary"],
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            font=FONT["h2"],
            command=self._on_search,
        )
        self._search_btn.pack(side="left")
        self._add_hover_effect(self._search_btn, COLORS["secondary"], COLORS["primary"])

        self._search_entry.focus()

    def _create_results_panel(self, parent: tk.Frame) -> None:
        container = tk.Frame(parent, bg=COLORS["bg"])
        container.grid(row=1, column=0, sticky="nsew", padx=(SPACING["md"], SPACING["sm"]), pady=(0, SPACING["md"]))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        columns = ("title", "uploader", "duration")
        self._results_tree = ttk.Treeview(
            container,
            columns=columns,
            show="headings",
            selectmode="browse",
            style="Modern.Treeview",
        )
        self._results_tree.heading("title", text="TITLE")
        self._results_tree.heading("uploader", text="UPLOADER")
        self._results_tree.heading("duration", text="DURATION")
        self._results_tree.column("title", width=350)
        self._results_tree.column("uploader", width=180)
        self._results_tree.column("duration", width=80)

        scrollbar = ttk.Scrollbar(container, orient="vertical")
        scrollbar.configure(command=self._results_tree.yview)
        self._results_tree.configure(yscrollcommand=scrollbar.set)

        self._results_tree.grid(row=0, column=0, sticky="nsew", padx=(0, SPACING["xs"]))
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._results_tree.bind("<<TreeviewSelect>>", self._on_result_select)
        self._results_tree.bind("<Double-Button-1>", lambda _: self._on_enqueue())

        self._style_treeview()

    def _style_treeview(self) -> None:
        style = ttk.Style()
        style.configure(
            "Modern.Treeview",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["surface"],
            borderwidth=0,
            rowheight=44,
            font=FONT["body"],
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=COLORS["bg"],
            foreground=COLORS["text_secondary"],
            borderwidth=0,
            padding=(12, 8),
            font=FONT["label"],
        )
        style.configure(
            "Modern.Treeview.Row",
            background=COLORS["surface"],
        )
        style.configure(
            "Modern.Treeview.Selected",
            background=COLORS["primary"],
            foreground="#FFFFFF",
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", "#FFFFFF")],
        )

    def _create_detail_panel(self, parent: tk.Frame) -> None:
        detail_container = tk.Frame(parent, bg=COLORS["bg"])
        detail_container.grid(row=1, column=1, sticky="nsew", padx=(SPACING["sm"], SPACING["md"]), pady=(0, SPACING["md"]))

        detail_frame = tk.Frame(detail_container, bg=COLORS["surface"])
        detail_frame.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"])

        tk.Label(
            detail_frame,
            text="DETAILS",
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            font=FONT["label"],
            anchor="w",
        ).pack(anchor="w", pady=(0, SPACING["md"]))

        row1 = tk.Frame(detail_frame, bg=COLORS["surface"])
        row1.pack(fill="x", pady=(0, SPACING["sm"]))
        tk.Label(
            row1,
            text="Title:",
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            font=FONT["body"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._detail_title = tk.Label(
            row1,
            text="-",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONT["body"],
            anchor="w",
            wraplength=180,
        )
        self._detail_title.pack(side="left", fill="x", expand=True)

        row2 = tk.Frame(detail_frame, bg=COLORS["surface"])
        row2.pack(fill="x", pady=(0, SPACING["sm"]))
        tk.Label(
            row2,
            text="Uploader:",
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            font=FONT["body"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._detail_uploader = tk.Label(
            row2,
            text="-",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=FONT["body"],
            anchor="w",
        )
        self._detail_uploader.pack(side="left")

        row3 = tk.Frame(detail_frame, bg=COLORS["surface"])
        row3.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(
            row3,
            text="Format:",
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            font=FONT["body"],
            width=10,
            anchor="w",
        ).pack(side="left")
        
        self._format_var = tk.StringVar(value="mp3")
        format_combo = ttk.Combobox(
            row3,
            textvariable=self._format_var,
            values=["mp3", "mp4", "wav", "m4a"],
            state="readonly",
            width=12,
            font=FONT["body"],
        )
        format_combo.pack(side="left")

        button_frame = tk.Frame(detail_frame, bg=COLORS["surface"])
        button_frame.pack(fill="x", pady=(SPACING["md"], 0))

        self._enqueue_btn = tk.Button(
            button_frame,
            text="Add to Queue",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=FONT["body"],
            command=self._on_enqueue,
        )
        self._enqueue_btn.pack(side="left", padx=(0, SPACING["sm"]), fill="x", expand=True)
        self._add_hover_effect(self._enqueue_btn, COLORS["hover"], COLORS["surface"])

        self._download_btn = tk.Button(
            button_frame,
            text="Download",
            bg=COLORS["primary"],
            fg="#FFFFFF",
            activebackground=COLORS["secondary"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=FONT["h2"],
            command=self._on_download_now,
        )
        self._download_btn.pack(side="left", fill="x", expand=True)
        self._add_hover_effect(self._download_btn, COLORS["secondary"], COLORS["primary"])

    def _create_status_bar(self) -> None:
        status_frame = tk.Frame(self._root, bg=COLORS["surface"])
        status_frame.grid(row=1, column=0, sticky="ew", padx=SPACING["md"], pady=SPACING["sm"])
        status_frame.columnconfigure(0, weight=1)

        self._status_var = tk.StringVar(value="Ready")
        self._status_label = tk.Label(
            status_frame,
            textvariable=self._status_var,
            bg=COLORS["surface"],
            fg=COLORS["text_secondary"],
            font=FONT["small"],
            anchor="w",
        )
        self._status_label.grid(row=0, column=0, sticky="w")

        progress_frame = tk.Frame(status_frame, bg=COLORS["surface"], height=6)
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(SPACING["sm"], 0))
        progress_frame.columnconfigure(0, weight=1)

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = tk.Canvas(
            progress_frame,
            bg=COLORS["surface"],
            height=6,
            highlightthickness=0,
            relief="flat",
        )
        self._progress_bar.pack(fill="x")
        self._progress_rect = self._progress_bar.create_rectangle(
            0, 0, 0, 6, fill=COLORS["primary"], outline=""
        )

    def _update_progress_bar(self) -> None:
        try:
            width = self._progress_bar.winfo_width()
            if width < 1:
                width = 1
            progress = self._progress_var.get() / 100.0
            x_pos = width * progress
            self._progress_bar.coords(self._progress_rect, 0, 0, x_pos, 6)
        except tk.TclError:
            pass

    def _create_menu(self) -> None:
        menubar = tk.Menu(self._root, bg=COLORS["bg"], fg=COLORS["text"], bd=0, relief="flat")
        self._root.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["surface"], fg=COLORS["text"], bd=1)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Output Folder", command=self._on_set_output)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._root.quit)

        queue_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["surface"], fg=COLORS["text"], bd=1)
        menubar.add_cascade(label="Queue", menu=queue_menu)
        queue_menu.add_command(label="Start Downloads", command=self._on_start_queue)
        queue_menu.add_command(label="Clear Queue", command=self._on_clear_queue)

        view_menu = tk.Menu(menubar, tearoff=0, bg=COLORS["surface"], fg=COLORS["text"], bd=1)
        menubar.add_cascade(label="View", menu=view_menu)
        self._debug_var = tk.BooleanVar(value=self._debug_mode)
        view_menu.add_checkbutton(
            label="Debug Mode",
            variable=self._debug_var,
            command=self._on_toggle_debug,
        )

    def _update_debug_visibility(self) -> None:
        if not self._paned_window or not self._log_frame:
            return
        
        should_be_visible = self._debug_mode
        
        if should_be_visible and not self._debug_panel_visible:
            self._paned_window.add(self._log_frame, weight=1)
            self._debug_panel_visible = True
            self._log_terminal.append("YouMuDow initialized", level="info")
        elif not should_be_visible and self._debug_panel_visible:
            self._paned_window.forget(self._log_frame)
            self._debug_panel_visible = False

    def _setup_event_listeners(self) -> None:
        self._event_bus = get_event_bus()

        def on_log(event) -> None:
            if self._log_terminal:
                self._log_terminal.append(
                    event.message,
                    level=event.level,
                    timestamp=event.timestamp,
                )

        def on_clear(event) -> None:
            if self._log_terminal:
                self._log_terminal.clear()

        self._log_unsubscribe = self._event_bus.subscribe(EventType.LOG_OUTPUT, on_log)
        self._clear_unsubscribe = self._event_bus.subscribe(EventType.LOG_CLEAR, on_clear)

    def _setup_controller_callbacks(self) -> None:
        def on_search_complete(results: list[Video]) -> None:
            self._is_searching = False
            self._update_results(results)
            self._set_status(f"Found {len(results)} results")
            self._update_button_states()

        def on_download_complete(video: Video) -> None:
            self._is_downloading = False
            self._set_status(f"Downloaded: {video.title}")
            self._update_button_states()

        self._controller.on_search_complete(on_search_complete)
        self._controller.on_download_complete(on_download_complete)

    def _setup_state_observer(self) -> None:
        def on_state_change(snapshot: AppStateData) -> None:
            self._update_from_snapshot(snapshot)

        self._controller.state.on_change(on_state_change)

    def _update_from_snapshot(self, snapshot: AppStateData) -> None:
        self._is_downloading = snapshot.state.name == "DOWNLOADING"
        
        if snapshot.state.name == "SEARCHING":
            self._is_searching = True
            self._set_status("Searching...")
        elif snapshot.state.name == "DOWNLOADING":
            self._is_searching = False
            if snapshot.active_downloads:
                active = snapshot.active_downloads[0]
                self._progress_var.set(active.progress)
                self._set_status(f"Downloading: {active.progress:.1f}%")
                self._progress_bar.itemconfig(self._progress_rect, fill=COLORS["primary"])
            else:
                self._set_status("Downloading...")
        elif snapshot.state.name == "ERROR":
            self._is_searching = False
            self._is_downloading = False
            self._set_status(f"Error: {snapshot.error_message}" if snapshot.error_message else "Error occurred")
            self._progress_var.set(0)
            self._progress_bar.itemconfig(self._progress_rect, fill=COLORS["error"])
        else:
            self._is_searching = False
            self._is_downloading = False
            self._set_status("Ready" if snapshot.state.name == "IDLE" else snapshot.state.name)
            if not snapshot.active_downloads:
                self._progress_var.set(0)
                self._progress_bar.itemconfig(self._progress_rect, fill=COLORS["border"])
        
        self._update_button_states()
        self._root.after(50, self._update_progress_bar)

        mode_is_debug = snapshot.mode.name == "DEBUG"
        if mode_is_debug != self._debug_mode:
            self._debug_mode = mode_is_debug
            self._debug_var.set(mode_is_debug)
            self._update_debug_visibility()

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

    def _update_button_states(self) -> None:
        is_busy = self._is_searching or self._is_downloading
        self._search_btn.configure(state="disabled" if is_busy else "normal")
        self._download_btn.configure(state="disabled" if is_busy or not self._selected_video else "normal")
        self._enqueue_btn.configure(state="disabled" if is_busy or not self._selected_video else "normal")

    def _on_search(self) -> None:
        query = self._search_var.get().strip()
        if not query or self._is_searching:
            return

        self._is_searching = True
        self._set_status("Searching...")
        self._update_button_states()
        self._controller.search(query)

    def _on_result_select(self, event: tk.Event) -> None:
        selection = self._results_tree.selection()
        if not selection:
            return

        results = self._controller.state.get_search_results()
        if not results:
            return

        try:
            index = self._results_tree.index(selection[0])
        except Exception:
            return

        if 0 <= index < len(results):
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

        self._is_downloading = True
        self._update_button_states()
        
        video.format = self._format_var.get()
        self._controller.download_now(video)
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
