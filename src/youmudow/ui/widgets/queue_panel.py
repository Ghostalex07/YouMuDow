"""Download queue panel for YouMuDow."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from youmudow.app.state import AppStateData
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video
from youmudow.ui.styles.constants import FONT, SPACING, _c
from youmudow.ui.widgets.components.empty_state import EmptyState

_STATUS_DISPLAY: dict[DownloadStatus, tuple[str, str]] = {
    DownloadStatus.READY: ("Queued", "-"),
    DownloadStatus.QUEUED: ("Queued", "-"),
    DownloadStatus.DOWNLOADING: ("Downloading", ""),
    DownloadStatus.DONE: ("Completed", "100%"),
    DownloadStatus.ERROR: ("Failed", "Failed"),
    DownloadStatus.CANCELLED: ("Cancelled", "Cancelled"),
}


def _queue_row(video: Video) -> tuple[str, str, str]:
    """Status label, title and progress for one queue panel row."""
    label, progress = _STATUS_DISPLAY.get(video.status, ("Queued", "-"))
    if not progress:
        progress = f"{video.progress:.0f}%"
    return (label, video.title[:60], progress)


def _queue_iid(video: Video) -> str:
    """Tree item id for a queue entry, unique per entry rather than per URL."""
    return f"q{video.queue_id}"


class QueuePanel(tk.Frame):
    """The queue tree, its count label and its context menu."""

    def __init__(self, parent: tk.Widget, main_window: object) -> None:
        super().__init__(parent, bg=_c("surface"))
        self._bg_key = "surface"
        self._mw = main_window
        self._visible = False
        self._empty_state: EmptyState | None = None
        self._empty_shown = False
        self.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=SPACING["xl"], pady=(0, SPACING["lg"])
        )
        self._build_header()
        self._build_tree()

    def _build_header(self) -> None:
        qheader = tk.Frame(self, bg=_c("surface"))
        qheader._bg_key = "surface"
        qheader.pack(fill="x", pady=(SPACING["sm"], SPACING["xs"]))
        tk.Label(
            qheader, text="QUEUE", bg=_c("surface"), fg=_c("text_secondary"), font=FONT["label"]
        ).pack(side="left", padx=SPACING["sm"])
        self._queue_count_label = tk.Label(
            qheader, text="0 queued", bg=_c("surface"), fg=_c("text_secondary"), font=FONT["small"]
        )
        self._queue_count_label.pack(side="right", padx=SPACING["sm"])

    def _build_tree(self) -> None:
        qcols = ("status", "title", "progress")
        self._queue_tree = ttk.Treeview(
            self, columns=qcols, show="headings", height=5, style="Modern.Treeview"
        )
        self._queue_tree.heading("status", text="STATUS")
        self._queue_tree.heading("title", text="TITLE")
        self._queue_tree.heading("progress", text="PROGRESS")
        self._queue_tree.column("status", width=100)
        self._queue_tree.column("title", width=300)
        self._queue_tree.column("progress", width=80)

        qscroll = ttk.Scrollbar(self, orient="vertical", command=self._queue_tree.yview)
        self._queue_tree.configure(yscrollcommand=qscroll.set)
        self._queue_tree.pack(
            side="left", fill="both", expand=True, padx=(SPACING["sm"], 0), pady=(0, SPACING["sm"])
        )
        qscroll.pack(side="right", fill="y", pady=(0, SPACING["sm"]), padx=(0, SPACING["sm"]))
        self._qscroll = qscroll
        self._queue_tree.bind("<Button-3>", self._on_right_click)

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if value:
            self.show()
        else:
            self.hide()

    def show(self) -> None:
        self.grid()
        self._visible = True

    def hide(self) -> None:
        self.grid_remove()
        self._visible = False

    def toggle(self) -> None:
        """Show or hide the panel, refreshing its rows when it appears."""
        if self._visible:
            self.hide()
        else:
            self.show()
            self.update_display()

    def update_display(self, snapshot: AppStateData | None = None) -> None:
        if snapshot is None:
            snapshot = self._mw._controller.state.get_snapshot()

        buckets = (
            snapshot.queue,
            snapshot.active_downloads,
            snapshot.completed_downloads,
            snapshot.failed_downloads,
        )
        desired: list[tuple[str, tuple]] = []
        used_iids: set[str] = set()
        for bucket in buckets:
            for v in bucket:
                iid = _queue_iid(v)
                if iid in used_iids:
                    iid = f"{iid}-{len(used_iids)}"
                used_iids.add(iid)
                desired.append((iid, _queue_row(v)))

        desired_iids = set(used_iids)
        existing_iids = set(self._queue_tree.get_children(""))

        for iid in existing_iids - desired_iids:
            self._queue_tree.delete(iid)

        for iid, values in desired:
            if iid in existing_iids:
                current = self._queue_tree.item(iid, "values")
                if current != values:
                    self._queue_tree.item(iid, values=values)
            else:
                self._queue_tree.insert("", "end", iid=iid, values=values)
                existing_iids.add(iid)

        for i, (iid, _) in enumerate(desired):
            self._queue_tree.move(iid, "", i)

        total = sum(len(bucket) for bucket in buckets)
        self._queue_count_label.configure(text=f"{total} items")

        empty = total == 0
        if empty != self._empty_shown:
            if empty:
                self._queue_tree.pack_forget()
                self._qscroll.pack_forget()
                if self._empty_state is None:
                    self._empty_state = EmptyState(self, message="Queue is empty")
                self._empty_state.pack(fill="x", pady=(SPACING["sm"], SPACING["sm"]))
            else:
                if self._empty_state is not None:
                    self._empty_state.pack_forget()
                self._queue_tree.pack(
                    side="left",
                    fill="both",
                    expand=True,
                    padx=(SPACING["sm"], 0),
                    pady=(0, SPACING["sm"]),
                )
                self._qscroll.pack(
                    side="right", fill="y", pady=(0, SPACING["sm"]), padx=(0, SPACING["sm"])
                )
            self._empty_shown = empty

    def _on_right_click(self, event: tk.Event) -> None:
        item = self._queue_tree.identify_row(event.y)
        if not item:
            return
        self._queue_tree.selection_set(item)
        snapshot = self._mw._controller.state.get_snapshot()
        all_videos = (
            list(snapshot.queue)
            + list(snapshot.active_downloads)
            + list(snapshot.completed_downloads)
            + list(snapshot.failed_downloads)
        )
        entry_id = item[1:].split("-", 1)[0]
        video = next((v for v in all_videos if str(v.queue_id) == entry_id), None)
        if not video:
            return
        menu = tk.Menu(self._mw._root, tearoff=0, bg=_c("surface"), fg=_c("text"))
        menu.add_command(
            label="Remove from queue", command=lambda: self._mw._controller.remove_from_queue(video)
        )
        menu.add_command(label="Open in browser", command=lambda: webbrowser.open(video.url))
        menu.tk_popup(event.x_root, event.y_root)
