"""Scrollable thumbnail-card list for YouMuDow search results."""

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from youmudow.domain.models import Video
from youmudow.services.thumbnail_loader import ThumbnailLoader
from youmudow.ui.styles.constants import FONT, SPACING, _c
from youmudow.ui.typed import setattr_any
from youmudow.ui.widgets.components.card import Card
from youmudow.ui.widgets.components.empty_state import EmptyState
from youmudow.ui.widgets.components.thumbnail import photoimage_from_bytes

logger = logging.getLogger(__name__)

_THUMB_WIDTH = 120
_THUMB_HEIGHT = 68
_INITIAL_BATCH = 12
_RETRY_DELAY_MS = 1500

# tkinter event.state modifier masks (same values across platforms).
_SHIFT = 0x0001
_CONTROL = 0x0004


class ResultsCards(tk.Frame):
    """A scrollable list of result cards replacing the old results table.

    Each card shows a lazily-loaded thumbnail plus title/uploader/duration.
    Selection supports single click and Ctrl/Shift multi-select; double-click
    fires ``on_double_click``, right-click fires ``on_open_in_browser``, and
    Up/Down/Return navigate the keyboard. ``get_selected()`` returns indices
    into the current video list.
    """

    def __init__(
        self,
        master: tk.Misc,
        state: object,
        thumbnail_loader: ThumbnailLoader,
        *,
        on_select: Callable[[], None] | None = None,
        on_double_click: Callable[[], None] | None = None,
        on_open_in_browser: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master, bg=_c("bg"))
        self._state = state
        self._loader = thumbnail_loader
        self._on_select = on_select
        self._on_double_click = on_double_click
        self._on_open_in_browser = on_open_in_browser

        self._videos: list[Video] = []
        self._is_playlist = False
        self._playlist_videos: list[Video] = []
        self._selected: set[int] = set()
        self._anchor: int | None = None
        self._cards: list[Card] = []
        self._thumb_labels: list[tk.Label] = []
        self._thumb_urls: dict[int, str] = {}
        self._retried: set[int] = set()
        self._retry_delay_ms = _RETRY_DELAY_MS
        self._thumb_batch = 0
        self._photo_refs: dict[int, object] = {}
        self._empty_state: EmptyState | None = None

        self.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(SPACING["xl"], SPACING["sm"]),
            pady=(0, SPACING["lg"]),
        )

        self._canvas = tk.Canvas(self, bg=_c("bg"), highlightthickness=0, bd=0)
        self._scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=_c("bg"))
        self._window_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._on_canvas_yscroll)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", lambda _: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind("<Button-5>", lambda _: self._canvas.yview_scroll(1, "units"))
        self.bind("<Up>", lambda _: self._on_up())
        self.bind("<Down>", lambda _: self._on_down())
        self.bind("<Return>", lambda _: self._on_enter())

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def update_results(self, videos: list[Video]) -> None:
        self._videos = list(videos)
        self._clear_children()
        if not videos:
            self._show_empty_state()
            return
        self._build_cards()
        self._request_thumbnails()

    def clear_results(self) -> None:
        self._videos = []
        self._clear_children()
        self._show_empty_state()

    def show_loading(self, message: str = "Searching...") -> None:
        self._videos = []
        self._clear_children()
        tk.Label(
            self._inner,
            text=message,
            bg=_c("bg"),
            fg=_c("text_secondary"),
            font=FONT["body"],
            pady=SPACING["xl"],
        ).pack(fill="x", expand=True)

    def select(self, index: int, notify: bool = True) -> None:
        if not self._videos:
            self._selected = set()
            self._anchor = None
        else:
            index = max(0, min(index, len(self._videos) - 1))
            self._selected = {index}
            self._anchor = index
        self._apply_selection_visuals()
        if notify and self._on_select:
            self._on_select()

    def get_selected(self) -> list[int]:
        return sorted(self._selected)

    def get_selected_videos(self) -> list[Video]:
        return [self._videos[i] for i in self.get_selected() if 0 <= i < len(self._videos)]

    def card_count(self) -> int:
        return len(self._cards)

    @property
    def is_playlist(self) -> bool:
        return self._is_playlist

    @is_playlist.setter
    def is_playlist(self, value: bool) -> None:
        self._is_playlist = value

    @property
    def playlist_videos(self) -> list[Video]:
        return self._playlist_videos

    @playlist_videos.setter
    def playlist_videos(self, value: list[Video]) -> None:
        self._playlist_videos = value

    # ------------------------------------------------------------------
    # Card construction
    # ------------------------------------------------------------------

    def _clear_children(self) -> None:
        for widget in self._inner.winfo_children():
            widget.destroy()
        self._cards = []
        self._thumb_labels = []
        self._selected = set()
        self._anchor = None
        self._thumb_urls = {}
        self._retried = set()
        self._thumb_batch = 0
        self._photo_refs = {}
        self._empty_state = None

    def _show_empty_state(self) -> None:
        self._empty_state = EmptyState(self._inner, message="No results yet")
        self._empty_state.pack(fill="x", expand=True, pady=SPACING["xl"])

    def _build_cards(self) -> None:
        for i, video in enumerate(self._videos):
            card, thumb = self._make_card(i, video)
            self._cards.append(card)
            self._thumb_labels.append(thumb)

    def _make_card(self, index: int, video: Video) -> tuple[Card, tk.Label]:
        card = Card(self._inner, padding=SPACING["sm"])
        card.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["sm"]))

        thumb = tk.Label(
            card,
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            text="",
        )
        thumb.pack(side="left", padx=(0, SPACING["sm"]), fill="y")

        info = tk.Frame(card, bg=_c("surface"))
        setattr_any(info, "_bg_key", "surface")
        info.pack(side="left", fill="both", expand=True)

        title = tk.Label(
            info,
            text=self._title_text(video),
            bg=_c("surface"),
            fg=_c("text"),
            font=FONT["body"],
            anchor="w",
        )
        title.pack(fill="x")

        meta = tk.Label(
            info,
            text=self._meta_text(video),
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            anchor="w",
        )
        meta.pack(fill="x")

        for widget in (card, thumb, info, title, meta):
            widget.bind("<Button-1>", self._make_click_handler(index))
            widget.bind("<Double-Button-1>", self._make_double_click_handler(index))
            widget.bind("<Button-3>", self._make_right_click_handler(index))
        return card, thumb

    def _make_click_handler(self, index: int) -> Callable[[tk.Event], None]:
        def handler(event: tk.Event) -> None:
            self._on_card_click(index, event)

        return handler

    def _make_double_click_handler(self, index: int) -> Callable[[tk.Event], None]:
        def handler(_event: tk.Event) -> None:
            self._on_card_double_click(index)

        return handler

    def _make_right_click_handler(self, index: int) -> Callable[[tk.Event], None]:
        def handler(_event: tk.Event) -> None:
            self._on_card_right_click(index)

        return handler

    def _title_text(self, video: Video) -> str:
        """Title as given, or a readable placeholder when the search returned none."""
        return video.title.strip() or "Untitled video"

    def _meta_text(self, video: Video) -> str:
        parts = []
        if video.uploader:
            parts.append(video.uploader)
        duration = video.format_duration()
        if duration and duration != "-":
            parts.append(duration)
        return "  ·  ".join(parts) if parts else "Metadata unavailable"

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_card_click(self, index: int, event: tk.Event) -> None:
        state = int(event.state)
        if state & _CONTROL:
            if index in self._selected:
                self._selected.discard(index)
            else:
                self._selected.add(index)
            self._anchor = index
        elif state & _SHIFT:
            if self._anchor is None:
                self._selected = {index}
            else:
                lo, hi = sorted((self._anchor, index))
                self._selected = set(range(lo, hi + 1))
        else:
            self._selected = {index}
            self._anchor = index
        self._apply_selection_visuals()
        self.focus_set()
        if self._on_select:
            self._on_select()

    def _on_card_double_click(self, index: int) -> None:
        self._selected = {index}
        self._anchor = index
        self._apply_selection_visuals()
        if self._on_double_click:
            self._on_double_click()

    def _on_card_right_click(self, index: int) -> None:
        if self._on_open_in_browser and 0 <= index < len(self._videos):
            self._on_open_in_browser(self._videos[index].url)

    def _apply_selection_visuals(self) -> None:
        for i, card in enumerate(self._cards):
            if i in self._selected:
                card.configure(highlightbackground=_c("primary"), highlightthickness=2)
                setattr_any(card, "_border_key", "primary")
            else:
                card.configure(highlightbackground=_c("border"), highlightthickness=1)
                setattr_any(card, "_border_key", "border")

    def _on_up(self) -> None:
        self._move_selection(-1)

    def _on_down(self) -> None:
        self._move_selection(1)

    def _move_selection(self, delta: int) -> None:
        if not self._videos:
            return
        if not self._selected:
            index = 0 if delta > 0 else len(self._videos) - 1
        else:
            index = max(0, min(min(self._selected) + delta, len(self._videos) - 1))
        self.select(index)
        self._ensure_visible(index)

    def _on_enter(self) -> None:
        if not self._selected:
            return
        if self._on_double_click:
            self._on_double_click()

    # ------------------------------------------------------------------
    # Thumbnails (lazy)
    # ------------------------------------------------------------------

    def _request_thumbnails(self) -> None:
        start = self._thumb_batch
        end = min(start + _INITIAL_BATCH, len(self._videos))
        for i in range(start, end):
            url = self._videos[i].thumbnail
            if not url:
                continue
            self._thumb_urls[i] = url
            self._loader.request(url, self._make_thumb_handler(i))
        self._thumb_batch = end

    def _make_thumb_handler(self, index: int) -> Callable[[str, bytes | None], None]:
        def handler(url: str, data: bytes | None) -> None:
            self._on_thumb_ready(index, url, data)

        return handler

    def _on_thumb_ready(self, index: int, url: str, data: bytes | None) -> None:
        if self._thumb_urls.get(index) != url:
            return
        if data is None:
            self._schedule_thumb_retry(index, url)
            return
        if index >= len(self._thumb_labels):
            return
        photo = photoimage_from_bytes(data, _THUMB_WIDTH, _THUMB_HEIGHT)
        if photo is None:
            return
        self._photo_refs[index] = photo
        self._thumb_labels[index].configure(image=photo, width=_THUMB_WIDTH, height=_THUMB_HEIGHT)

    def _schedule_thumb_retry(self, index: int, url: str) -> None:
        """Retry a failed download once, so a blip does not leave a blank card."""
        if index in self._retried:
            return
        self._retried.add(index)
        self.after(self._retry_delay_ms, lambda: self._retry_thumb(index, url))

    def _retry_thumb(self, index: int, url: str) -> None:
        if self._thumb_urls.get(index) != url:
            return
        self._loader.request(url, self._make_thumb_handler(index))

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

    def _on_canvas_yscroll(self, *args: object) -> None:
        self._scrollbar.set(*[str(arg) for arg in args])
        if self._canvas.yview()[1] >= 0.9:
            self._request_thumbnails()

    def _on_inner_configure(self, event: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.itemconfigure(self._window_id, width=event.width)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _ensure_visible(self, index: int) -> None:
        if not self._cards or index >= len(self._cards):
            return
        card = self._cards[index]
        y = card.winfo_y()
        total = max(1, self._inner.winfo_height())
        self._canvas.yview_moveto(max(0.0, min(1.0, y / total)))
