"""Reusable results table widget."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from youmudow.domain.models import Video


class ResultsTable(ttk.Frame):
    """Reusable table widget for displaying search results."""

    COLUMNS = ("title", "uploader", "duration")
    HEADINGS = ("Title", "Uploader", "Duration")

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Callable[[int], None] | None = None,
        on_double_click: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_select_callback = on_select
        self._on_double_click_callback = on_double_click
        self._items: list[Video] = []

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            self,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
        )
        self._setup_columns()
        self._setup_scrollbar()
        self._setup_events()

    def _setup_columns(self) -> None:
        widths = {"title": 300, "uploader": 150, "duration": 80}
        for col, heading in zip(self.COLUMNS, self.HEADINGS):
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=widths.get(col, 150))

    def _setup_scrollbar(self) -> None:
        scrollbar = ttk.Scrollbar(self, orient="vertical")
        scrollbar.configure(command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _setup_events(self) -> None:
        self._tree.bind("<<TreeviewSelect>>", self._handle_select)
        self._tree.bind("<Double-Button-1>", self._handle_double_click)

    def _handle_select(self, event: tk.Event) -> None:
        if self._on_select_callback:
            index = self._tree.index(self._tree.selection()[0]) if self._tree.selection() else -1
            if index >= 0:
                self._on_select_callback(index)

    def _handle_double_click(self, event: tk.Event) -> None:
        if self._on_double_click_callback:
            selection = self._tree.selection()
            if selection:
                index = self._tree.index(selection[0])
                self._on_double_click_callback(index)

    def set_results(self, videos: list[Video]) -> None:
        self._items = videos
        self.clear()
        for video in videos:
            duration = self._format_duration(video.duration)
            self._tree.insert("", "end", values=(video.title, video.uploader, duration))

    def get_selected_index(self) -> int:
        selection = self._tree.selection()
        if selection:
            return self._tree.index(selection[0])
        return -1

    def get_selected_video(self) -> Video | None:
        index = self.get_selected_index()
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def clear(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

    def _format_duration(self, seconds: int) -> str:
        if seconds == 0:
            return "-"
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def set_column_width(self, column: str, width: int) -> None:
        if column in self.COLUMNS:
            self._tree.column(column, width=width)
