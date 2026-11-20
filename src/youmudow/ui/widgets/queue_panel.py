"""Download queue panel for YouMuDow."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from youmudow.app.state import AppStateData
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.error_causes import ErrorCause, summarize_failures
from youmudow.domain.models import Video
from youmudow.i18n import t
from youmudow.ui.protocols import MainWindowProtocol
from youmudow.ui.styles.constants import FONT, SPACING, _c
from youmudow.ui.typed import setattr_any
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


_CAUSE_LABELS: dict[ErrorCause, str] = {
    ErrorCause.PRIVATE: "private",
    ErrorCause.COOKIES: "needs cookies",
    ErrorCause.GEO: "geo-blocked",
    ErrorCause.NETWORK: "network error",
    ErrorCause.DISK: "disk error",
    ErrorCause.UNSUPPORTED: "unsupported",
    ErrorCause.OTHER: "other error",
}


class QueuePanel(tk.Frame):
    """The queue tree, its count label and its context menu."""

    def __init__(self, parent: tk.Widget, main_window: MainWindowProtocol) -> None:
        super().__init__(parent, bg=_c("surface"))
        setattr_any(self, "_bg_key", "surface")
        self._mw = main_window
        self._visible = False
        self._empty_state: EmptyState | None = None
        self._empty_shown = False
        self.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=SPACING["xl"], pady=(0, SPACING["lg"])
        )
        self._build_header()
        self._build_tree()
        self._build_problems()

    def _build_header(self) -> None:
        qheader = tk.Frame(self, bg=_c("surface"))
        setattr_any(qheader, "_bg_key", "surface")
        qheader.pack(fill="x", pady=(SPACING["sm"], SPACING["xs"]))
        tk.Label(
            qheader, text=t("QUEUE"), bg=_c("surface"), fg=_c("text_secondary"), font=FONT["label"]
        ).pack(side="left", padx=SPACING["sm"])
        self._queue_count_label = tk.Label(
            qheader, text="0 queued", bg=_c("surface"), fg=_c("text_secondary"), font=FONT["small"]
        )
        self._queue_count_label.pack(side="right", padx=SPACING["sm"])
        self._pause_btn = tk.Button(
            qheader,
            text=t("Pause"),
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("hover"),
            activeforeground=_c("text"),
            relief="flat",
            bd=0,
            font=FONT["label"],
            command=self._toggle_pause,
        )
        self._pause_btn.pack(side="right", padx=SPACING["xs"])

    def _build_tree(self) -> None:
        qcols = ("status", "title", "progress")
        self._queue_tree = ttk.Treeview(
            self, columns=qcols, show="headings", height=5, style="Modern.Treeview"
        )
        self._queue_tree.heading("status", text=t("STATUS"))
        self._queue_tree.heading("title", text=t("TITLE"))
        self._queue_tree.heading("progress", text=t("PROGRESS"))
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
        self._queue_tree.bind("<Delete>", self._on_remove_selected)
        self._queue_tree.bind("<ButtonPress-1>", self._on_drag_start)
        self._queue_tree.bind("<B1-Motion>", self._on_drag_motion)
        self._queue_tree.bind("<ButtonRelease-1>", self._on_drag_end)

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

    def _build_problems(self) -> None:
        self._problems = tk.Frame(self, bg=_c("surface"))
        setattr_any(self, "_bg_key", "surface")
        self._problems_label = tk.Label(
            self._problems,
            text="",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
        )
        self._problems_label.pack(side="left")
        self._retry_failed_btn = tk.Button(
            self._problems,
            text=t("Retry failed"),
            command=self._on_retry_failed,
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("hover"),
            activeforeground=_c("text"),
            relief="flat",
            font=FONT["small"],
            cursor="hand2",
        )
        self._retry_failed_btn.pack(side="right")

    def _on_retry_failed(self) -> None:
        self._mw._on_retry_failed()

    def _update_problems(self, snapshot: AppStateData) -> None:
        counts = summarize_failures(snapshot.failed_downloads)
        if not counts:
            self._problems.pack_forget()
            return
        self._problems_label.configure(
            text=" · ".join(f"{count} {t(_CAUSE_LABELS[cause])}" for cause, count in counts)
        )
        if not self._problems.winfo_manager():
            self._problems.pack(fill="x", pady=(SPACING["xs"], 0))

    def update_display(self, snapshot: AppStateData | None = None) -> None:
        if snapshot is None:
            snapshot = self._mw._controller.state.get_snapshot()

        self._update_problems(snapshot)
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

    def _video_for_item(self, item: str) -> Video | None:
        snapshot = self._mw._controller.state.get_snapshot()
        all_videos = (
            list(snapshot.queue)
            + list(snapshot.active_downloads)
            + list(snapshot.completed_downloads)
            + list(snapshot.failed_downloads)
        )
        entry_id = item[1:].split("-", 1)[0]
        return next((v for v in all_videos if str(v.queue_id) == entry_id), None)

    def _selected_video(self) -> Video | None:
        selection = self._queue_tree.selection()
        if not selection:
            return None
        return self._video_for_item(selection[0])

    def _toggle_pause(self) -> None:
        controller = self._mw._controller
        if controller.downloads_paused:
            controller.resume_downloads()
        else:
            controller.pause_downloads()
        self._sync_pause_button()

    def _sync_pause_button(self) -> None:
        paused = self._mw._controller.downloads_paused
        self._pause_btn.configure(text=t("Resume") if paused else t("Pause"))

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_item = self._queue_tree.identify_row(event.y)

    def _on_drag_motion(self, event: tk.Event) -> None:
        item = getattr(self, "_drag_item", "")
        if not item:
            return
        target = self._queue_tree.identify_row(event.y)
        if target:
            self._queue_tree.move(item, "", self._queue_tree.index(target))

    def _on_drag_end(self, event: tk.Event) -> None:
        item = getattr(self, "_drag_item", "")
        self._drag_item = ""
        if not item:
            return
        video = self._video_for_item(item)
        if video is None or video.status != DownloadStatus.QUEUED:
            return
        self._mw._controller.move_in_queue(video, self._queue_tree.index(item))

    def _on_remove_selected(self, _event: tk.Event | None = None) -> None:
        """Delete key: drop the selected row from the queue."""
        video = self._selected_video()
        if video is not None:
            self._mw._controller.remove_from_queue(video)

    def _on_right_click(self, event: tk.Event) -> None:
        item = self._queue_tree.identify_row(event.y)
        if not item:
            return
        self._queue_tree.selection_set(item)
        video = self._selected_video()
        if not video:
            return
        menu = tk.Menu(self._mw._root, tearoff=0, bg=_c("surface"), fg=_c("text"))
        menu.add_command(
            label=t("Remove from queue"),
            command=lambda: self._mw._controller.remove_from_queue(video),
        )
        menu.add_command(label=t("Open in browser"), command=lambda: webbrowser.open(video.url))
        menu.tk_popup(event.x_root, event.y_root)
