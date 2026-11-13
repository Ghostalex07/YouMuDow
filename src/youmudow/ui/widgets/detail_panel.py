"""Detail panel widget for YouMuDow."""

import copy
import logging
import tkinter as tk

from youmudow.app.state import AppStateData
from youmudow.domain.models import DownloadOptions, Video
from youmudow.paths import cache_dir
from youmudow.services.thumbnail_cache import ThumbnailCache
from youmudow.services.thumbnail_loader import ThumbnailLoader
from youmudow.services.thumbnail_service import ThumbnailService
from youmudow.ui.protocols import MainWindowProtocol
from youmudow.ui.styles.constants import FONT, SPACING, _c, add_hover_effect
from youmudow.ui.typed import setattr_any
from youmudow.ui.widgets.components.thumbnail import photoimage_from_bytes
from youmudow.ui.widgets.options_panel import OptionsPanel
from youmudow.ui.widgets.queue_panel import QueuePanel

logger = logging.getLogger(__name__)


class DetailPanel(tk.Frame):
    """Video details, download actions and the options/queue sub-panels."""

    def __init__(
        self,
        parent: tk.Widget,
        main_window: MainWindowProtocol,
        thumbnail_loader: ThumbnailLoader | None = None,
    ) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._mw = main_window
        self._last_thumb_url: str | None = None
        self._thumbnail_loader = (
            thumbnail_loader
            if thumbnail_loader is not None
            else ThumbnailLoader(self._mw._root, ThumbnailCache(cache_dir()), ThumbnailService())
        )

        self.grid(
            row=1,
            column=1,
            sticky="nsew",
            padx=(0, SPACING["xl"]),
            pady=(0, SPACING["lg"]),
        )

        # Builds and packs the "OPTIONS" header first so the layout order of
        # this frame stays identical.
        self.options = OptionsPanel(self, main_window)

        self._build_thumbnail()
        self._build_info_rows()
        self._build_action_buttons()
        content_frame = main_window._main_content_frame
        if content_frame is None:
            content_frame = self
        self.queue = QueuePanel(content_frame, main_window)

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_thumbnail(self) -> None:
        self._thumbnail_label = tk.Label(
            self,
            text="[No thumbnail]",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            anchor="center",
            height=8,
        )
        self._thumbnail_label.pack(fill="x", pady=(0, SPACING["sm"]))

    def _build_info_rows(self) -> None:
        row_title = tk.Frame(self, bg=_c("surface"))
        setattr_any(row_title, "_bg_key", "surface")
        row_title.pack(fill="x", pady=(0, SPACING["xs"]))
        tk.Label(
            row_title,
            text="Title:",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._detail_title = tk.Label(
            row_title,
            text="-",
            bg=_c("surface"),
            fg=_c("text"),
            font=FONT["body"],
            anchor="w",
            wraplength=180,
        )
        self._detail_title.pack(side="left", fill="x", expand=True)

        row_uploader = tk.Frame(self, bg=_c("surface"))
        setattr_any(row_uploader, "_bg_key", "surface")
        row_uploader.pack(fill="x", pady=(0, SPACING["sm"]))
        tk.Label(
            row_uploader,
            text="Uploader:",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._detail_uploader = tk.Label(
            row_uploader, text="-", bg=_c("surface"), fg=_c("text"), font=FONT["body"], anchor="w"
        )
        self._detail_uploader.pack(side="left")

        tk.Frame(self, height=1, bg=_c("border")).pack(
            fill="x", pady=(SPACING["sm"], SPACING["md"])
        )

    def _build_action_buttons(self) -> None:
        self._download_btn = tk.Button(
            self,
            text="Download",
            bg=_c("primary"),
            fg="#FFFFFF",
            activebackground=_c("secondary"),
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            font=FONT["h3"],
            pady=8,
            command=lambda: self._mw._on_download_now(),
        )
        setattr_any(
            self._download_btn,
            "_theme",
            {
                "bg": "primary",
                "fg": "#FFFFFF",
                "activebg": "secondary",
                "activefg": "#FFFFFF",
            },
        )
        self._download_btn.pack(fill="x", pady=(0, SPACING["sm"]))
        add_hover_effect(self._download_btn, "secondary", "primary")

        btn_row = tk.Frame(self, bg=_c("bg"))
        btn_row.pack(fill="x", pady=(0, SPACING["md"]))

        self._open_folder_btn = tk.Button(
            btn_row,
            text="Open Folder",
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("hover"),
            activeforeground=_c("text"),
            relief="flat",
            bd=0,
            font=FONT["body"],
            pady=4,
            command=self._mw._on_open_folder,
        )
        setattr_any(
            self._open_folder_btn,
            "_theme",
            {
                "bg": "surface",
                "fg": "text",
                "activebg": "hover",
                "activefg": "text",
            },
        )
        self._open_folder_btn.pack(side="left", fill="x", expand=True, padx=(0, SPACING["xs"]))
        add_hover_effect(self._open_folder_btn, "hover", "surface")

        self._add_all_btn = tk.Button(
            btn_row,
            text="Add All",
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("hover"),
            activeforeground=_c("text"),
            relief="flat",
            bd=0,
            font=FONT["body"],
            pady=4,
            command=self._add_all_to_queue,
        )
        setattr_any(
            self._add_all_btn,
            "_theme",
            {
                "bg": "surface",
                "fg": "text",
                "activebg": "hover",
                "activefg": "text",
            },
        )
        self._add_all_btn.pack(side="left", fill="x", expand=True, padx=(SPACING["xs"], 0))
        add_hover_effect(self._add_all_btn, "hover", "surface")

        self._queue_toggle_btn = tk.Button(
            btn_row,
            text="Queue",
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("hover"),
            activeforeground=_c("text"),
            relief="flat",
            bd=0,
            font=FONT["body"],
            pady=4,
            command=self._toggle_queue_panel,
        )
        setattr_any(
            self._queue_toggle_btn,
            "_theme",
            {
                "bg": "surface",
                "fg": "text",
                "activebg": "hover",
                "activefg": "text",
            },
        )
        self._queue_toggle_btn.pack(side="left", fill="x", expand=True, padx=(SPACING["xs"], 0))
        add_hover_effect(self._queue_toggle_btn, "hover", "surface")

    # ------------------------------------------------------------------
    # Public surface used by MainWindow / ResultsCards
    # ------------------------------------------------------------------

    def update_detail_panel(self, video: Video) -> None:
        self._detail_title.configure(text=video.title or "-")
        self._detail_uploader.configure(text=video.uploader or "-")
        self._load_thumbnail(video)
        self.options.update_for_video(video)

    def get_current_options(self) -> DownloadOptions | None:
        return self.options.get_options()

    def apply_options_to_video(self, video: Video) -> None:
        self.options.apply_to_video(video)

    @property
    def queue_panel_visible(self) -> bool:
        return self.queue.visible

    def update_queue(self, snapshot: AppStateData | None = None) -> None:
        self.queue.update_display(snapshot)

    def enqueue_selected(self) -> None:
        cards = self._mw._results_cards
        if cards is None:
            return
        selected = cards.get_selected_videos()
        if selected:
            opts = self.get_current_options()
            if opts is None:
                return
            for video in selected:
                video.options = copy.copy(opts)
            self._mw._controller.enqueue_multiple(selected)
            self._mw._set_status(f"Added {len(selected)} to queue")
            return
        if cards.is_playlist and cards.playlist_videos:
            return
        selected_video = self._mw._selected_video
        if selected_video is None:
            return
        self.apply_options_to_video(selected_video)
        self._mw._controller.enqueue(selected_video)
        self._mw._set_status(f"Added to queue: {selected_video.title}")

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None:
        is_busy = is_searching or is_downloading
        has_video = self._mw._selected_video is not None
        self._download_btn.configure(state="disabled" if is_busy or not has_video else "normal")
        self._open_folder_btn.configure(state="normal")
        cards = self._mw._results_cards
        is_playlist = cards.is_playlist if cards is not None else False
        has_playlist = bool(cards.playlist_videos) if cards is not None else False
        self._add_all_btn.configure(state="normal" if is_playlist and has_playlist else "disabled")
        self.options.update_button_states(is_searching, is_downloading)

    # ------------------------------------------------------------------
    # Internal actions
    # ------------------------------------------------------------------

    def _load_thumbnail(self, video: Video) -> None:
        self._thumbnail_label.configure(text="[No thumbnail]")
        thumbnail_url = video.thumbnail
        self._last_thumb_url = thumbnail_url
        if not thumbnail_url:
            return
        self._thumbnail_loader.request(thumbnail_url, self._on_thumbnail_ready)

    def _on_thumbnail_ready(self, url: str, data: bytes | None) -> None:
        if self._last_thumb_url != url or data is None:
            return
        photo = photoimage_from_bytes(data, 240, 120)
        if photo is None:
            self._thumbnail_label.configure(text=f"[Thumbnail: {url}]")
            return
        self._tk_image = photo
        self._thumbnail_label.configure(image=photo, text="")

    def _add_all_to_queue(self) -> None:
        opts = self.get_current_options()
        if opts is None:
            return
        cards = self._mw._results_cards
        if cards is None:
            return
        videos = cards.playlist_videos
        for video in videos:
            video.options = copy.copy(opts)
        self._mw._controller.enqueue_multiple(videos)
        self._mw._set_status(f"Added {len(videos)} videos to queue")

    def _toggle_queue_panel(self) -> None:
        self.queue.toggle()
        self._queue_toggle_btn.configure(text="Queue")
