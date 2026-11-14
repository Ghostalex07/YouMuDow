"""Download options panel for YouMuDow.

The panel builds its controls directly inside the host frame (instead of being
a container widget itself) so ``DetailPanel`` keeps full control over the
layout order. It owns the Tk variables backing every option.
"""

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, ttk
from typing import Any, Literal

from youmudow.adapters.browser_profiles import get_all_browser_profiles, get_available_browsers
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video
from youmudow.domain.validators import (
    SUPPORTED_FORMATS,
    SUPPORTED_QUALITIES,
    is_valid_rate_limit,
)
from youmudow.ui.protocols import MainWindowProtocol
from youmudow.ui.styles.constants import FONT, SPACING, _c, add_hover_effect
from youmudow.ui.typed import setattr_any

logger = logging.getLogger(__name__)


class OptionsPanel:
    """Download options: format, quality, auth, rate limit and concurrency.

    Widgets are parented to ``parent`` rather than to this object; the object
    only owns them and the Tk variables behind them. That keeps the pixel
    layout of the detail panel unchanged.
    """

    def __init__(self, parent: tk.Widget, main_window: MainWindowProtocol) -> None:
        self._mw = main_window
        self._available_browsers: list[str] | None = None
        self._browser_profiles_cache: dict | None = None
        self._build_header(parent)
        self._build_retry_button(parent)
        self._build_options(parent)
        self._on_subtitles_toggle()

    # ------------------------------------------------------------------
    # Browser detection (memoized per instance)
    # ------------------------------------------------------------------

    def _browser_options(self) -> list[str]:
        if self._available_browsers is None:
            self._available_browsers = get_available_browsers()
        return self._available_browsers

    def _browser_profiles(self) -> dict:
        if self._browser_profiles_cache is None:
            self._browser_profiles_cache = get_all_browser_profiles()
        return self._browser_profiles_cache

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_header(self, parent: tk.Widget) -> None:
        header_frame = tk.Frame(parent, bg=_c("bg"))
        header_frame.pack(fill="x", pady=(0, SPACING["xs"]))

        self._detail_toggle_btn = tk.Button(
            header_frame,
            text="OPTIONS",
            bg=_c("bg"),
            fg=_c("text_secondary"),
            font=FONT["label"],
            relief="flat",
            bd=0,
            command=self.toggle,
        )
        setattr_any(
            self._detail_toggle_btn,
            "_theme",
            {"bg": "bg", "fg": "text_secondary", "activebg": "hover", "activefg": "text"},
        )
        self._detail_toggle_btn.pack(side="left")
        add_hover_effect(self._detail_toggle_btn, "hover", "bg", _c("text"), _c("text_secondary"))

    def _build_retry_button(self, parent: tk.Widget) -> None:
        self._retry_btn = tk.Button(
            parent,
            text="Retry",
            bg=_c("warning"),
            fg="#000000",
            activebackground=_c("warning"),
            activeforeground="#000000",
            relief="flat",
            bd=0,
            font=FONT["body"],
            pady=6,
            command=self._on_retry_download,
        )
        setattr_any(
            self._retry_btn,
            "_theme",
            {
                "bg": "warning",
                "fg": "#000000",
                "activebg": "warning",
                "activefg": "#000000",
            },
        )

    def _build_options(self, parent: tk.Widget) -> None:
        self._options_frame = tk.Frame(parent, bg=_c("surface"))
        setattr_any(self._options_frame, "_bg_key", "surface")
        self._rows = self._build_rows()
        self._rows_count = len(self._rows)

    # ------------------------------------------------------------------
    # Row and control builders
    # ------------------------------------------------------------------

    def _row(self, label: str | None = None, *, pady: tuple = (0, SPACING["md"])) -> tk.Frame:
        row = tk.Frame(self._options_frame, bg=_c("surface"))
        setattr_any(row, "_bg_key", "surface")
        row.pack(fill="x", pady=pady)
        if label is not None:
            self._label(row, label, width=10)
        return row

    def _label(
        self,
        parent: tk.Widget,
        text: str,
        *,
        width: int | None = None,
        padx: tuple = (0, 0),
    ) -> tk.Label:
        label = tk.Label(
            parent,
            text=text,
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            anchor="w",
        )
        if width is not None:
            label.configure(width=width)
        label.pack(side="left", padx=padx)
        return label

    def _check(
        self,
        parent: tk.Widget,
        var: tk.Variable,
        text: str,
        *,
        command: Callable[[], Any] | None = None,
        font=FONT["body"],
        fg=None,
        padx: tuple = (0, 0),
    ) -> tk.Checkbutton:
        if fg is None:
            fg = _c("text")
        check = tk.Checkbutton(
            parent,
            text=text,
            variable=var,
            bg=_c("surface"),
            fg=fg,
            activebackground=_c("surface"),
            activeforeground=_c("text"),
            selectcolor=_c("surface"),
            relief="flat",
            font=font,
        )
        if command is not None:
            check.configure(command=command)
        check.pack(side="left", padx=padx)
        return check

    def _combo(
        self,
        parent: tk.Widget,
        var: tk.Variable,
        values: list[str],
        width: int,
        *,
        font=FONT["body"],
        padx: tuple = (0, 0),
    ) -> ttk.Combobox:
        combo = ttk.Combobox(
            parent,
            textvariable=var,
            values=values,
            state="readonly",
            width=width,
            font=font,
        )
        combo.pack(side="left", padx=padx)
        return combo

    def _entry(
        self,
        parent: tk.Widget,
        var: tk.Variable,
        width: int,
        *,
        padx: tuple = (0, 0),
    ) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=var,
            bg=_c("input_bg"),
            fg=_c("text"),
            relief="flat",
            font=FONT["small"],
            width=width,
        )
        entry.pack(side="left", padx=padx)
        return entry

    def _spinbox(
        self,
        parent: tk.Widget,
        var: tk.Variable,
        *,
        from_: int,
        to: int,
        command: Callable[[], Any] | None = None,
    ) -> tk.Spinbox:
        spin = tk.Spinbox(
            parent,
            from_=from_,
            to=to,
            textvariable=var,
            state="readonly",
            bg=_c("input_bg"),
            fg=_c("text"),
            relief="flat",
            width=3,
            font=FONT["body"],
        )
        if command is not None:
            spin.configure(command=command)
        spin.pack(side="left", padx=(0, SPACING["sm"]))
        return spin

    def _build_rows(self) -> list[tk.Widget]:
        return [
            self._build_format_row(),
            self._build_quality_row(),
            self._build_concurrent_row(),
            self._build_subtitles_row(),
            self._build_auth_row(),
            self._build_extra_row(),
        ]

    def _build_format_row(self) -> tk.Frame:
        self._format_var = tk.StringVar(value="mp3")
        row = self._row("Format:", pady=(SPACING["sm"], SPACING["md"]))
        self._combo(row, self._format_var, sorted(SUPPORTED_FORMATS), 8, padx=(0, SPACING["sm"]))
        return row

    def _build_quality_row(self) -> tk.Frame:
        self._quality_var = tk.StringVar(value="best")
        row = self._row("Quality:")
        self._combo(row, self._quality_var, sorted(SUPPORTED_QUALITIES), 10)
        return row

    def _build_concurrent_row(self) -> tk.Frame:
        self._concurrent_var = tk.IntVar(value=1)
        row = self._row("Concurrent:")
        self._spinbox(row, self._concurrent_var, from_=1, to=4, command=self._on_concurrent_change)
        self._label(row, "(1-4)")
        return row

    def _build_subtitles_row(self) -> tk.Frame:
        self._subtitles_var = tk.BooleanVar(value=False)
        row = self._row()
        self._check(row, self._subtitles_var, "Subtitles", command=self._on_subtitles_toggle)
        self._subtitle_lang_var = tk.StringVar(value="en")
        self._subtitle_lang_entry = self._entry(
            row, self._subtitle_lang_var, 10, padx=(SPACING["sm"], 0)
        )
        self._label(row, "(en,es,fr...)", padx=(2, 0))
        self._embed_subs_var = tk.BooleanVar(value=False)
        self._embed_subs_check = self._check(
            row,
            self._embed_subs_var,
            "Embed",
            font=FONT["small"],
            fg=_c("text_secondary"),
            padx=(SPACING["sm"], 0),
        )
        return row

    def _build_auth_row(self) -> tk.Frame:
        self._use_cookies_var = tk.BooleanVar(value=False)
        self._cookies_source_var = tk.StringVar(value="browser")
        self._cookies_file_var = tk.StringVar(value="")
        row = self._row("Auth:")
        self._check(
            row,
            self._use_cookies_var,
            "Cookies",
            font=FONT["small"],
            command=self._on_cookies_toggle,
        )
        installed_browsers = self._browser_options()
        default_browser = installed_browsers[0] if installed_browsers else "chrome"
        self._browser_var = tk.StringVar(value=default_browser)
        browser_combo = self._combo(
            row,
            self._browser_var,
            installed_browsers if installed_browsers else ["chrome"],
            8,
            font=FONT["small"],
            padx=(SPACING["sm"], 0),
        )
        browser_combo.bind("<<ComboboxSelected>>", self._on_browser_changed)
        self._profile_var = tk.StringVar(value="Default")
        self._profile_combo = self._combo(
            row, self._profile_var, ["Default"], 10, font=FONT["small"], padx=(SPACING["sm"], 0)
        )
        self._cookies_file_btn = tk.Button(
            row,
            text="...",
            bg=_c("surface"),
            fg=_c("text"),
            relief="flat",
            font=FONT["body"],
            width=2,
            command=self._on_select_cookies_file,
        )
        setattr_any(self._cookies_file_btn, "_theme", {"bg": "surface", "fg": "text"})
        self._cookies_file_btn.pack(side="left", padx=(SPACING["sm"], 0))
        add_hover_effect(self._cookies_file_btn, "hover", "surface")
        return row

    def _build_extra_row(self) -> tk.Frame:
        self._rate_limit_var = tk.StringVar(value="")
        row = self._row("Options:")
        self._entry(row, self._rate_limit_var, 8, padx=(0, SPACING["sm"]))
        self._label(row, "Rate (e.g. 1M)", padx=(0, SPACING["md"]))
        self._split_chapters_var = tk.BooleanVar(value=False)
        self._check(row, self._split_chapters_var, "Split chapters", font=FONT["small"])
        return row

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def get_options(self) -> DownloadOptions | None:
        """Options currently selected, or ``None`` when validation fails."""
        rate = self._rate_limit_var.get().strip()
        if rate and not is_valid_rate_limit(rate):
            self._mw._set_status("Invalid rate limit. Use format: 1M, 500K, 2G")
            return None
        opts = DownloadOptions(
            file_format=self._format_var.get(),
            quality=self._quality_var.get(),
            subtitles=self._subtitles_var.get(),
            subtitle_lang=self._subtitle_lang_var.get(),
            embed_subtitles=self._embed_subs_var.get(),
            use_cookies=self._use_cookies_var.get(),
            rate_limit=rate or None,
            split_chapters=self._split_chapters_var.get(),
        )
        if opts.use_cookies:
            if self._cookies_source_var.get() == "file" and self._cookies_file_var.get():
                opts.cookies_file = self._cookies_file_var.get()
            else:
                opts.cookies_from_browser = self._browser_var.get()
                opts.cookies_profile = (
                    self._profile_var.get() if self._profile_var.get() != "Default" else None
                )
        return opts

    def apply_to_video(self, video: Video) -> None:
        opts = self.get_options()
        if opts is not None:
            video.options = opts

    def update_for_video(self, video: Video) -> None:
        """Load ``video``'s options into the controls and refresh the retry button."""
        self._format_var.set(video.options.file_format)
        self._quality_var.set(video.options.quality)
        self._subtitles_var.set(video.options.subtitles)
        self._subtitle_lang_var.set(video.options.subtitle_lang)
        self._embed_subs_var.set(video.options.embed_subtitles)
        self._use_cookies_var.set(video.options.use_cookies)
        self._rate_limit_var.set(video.options.rate_limit or "")
        self._split_chapters_var.set(video.options.split_chapters or False)

        if video.options.cookies_file:
            self._cookies_source_var.set("file")
            self._cookies_file_var.set(video.options.cookies_file)
        else:
            self._cookies_source_var.set("browser")
            blist = self._browser_options()
            saved_browser = video.options.cookies_from_browser or "chrome"
            self._browser_var.set(
                saved_browser if saved_browser in blist else (blist[0] if blist else "chrome")
            )
            self._on_browser_changed()
            saved_profile = video.options.cookies_profile or "Default"
            current_profiles = list(self._profile_combo["values"])
            if saved_profile in current_profiles:
                self._profile_var.set(saved_profile)
            elif current_profiles:
                self._profile_var.set(current_profiles[0])
            else:
                self._profile_var.set("Default")

        if self._retry_btn.winfo_ismapped():
            self._retry_btn.pack_forget()
        if video.status == DownloadStatus.ERROR:
            self._retry_btn.pack(fill="x", pady=(0, SPACING["sm"]))
            add_hover_effect(self._retry_btn, "warning", "warning")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_settings(self, config: Any) -> None:
        """Apply persisted option values to the controls."""
        # Re-detect browsers/profiles: loading settings is an explicit reload, so
        # a stale memo would defeat the fallback-to-default logic.
        self._available_browsers = None
        self._browser_profiles_cache = None
        self._format_var.set(config.get("format", "mp3"))
        self._quality_var.set(config.get("quality", "best"))
        self._subtitles_var.set(config.get("subtitles", False))
        self._subtitle_lang_var.set(config.get("subtitle_lang", "en"))
        self._embed_subs_var.set(config.get("embed_subtitles", False))
        self._use_cookies_var.set(config.get("use_cookies", False))
        self._cookies_source_var.set(config.get("cookies_source", "browser"))
        self._cookies_file_var.set(config.get("cookies_file", ""))

        saved_browser = config.get("browser", "chrome")
        available = self._browser_options()
        if available:
            self._browser_var.set(saved_browser if saved_browser in available else available[0])
        else:
            self._browser_var.set("chrome")
        self._on_browser_changed()

        current_profiles = list(self._profile_combo["values"])
        saved_profile = config.get("profile", "Default")
        if saved_profile in current_profiles:
            self._profile_var.set(saved_profile)
        elif current_profiles:
            self._profile_var.set(current_profiles[0])
        else:
            self._profile_var.set("Default")

        self._rate_limit_var.set(config.get("rate_limit", ""))
        self._split_chapters_var.set(config.get("split_chapters", False))
        self._concurrent_var.set(config.get("concurrent_downloads", 1))

        if config.get("options_panel_open", False):
            self._options_frame.pack(
                fill="both", expand=True, padx=SPACING["md"], pady=(0, SPACING["md"])
            )
            self._detail_toggle_btn.configure(text="▼ OPTIONS")

        # Keep the subtitle controls in sync with the restored values. Cookies
        # are deliberately not re-toggled: ``_on_cookies_toggle`` resets the
        # browser/profile selection to the defaults.
        self._on_subtitles_toggle()

    def save_settings(self, config: Any) -> None:
        """Persist the current option values into ``config``."""
        rate = ""
        try:
            rate = self._rate_limit_var.get().strip()
            if rate and not is_valid_rate_limit(rate):
                rate = ""
        except (tk.TclError, KeyError, TypeError, ValueError) as e:
            logger.debug("Could not read rate limit: %s", e)

        def read_concurrent() -> int:
            try:
                return int(self._concurrent_var.get())
            except (tk.TclError, KeyError, TypeError, ValueError) as e:
                logger.debug("Invalid concurrent downloads value, keeping saved one: %s", e)
                return int(config.get("concurrent_downloads", 1))

        fields = (
            ("format", self._format_var.get),
            ("quality", self._quality_var.get),
            ("subtitles", self._subtitles_var.get),
            ("subtitle_lang", self._subtitle_lang_var.get),
            ("embed_subtitles", self._embed_subs_var.get),
            ("use_cookies", self._use_cookies_var.get),
            ("cookies_source", self._cookies_source_var.get),
            ("cookies_file", self._cookies_file_var.get),
            ("browser", self._browser_var.get),
            ("profile", self._profile_var.get),
            ("rate_limit", lambda: rate),
            ("split_chapters", self._split_chapters_var.get),
            ("options_panel_open", self._options_frame.winfo_ismapped),
            ("concurrent_downloads", read_concurrent),
        )
        for key, read in fields:
            try:
                config.set(key, read())
            except (tk.TclError, KeyError, TypeError, ValueError) as e:
                logger.debug("Could not store config field %s: %s", key, e)

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None:
        """Retry stays enabled whenever it is visible, independent of other jobs."""
        self._retry_btn.configure(state="normal")

    def toggle(self) -> None:
        """Expand or collapse the options body."""
        if self._options_frame.winfo_ismapped():
            self._options_frame.pack_forget()
            self._detail_toggle_btn.configure(text="OPTIONS")
        else:
            self._options_frame.pack(
                fill="both", expand=True, padx=SPACING["md"], pady=(0, SPACING["md"])
            )
            self._detail_toggle_btn.configure(text="OPTIONS")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_retry_download(self) -> None:
        video = self._mw._selected_video
        if video is None:
            return
        video.status = DownloadStatus.READY
        video.error_message = ""
        video.progress = 0.0
        self.apply_to_video(video)
        self._mw._controller.enqueue(video)
        self._mw._controller.start_downloads()
        self._mw._set_status(f"Retrying: {video.title}")

    def _on_concurrent_change(self) -> None:
        try:
            val = self._concurrent_var.get()
        except (tk.TclError, TypeError, ValueError):
            return
        ds = self._mw._controller
        ds.set_max_concurrent(val)

    def _on_subtitles_toggle(self) -> None:
        state: Literal["normal", "disabled"] = "normal" if self._subtitles_var.get() else "disabled"
        self._subtitle_lang_entry.configure(state=state)
        self._embed_subs_check.configure(state=state)

    def _on_cookies_toggle(self) -> None:
        browsers = self._browser_options()
        self._browser_var.set(browsers[0] if browsers else "chrome")
        self._on_browser_changed()

    def _on_select_cookies_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Cookies File",
            filetypes=[("Netscape cookies", "*.txt"), ("All files", "*.*")],
        )
        if file_path:
            self._use_cookies_var.set(True)
            self._cookies_source_var.set("file")
            self._cookies_file_var.set(file_path)

    def _on_browser_changed(self, event=None) -> None:
        browser = self._browser_var.get()
        profiles = self._browser_profiles()
        browser_profiles = profiles.get(browser, [])
        profile_names = [p.name for p in browser_profiles] if browser_profiles else ["Default"]
        self._profile_combo["values"] = profile_names
        self._profile_var.set(profile_names[0] if profile_names else "Default")
