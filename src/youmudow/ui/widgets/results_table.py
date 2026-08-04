"""Results table widget for YouMuDow."""

import logging
import tkinter as tk
import webbrowser
from tkinter import ttk

from youmudow.domain.models import Video
from youmudow.ui.styles.constants import FONT, SPACING, _c

logger = logging.getLogger(__name__)


class ResultsTable(tk.Frame):
    def __init__(self, parent: tk.Widget, main_window: object) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._mw = main_window
        self._playlist_videos: list[Video] = []
        self._is_playlist = False

        self.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(SPACING["md"], SPACING["sm"]),
            pady=(0, SPACING["md"]),
        )
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        columns = ("title", "uploader", "duration")
        self._results_tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="Modern.Treeview",
        )
        self._results_tree.heading("title", text="TITLE")
        self._results_tree.heading("uploader", text="UPLOADER")
        self._results_tree.heading("duration", text="DURATION")
        self._results_tree.column("title", width=350)
        self._results_tree.column("uploader", width=180)
        self._results_tree.column("duration", width=80)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._results_tree.yview)
        self._results_tree.configure(yscrollcommand=scrollbar.set)

        self._results_tree.grid(row=0, column=0, sticky="nsew", padx=(0, SPACING["xs"]))
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._results_tree.bind("<<TreeviewSelect>>", self._on_result_select)
        self._results_tree.bind("<Double-Button-1>", lambda _: self._mw._on_download_now())
        self._results_tree.bind("<Button-3>", self._on_open_in_browser)

        self._style_treeview()

    @property
    def results_tree(self) -> ttk.Treeview:
        return self._results_tree

    @property
    def playlist_videos(self) -> list[Video]:
        return self._playlist_videos

    @playlist_videos.setter
    def playlist_videos(self, videos: list[Video]) -> None:
        self._playlist_videos = videos

    @property
    def is_playlist(self) -> bool:
        return self._is_playlist

    @is_playlist.setter
    def is_playlist(self, val: bool) -> None:
        self._is_playlist = val

    def _style_treeview(self) -> None:
        style = ttk.Style()
        style.configure(
            "Modern.Treeview",
            background=_c("surface"),
            foreground=_c("text"),
            fieldbackground=_c("surface"),
            borderwidth=0,
            rowheight=44,
            font=FONT["body"],
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=_c("bg"),
            foreground=_c("text_secondary"),
            borderwidth=0,
            padding=(12, 8),
            font=FONT["label"],
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", _c("primary"))],
            foreground=[("selected", "#FFFFFF")],
        )

    def update_results(self, results: list[Video]) -> None:
        for item in self._results_tree.get_children():
            self._results_tree.delete(item)

        for video in results:
            duration = video.format_duration()
            self._results_tree.insert("", "end", values=(video.title, video.uploader, duration))

        self._playlist_videos = results

        if results:
            if self._is_playlist and len(results) > 1:
                self._mw._set_status(
                    f"Found {len(results)} videos - 'Add to Queue' adds all to queue"
                )
            elif len(results) > 1:
                self._mw._set_status(f"Found {len(results)} results - select one to download")
            else:
                self._mw._set_status(f"Found: {results[0].title}")

    def get_selected_videos(self) -> list[Video]:
        selected_ids = self._results_tree.selection()
        if not selected_ids:
            return []
        results = self._mw._controller.state.get_search_results()
        if not results:
            return []
        videos = []
        for item_id in selected_ids:
            try:
                index = self._results_tree.index(item_id)
                if 0 <= index < len(results):
                    videos.append(results[index])
            except tk.TclError as e:
                logger.debug("Could not resolve selected video: %s", e)
                continue
        return videos

    def _on_result_select(self, event: tk.Event) -> None:
        selection = self._results_tree.selection()
        if not selection:
            return
        results = self._mw._controller.state.get_search_results()
        if not results:
            return
        try:
            index = self._results_tree.index(selection[0])
        except tk.TclError as e:
            logger.debug("Could not resolve selection: %s", e)
            return
        if 0 <= index < len(results):
            self._mw._selected_video = results[index]
            self._mw._detail_panel.update_detail_panel(self._mw._selected_video)
            self._mw._update_button_states()
            if len(selection) > 1:
                self._mw._set_status(f"{len(selection)} videos selected")

    def _on_open_in_browser(self, event: tk.Event) -> None:
        item_id = self._results_tree.identify_row(event.y)
        if not item_id:
            return
        results = self._mw._controller.state.get_search_results()
        if not results:
            return
        try:
            index = self._results_tree.index(item_id)
        except tk.TclError as e:
            logger.debug("Could not resolve row index: %s", e)
            return
        if 0 <= index < len(results):
            webbrowser.open(results[index].url)

    def clear_results(self) -> None:
        for item in self._results_tree.get_children():
            self._results_tree.delete(item)
