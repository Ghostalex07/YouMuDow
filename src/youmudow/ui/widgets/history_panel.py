"""History panel widget for YouMuDow."""

import logging
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from youmudow.domain.models import HistoryEntry
from youmudow.ui.styles.constants import FONT, SPACING, _c

logger = logging.getLogger(__name__)


class HistoryPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, main_window: object) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._mw = main_window
        self._all_entries: list[HistoryEntry] = []
        self._filtered: list[HistoryEntry] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        search_frame = tk.Frame(self, bg=_c("bg"))
        search_frame.pack(fill="x", padx=SPACING["md"], pady=(SPACING["md"], SPACING["xs"]))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_filter_change)
        search_entry = tk.Entry(
            search_frame,
            textvariable=self._search_var,
            bg=_c("surface"),
            fg=_c("text"),
            insertbackground=_c("text"),
            font=FONT["body"],
            relief="flat",
            bd=0,
        )
        search_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=SPACING["sm"])

        clear_btn = tk.Button(
            search_frame,
            text="Clear History",
            bg=_c("error"),
            fg="#FFFFFF",
            activebackground=_c("warning"),
            activeforeground="#000000",
            relief="flat",
            bd=0,
            font=FONT["label"],
            command=self._on_clear_history,
        )
        clear_btn.pack(side="right", padx=(SPACING["sm"], 0))

        tree_frame = tk.Frame(self, bg=_c("bg"))
        tree_frame.pack(fill="both", expand=True, padx=SPACING["md"], pady=(0, SPACING["md"]))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = ("title", "format", "date", "size")
        self._tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            style="Modern.Treeview",
        )
        self._tree.heading("title", text="TITLE")
        self._tree.heading("format", text="FORMAT")
        self._tree.heading("date", text="DATE")
        self._tree.heading("size", text="SIZE")
        self._tree.column("title", width=320, minwidth=150)
        self._tree.column("format", width=70, minwidth=50)
        self._tree.column("date", width=140, minwidth=100)
        self._tree.column("size", width=80, minwidth=60)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<Button-3>", self._on_right_click)
        self._tree.bind("<Double-Button-1>", self._on_redownload)

    def refresh(self) -> None:
        if not hasattr(self._mw, "_controller"):
            return
        self._all_entries = self._mw._controller.history.get_all()
        self._apply_filter(self._search_var.get())

    def _apply_filter(self, query: str) -> None:
        q = query.strip().lower()
        if q:
            self._filtered = [
                e for e in self._all_entries if q in e.title.lower() or q in e.uploader.lower()
            ]
        else:
            self._filtered = list(self._all_entries)
        self._populate(self._filtered)

    def _populate(self, entries: list[HistoryEntry]) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for entry in entries:
            self._tree.insert(
                "",
                "end",
                values=(
                    entry.title,
                    entry.file_format.upper(),
                    entry.format_date(),
                    entry.format_size() or "-",
                ),
            )
        if not entries:
            self._tree.insert("", "end", values=("No history yet", "", "", ""))

    def _on_filter_change(self, *_) -> None:
        self._apply_filter(self._search_var.get())

    def _get_selected_entry(self) -> HistoryEntry | None:
        selection = self._tree.selection()
        if not selection:
            return None
        try:
            index = self._tree.index(selection[0])
            if 0 <= index < len(self._filtered):
                return self._filtered[index]
        except tk.TclError as e:
            logger.debug("Could not resolve selected history entry: %s", e)
        return None

    def _on_right_click(self, event: tk.Event) -> None:
        item = self._tree.identify_row(event.y)
        if not item:
            return
        self._tree.selection_set(item)
        entry = self._get_selected_entry()
        if not entry:
            return
        menu = tk.Menu(self._mw._root, tearoff=0, bg=_c("surface"), fg=_c("text"))
        menu.add_command(label="↺  Re-download", command=self._on_redownload)
        menu.add_command(label="🌐  Open in browser", command=lambda: webbrowser.open(entry.url))
        menu.add_separator()
        menu.add_command(label="🗑  Remove from history", command=self._on_remove)
        menu.tk_popup(event.x_root, event.y_root)

    def _on_redownload(self, _event: tk.Event | None = None) -> None:
        entry = self._get_selected_entry()
        if not entry:
            return
        self._mw._search_bar.search_var.set(entry.url)
        self._mw._on_search()
        if hasattr(self._mw, "_notebook"):
            self._mw._notebook.select(0)

    def _on_remove(self) -> None:
        entry = self._get_selected_entry()
        if not entry:
            return
        self._mw._controller.history.remove(entry)
        self.refresh()

    def _on_clear_history(self) -> None:
        if messagebox.askyesno("Clear History", "Delete all download history?"):
            self._mw._controller.history.clear()
            self.refresh()
