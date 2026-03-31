"""Reusable detail panel widget."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from youmudow.domain.models import Video


class DetailPanel(ttk.LabelFrame):
    """Reusable detail panel widget for displaying video information."""

    FORMATS = ("mp3", "mp4", "wav", "m4a", "flac", "ogg")

    def __init__(
        self,
        parent: tk.Widget,
        on_enqueue: Callable[[Video, str], None] | None = None,
        on_download: Callable[[Video, str], None] | None = None,
    ) -> None:
        super().__init__(parent, text="Details", padding=10)
        self._on_enqueue_callback = on_enqueue
        self._on_download_callback = on_download
        self._current_video: Video | None = None

        self.rowconfigure(3, weight=1)

        self._create_labels()
        self._create_format_selector()
        self._create_buttons()

    def _create_labels(self) -> None:
        ttk.Label(
            self, text="Title:", font=("TkDefaultFont", 10, "bold")
        ).grid(row=0, column=0, sticky="nw", pady=(0, 5))
        self._title_var = tk.StringVar(value="-")
        self._title_label = ttk.Label(self, textvariable=self._title_var, wraplength=200)
        self._title_label.grid(row=0, column=1, sticky="nw", padx=(5, 0), pady=(0, 5))

        ttk.Label(
            self, text="Uploader:", font=("TkDefaultFont", 10, "bold")
        ).grid(row=1, column=0, sticky="nw", pady=(0, 5))
        self._uploader_var = tk.StringVar(value="-")
        self._uploader_label = ttk.Label(self, textvariable=self._uploader_var)
        self._uploader_label.grid(row=1, column=1, sticky="nw", padx=(5, 0), pady=(0, 5))

        ttk.Label(
            self, text="Duration:", font=("TkDefaultFont", 10, "bold")
        ).grid(row=2, column=0, sticky="nw", pady=(0, 5))
        self._duration_var = tk.StringVar(value="-")
        self._duration_label = ttk.Label(self, textvariable=self._duration_var)
        self._duration_label.grid(row=2, column=1, sticky="nw", padx=(5, 0), pady=(0, 5))

    def _create_format_selector(self) -> None:
        ttk.Label(
            self, text="Format:", font=("TkDefaultFont", 10, "bold")
        ).grid(row=3, column=0, sticky="nw", pady=(0, 10))
        self._format_var = tk.StringVar(value="mp3")
        self._format_combo = ttk.Combobox(
            self,
            textvariable=self._format_var,
            values=self.FORMATS,
            state="readonly",
            width=10,
        )
        self._format_combo.grid(row=3, column=1, sticky="w", padx=(5, 0), pady=(0, 10))

    def _create_buttons(self) -> None:
        button_frame = ttk.Frame(self)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self._enqueue_btn = ttk.Button(
            button_frame,
            text="Add to Queue",
            command=self._handle_enqueue,
        )
        self._enqueue_btn.pack(side="left", padx=(0, 5))

        self._download_btn = ttk.Button(
            button_frame,
            text="Download Now",
            command=self._handle_download,
        )
        self._download_btn.pack(side="left")

    def set_video(self, video: Video | None) -> None:
        self._current_video = video
        if video:
            self._title_var.set(video.title or "-")
            self._uploader_var.set(video.uploader or "-")
            self._duration_var.set(self._format_duration(video.duration))
            self._format_var.set(video.format)
            self._set_buttons_enabled(True)
        else:
            self._title_var.set("-")
            self._uploader_var.set("-")
            self._duration_var.set("-")
            self._set_buttons_enabled(False)

    def get_selected_format(self) -> str:
        return self._format_var.get()

    def get_video(self) -> Video | None:
        return self._current_video

    def _handle_enqueue(self) -> None:
        if self._current_video and self._on_enqueue_callback:
            self._on_enqueue_callback(self._current_video, self._format_var.get())

    def _handle_download(self) -> None:
        if self._current_video and self._on_download_callback:
            self._on_download_callback(self._current_video, self._format_var.get())

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._enqueue_btn.configure(state=state)
        self._download_btn.configure(state=state)

    def _format_duration(self, seconds: int) -> str:
        if seconds == 0:
            return "-"
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
