"""Reusable search bar widget."""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class SearchBar(ttk.Frame):
    """Reusable search bar widget with entry and button."""

    def __init__(
        self,
        parent: tk.Widget,
        placeholder: str = "Search...",
        on_search: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_search_callback = on_search
        self._placeholder = placeholder

        self.columnconfigure(0, weight=1)

        self._var = tk.StringVar()
        self._entry = ttk.Entry(
            self,
            textvariable=self._var,
            font=("TkDefaultFont", 12),
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._entry.bind("<Return>", lambda _: self._trigger_search())
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)

        self._button = ttk.Button(
            self,
            text="Search",
            command=self._trigger_search,
        )
        self._button.grid(row=0, column=1)

        self._set_placeholder()

    def _set_placeholder(self) -> None:
        self._entry.configure(style="Placeholder.TEntry")

    def _on_focus_in(self, event: tk.Event) -> None:
        if self._var.get() == self._placeholder:
            self._var.set("")
            self._entry.configure(style="TEntry")

    def _on_focus_out(self, event: tk.Event) -> None:
        if not self._var.get():
            self._set_placeholder()

    def _trigger_search(self) -> None:
        query = self._var.get().strip()
        if not query or query == self._placeholder:
            return
        if self._on_search_callback:
            self._on_search_callback(query)

    def get_query(self) -> str:
        return self._var.get().strip()

    def set_query(self, query: str) -> None:
        self._var.set(query)

    def clear(self) -> None:
        self._var.set("")
        self._set_placeholder()

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._entry.configure(state=state)
        self._button.configure(state=state)

    def set_searching(self, searching: bool) -> None:
        self.set_enabled(not searching)
        if searching:
            self._button.configure(text="Searching...")
        else:
            self._button.configure(text="Search")
