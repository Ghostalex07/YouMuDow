"""Download options panel for YouMuDow.

The panel builds its controls directly inside the host frame (instead of being
a container widget itself) so ``DetailPanel`` keeps full control over the
layout order. It owns the Tk variables backing every option.
"""

import logging
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any

from youmudow.adapters.browser_profiles import get_all_browser_profiles, get_available_browsers
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video
from youmudow.domain.validators import (
    SUPPORTED_FORMATS,
    SUPPORTED_QUALITIES,
    is_valid_rate_limit,
)
from youmudow.ui.styles.constants import FONT, SPACING, _c, add_hover_effect

logger = logging.getLogger(__name__)


class OptionsPanel:
    """Download options: format, quality, auth, rate limit and concurrency.

    Widgets are parented to ``parent`` rather than to this object; the object
    only owns them and the Tk variables behind them. That keeps the pixel
    layout of the detail panel unchanged.
    """

    def __init__(self, parent: tk.Widget, main_window: object) -> None:
        self._mw = main_window
        self._build_header(parent)
        self._build_retry_button(parent)
        self._build_options(parent)
        self._on_subtitles_toggle()

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
        self._detail_toggle_btn._theme = {"bg": "bg", "fg": "text_secondary"}
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
        self._retry_btn._theme = {
            "bg": "warning",
            "fg": "#000000",
            "activebg": "warning",
            "activefg": "#000000",
        }

    def _build_options(self, parent: tk.Widget) -> None:
        self._options_frame = tk.Frame(parent, bg=_c("surface"))
        self._options_frame._bg_key = "surface"
        self._build_format_row()
        self._build_quality_row()
        self._build_concurrent_row()
        self._build_subtitles_row()
        self._build_auth_row()
        self._build_extra_row()

    def _build_format_row(self) -> None:
        format_row = tk.Frame(self._options_frame, bg=_c("surface"))
        format_row._bg_key = "surface"
        format_row.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))
        tk.Label(
            format_row,
            text="Format:",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._format_var = tk.StringVar(value="mp3")
        format_combo = ttk.Combobox(
            format_row,
            textvariable=self._format_var,
            values=sorted(SUPPORTED_FORMATS),
            state="readonly",
            width=8,
            font=FONT["body"],
        )
        format_combo.pack(side="left", padx=(0, SPACING["sm"]))

    def _build_quality_row(self) -> None:
        quality_row = tk.Frame(self._options_frame, bg=_c("surface"))
        quality_row._bg_key = "surface"
        quality_row.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(
            quality_row,
            text="Quality:",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(
            quality_row,
            textvariable=self._quality_var,
            values=sorted(SUPPORTED_QUALITIES),
            state="readonly",
            width=10,
            font=FONT["body"],
        )
        quality_combo.pack(side="left")

    def _build_concurrent_row(self) -> None:
        concurrent_row = tk.Frame(self._options_frame, bg=_c("surface"))
        concurrent_row._bg_key = "surface"
        concurrent_row.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(
            concurrent_row,
            text="Concurrent:",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._concurrent_var = tk.IntVar(value=1)
        concurrent_spin = tk.Spinbox(
            concurrent_row,
            from_=1,
            to=4,
            textvariable=self._concurrent_var,
            state="readonly",
            bg=_c("input_bg"),
            fg=_c("text"),
            relief="flat",
            width=3,
            font=FONT["body"],
            command=self._on_concurrent_change,
        )
        concurrent_spin.pack(side="left", padx=(0, SPACING["sm"]))
        tk.Label(
            concurrent_row,
            text="(1-4)",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
        ).pack(side="left")

    def _build_subtitles_row(self) -> None:
        subtitles_row = tk.Frame(self._options_frame, bg=_c("surface"))
        subtitles_row._bg_key = "surface"
        subtitles_row.pack(fill="x", pady=(0, SPACING["md"]))
        self._subtitles_var = tk.BooleanVar(value=False)
        subtitles_check = tk.Checkbutton(
            subtitles_row,
            text="Subtitles",
            variable=self._subtitles_var,
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("surface"),
            activeforeground=_c("text"),
            selectcolor=_c("surface"),
            relief="flat",
            font=FONT["body"],
            command=self._on_subtitles_toggle,
        )
        subtitles_check.pack(side="left")
        self._subtitle_lang_var = tk.StringVar(value="en")
        self._subtitle_lang_entry = tk.Entry(
            subtitles_row,
            textvariable=self._subtitle_lang_var,
            bg=_c("input_bg"),
            fg=_c("text"),
            relief="flat",
            font=FONT["small"],
            width=10,
        )
        self._subtitle_lang_entry.pack(side="left", padx=(SPACING["sm"], 0))
        tk.Label(
            subtitles_row,
            text="(en,es,fr...)",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
        ).pack(side="left", padx=(2, 0))
        self._embed_subs_var = tk.BooleanVar(value=False)
        self._embed_subs_check = tk.Checkbutton(
            subtitles_row,
            text="Embed",
            variable=self._embed_subs_var,
            bg=_c("surface"),
            fg=_c("text_secondary"),
            activebackground=_c("surface"),
            activeforeground=_c("text"),
            selectcolor=_c("surface"),
            relief="flat",
            font=FONT["small"],
        )
        self._embed_subs_check.pack(side="left", padx=(SPACING["sm"], 0))

    def _build_auth_row(self) -> None:
        auth_row = tk.Frame(self._options_frame, bg=_c("surface"))
        auth_row._bg_key = "surface"
        auth_row.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(
            auth_row,
            text="Auth:",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._use_cookies_var = tk.BooleanVar(value=False)
        self._cookies_source_var = tk.StringVar(value="browser")
        self._cookies_file_var = tk.StringVar(value="")
        cookies_check = tk.Checkbutton(
            auth_row,
            text="Cookies",
            variable=self._use_cookies_var,
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("surface"),
            activeforeground=_c("text"),
            selectcolor=_c("surface"),
            relief="flat",
            font=FONT["small"],
            command=self._on_cookies_toggle,
        )
        cookies_check.pack(side="left")
        installed_browsers = get_available_browsers()
        default_browser = installed_browsers[0] if installed_browsers else "chrome"
        self._browser_var = tk.StringVar(value=default_browser)
        browser_combo = ttk.Combobox(
            auth_row,
            textvariable=self._browser_var,
            values=installed_browsers if installed_browsers else ["chrome"],
            state="readonly",
            width=8,
            font=FONT["small"],
        )
        browser_combo.pack(side="left", padx=(SPACING["sm"], 0))
        browser_combo.bind("<<ComboboxSelected>>", self._on_browser_changed)
        self._profile_var = tk.StringVar(value="Default")
        self._profile_combo = ttk.Combobox(
            auth_row,
            textvariable=self._profile_var,
            values=["Default"],
            state="readonly",
            width=10,
            font=FONT["small"],
        )
        self._profile_combo.pack(side="left", padx=(SPACING["sm"], 0))
        self._cookies_file_btn = tk.Button(
            auth_row,
            text="...",
            bg=_c("surface"),
            fg=_c("text"),
            relief="flat",
            font=FONT["body"],
            width=2,
            command=self._on_select_cookies_file,
        )
        self._cookies_file_btn._theme = {"bg": "surface", "fg": "text"}
        self._cookies_file_btn.pack(side="left", padx=(SPACING["sm"], 0))
        add_hover_effect(self._cookies_file_btn, "hover", "surface")

    def _build_extra_row(self) -> None:
        extra_row = tk.Frame(self._options_frame, bg=_c("surface"))
        extra_row._bg_key = "surface"
        extra_row.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(
            extra_row,
            text="Options:",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            width=10,
            anchor="w",
        ).pack(side="left")
        self._rate_limit_var = tk.StringVar(value="")
        rate_entry = tk.Entry(
            extra_row,
            textvariable=self._rate_limit_var,
            bg=_c("input_bg"),
            fg=_c("text"),
            relief="flat",
            font=FONT["small"],
            width=8,
        )
        rate_entry.pack(side="left", padx=(0, SPACING["sm"]))
        tk.Label(
            extra_row,
            text="Rate (e.g. 1M)",
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
        ).pack(side="left", padx=(0, SPACING["md"]))
        self._split_chapters_var = tk.BooleanVar(value=False)
        split_check = tk.Checkbutton(
            extra_row,
            text="Split chapters",
            variable=self._split_chapters_var,
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("surface"),
            activeforeground=_c("text"),
            selectcolor=_c("surface"),
            relief="flat",
            font=FONT["small"],
        )
        split_check.pack(side="left")

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
            blist = get_available_browsers()
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
        self._format_var.set(config.get("format", "mp3"))
        self._quality_var.set(config.get("quality", "best"))
        self._subtitles_var.set(config.get("subtitles", False))
        self._subtitle_lang_var.set(config.get("subtitle_lang", "en"))
        self._embed_subs_var.set(config.get("embed_subtitles", False))
        self._use_cookies_var.set(config.get("use_cookies", False))
        self._cookies_source_var.set(config.get("cookies_source", "browser"))
        self._cookies_file_var.set(config.get("cookies_file", ""))

        saved_browser = config.get("browser", "chrome")
        available = get_available_browsers()
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
        if hasattr(self._mw, "_controller") and self._mw._controller:
            ds = self._mw._controller._download_service
            ds.set_max_concurrent(val)

    def _on_subtitles_toggle(self) -> None:
        state = "normal" if self._subtitles_var.get() else "disabled"
        self._subtitle_lang_entry.configure(state=state)
        self._embed_subs_check.configure(state=state)

    def _on_cookies_toggle(self) -> None:
        self._browser_var.set(get_available_browsers()[0] if get_available_browsers() else "chrome")
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
        profiles = get_all_browser_profiles()
        browser_profiles = profiles.get(browser, [])
        profile_names = [p.name for p in browser_profiles] if browser_profiles else ["Default"]
        self._profile_combo["values"] = profile_names
        self._profile_var.set(profile_names[0] if profile_names else "Default")
