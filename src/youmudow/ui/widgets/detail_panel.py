"""Detail panel widget for YouMuDow."""

import threading
import tkinter as tk
from tkinter import ttk, filedialog
import webbrowser

from youmudow.domain.models import Video, DownloadOptions
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.validators import (get_all_browser_profiles, get_available_browsers,
                                        is_valid_rate_limit)
from youmudow.app.state import AppStateData
from youmudow.ui.styles.constants import SPACING, FONT, _c, add_hover_effect


class DetailPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, main_window: object) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._mw = main_window
        self._last_thumb_url: str | None = None
        self._queue_panel_visible = False

        self.grid(row=1, column=1, sticky="nsew",
                  padx=(SPACING["sm"], SPACING["md"]), pady=(0, SPACING["md"]))

        header_frame = tk.Frame(self, bg=_c("bg"))
        header_frame.pack(fill="x", pady=(0, SPACING["xs"]))

        self._detail_toggle_btn = tk.Button(
            header_frame, text="▶ OPTIONS",
            bg=_c("bg"), fg=_c("text_secondary"),
            font=FONT["label"], relief="flat", bd=0,
            command=self._toggle_options,
        )
        self._detail_toggle_btn._theme = {"bg": "bg", "fg": "text_secondary"}
        self._detail_toggle_btn.pack(side="left")

        self._thumbnail_label = tk.Label(
            self, text="[No thumbnail]",
            bg=_c("surface"), fg=_c("text_secondary"),
            font=FONT["small"], anchor="center", height=8,
        )
        self._thumbnail_label.pack(fill="x", pady=(0, SPACING["sm"]))

        row_title = tk.Frame(self, bg=_c("surface"))
        row_title._bg_key = "surface"
        row_title.pack(fill="x", pady=(0, SPACING["xs"]))
        tk.Label(row_title, text="Title:", bg=_c("surface"), fg=_c("text_secondary"),
                 font=FONT["body"], width=10, anchor="w").pack(side="left")
        self._detail_title = tk.Label(row_title, text="-", bg=_c("surface"), fg=_c("text"),
                                      font=FONT["body"], anchor="w", wraplength=180)
        self._detail_title.pack(side="left", fill="x", expand=True)

        row_uploader = tk.Frame(self, bg=_c("surface"))
        row_uploader._bg_key = "surface"
        row_uploader.pack(fill="x", pady=(0, SPACING["sm"]))
        tk.Label(row_uploader, text="Uploader:", bg=_c("surface"), fg=_c("text_secondary"),
                 font=FONT["body"], width=10, anchor="w").pack(side="left")
        self._detail_uploader = tk.Label(row_uploader, text="-", bg=_c("surface"), fg=_c("text"),
                                         font=FONT["body"], anchor="w")
        self._detail_uploader.pack(side="left")

        tk.Frame(self, height=2, bg=_c("bg")).pack(fill="x", pady=(0, SPACING["md"]))

        self._download_btn = tk.Button(
            self, text="Download",
            bg=_c("primary"), fg="#FFFFFF",
            activebackground=_c("secondary"), activeforeground="#FFFFFF",
            relief="flat", font=FONT["body"],
            command=lambda: self._mw._on_download_now(),
        )
        self._download_btn._theme = {"bg": "primary", "fg": "#FFFFFF", "activebg": "secondary", "activefg": "#FFFFFF"}
        self._download_btn.pack(fill="x", pady=(0, SPACING["xs"]))
        add_hover_effect(self._download_btn, "secondary", "primary")

        self._retry_btn = tk.Button(
            self, text="↺ Retry",
            bg=_c("warning"), fg="#000000",
            activebackground=_c("secondary"), activeforeground="#000000",
            relief="flat", font=FONT["body"],
            command=self._on_retry_download,
        )
        self._retry_btn._theme = {"bg": "warning", "fg": "#000000", "activebg": "secondary", "activefg": "#000000"}

        btn_row = tk.Frame(self, bg=_c("bg"))
        btn_row.pack(fill="x", pady=(0, SPACING["md"]))

        self._open_folder_btn = tk.Button(
            btn_row, text="Open Folder",
            bg=_c("surface"), fg=_c("text"),
            activebackground=_c("hover"), activeforeground=_c("text"),
            relief="flat", font=FONT["body"],
            command=self._mw._on_open_folder,
        )
        self._open_folder_btn._theme = {"bg": "surface", "fg": "text", "activebg": "hover", "activefg": "text"}
        self._open_folder_btn.pack(side="left", fill="x", expand=True, padx=(0, SPACING["xs"]))
        add_hover_effect(self._open_folder_btn, "hover", "surface")

        self._add_all_btn = tk.Button(
            btn_row, text="Add All",
            bg=_c("surface"), fg=_c("text"),
            activebackground=_c("hover"), activeforeground=_c("text"),
            relief="flat", font=FONT["body"],
            command=self._add_all_to_queue,
        )
        self._add_all_btn._theme = {"bg": "surface", "fg": "text", "activebg": "hover", "activefg": "text"}
        self._add_all_btn.pack(side="left", fill="x", expand=True, padx=(SPACING["xs"], 0))
        add_hover_effect(self._add_all_btn, "hover", "surface")

        self._queue_toggle_btn = tk.Button(
            btn_row, text="Queue ▾",
            bg=_c("surface"), fg=_c("text"),
            activebackground=_c("hover"), activeforeground=_c("text"),
            relief="flat", font=FONT["body"],
            command=self._toggle_queue_panel,
        )
        self._queue_toggle_btn._theme = {"bg": "surface", "fg": "text", "activebg": "hover", "activefg": "text"}
        self._queue_toggle_btn.pack(side="left", fill="x", expand=True, padx=(SPACING["xs"], 0))
        add_hover_effect(self._queue_toggle_btn, "hover", "surface")

        self._options_frame = tk.Frame(self, bg=_c("surface"))
        self._options_frame._bg_key = "surface"
        self._create_options()
        self._create_queue_panel()

    def _create_options(self) -> None:
        of = self._options_frame
        format_row = tk.Frame(of, bg=_c("surface"))
        format_row._bg_key = "surface"
        format_row.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(format_row, text="Format:", bg=_c("surface"), fg=_c("text_secondary"),
                 font=FONT["body"], width=10, anchor="w").pack(side="left")
        self._format_var = tk.StringVar(value="mp3")
        format_combo = ttk.Combobox(format_row, textvariable=self._format_var,
                                    values=["mp3", "mp4", "m4a", "best"],
                                    state="readonly", width=8, font=FONT["body"])
        format_combo.pack(side="left", padx=(0, SPACING["sm"]))

        quality_row = tk.Frame(of, bg=_c("surface"))
        quality_row._bg_key = "surface"
        quality_row.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))
        tk.Label(quality_row, text="Quality:", bg=_c("surface"), fg=_c("text_secondary"),
                 font=FONT["body"], width=10, anchor="w").pack(side="left")
        self._quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(quality_row, textvariable=self._quality_var,
                                     values=["best", "320kbps", "256kbps", "192kbps", "1080p", "720p", "480p"],
                                     state="readonly", width=10, font=FONT["body"])
        quality_combo.pack(side="left")

        concurrent_row = tk.Frame(of, bg=_c("surface"))
        concurrent_row._bg_key = "surface"
        concurrent_row.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))
        tk.Label(concurrent_row, text="Concurrent DL:", bg=_c("surface"), fg=_c("text_secondary"),
                 font=FONT["body"], width=12, anchor="w").pack(side="left")
        self._concurrent_var = tk.IntVar(value=1)
        concurrent_spin = tk.Spinbox(
            concurrent_row, from_=1, to=4, textvariable=self._concurrent_var,
            bg=_c("input_bg"), fg=_c("text"), relief="flat", width=3,
            font=FONT["body"], command=self._on_concurrent_change,
        )
        concurrent_spin.pack(side="left", padx=(0, SPACING["sm"]))
        tk.Label(concurrent_row, text="(1-4)", bg=_c("surface"), fg=_c("text_secondary"),
                 font=("Segoe UI", 8)).pack(side="left")

        subtitles_row = tk.Frame(of, bg=_c("surface"))
        subtitles_row._bg_key = "surface"
        subtitles_row.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))
        self._subtitles_var = tk.BooleanVar(value=False)
        subtitles_check = tk.Checkbutton(subtitles_row, text="Download subtitles",
                                          variable=self._subtitles_var,
                                          bg=_c("surface"), fg=_c("text"),
                                          activebackground=_c("surface"), activeforeground=_c("text"),
                                          selectcolor=_c("surface"), relief="flat", font=FONT["body"],
                                          command=self._on_subtitles_toggle)
        subtitles_check.pack(side="left")
        self._subtitle_lang_var = tk.StringVar(value="en")
        self._subtitle_lang_entry = tk.Entry(subtitles_row, textvariable=self._subtitle_lang_var,
                                              bg=_c("input_bg"), fg=_c("text"), relief="flat",
                                              font=("Segoe UI", 9), width=10)
        self._subtitle_lang_entry.pack(side="left", padx=(SPACING["sm"], 0))
        tk.Label(subtitles_row, text="(en,es,fr...)", bg=_c("surface"), fg=_c("text_secondary"),
                 font=("Segoe UI", 8)).pack(side="left", padx=(2, 0))
        self._embed_subs_var = tk.BooleanVar(value=False)
        self._embed_subs_check = tk.Checkbutton(subtitles_row, text="Embed",
                                                 variable=self._embed_subs_var,
                                                 bg=_c("surface"), fg=_c("text_secondary"),
                                                 activebackground=_c("surface"), activeforeground=_c("text"),
                                                 selectcolor=_c("surface"), relief="flat", font=("Segoe UI", 9))
        self._embed_subs_check.pack(side="left", padx=(SPACING["sm"], 0))

        auth_row = tk.Frame(of, bg=_c("surface"))
        auth_row._bg_key = "surface"
        auth_row.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))
        tk.Label(auth_row, text="Auth:", bg=_c("surface"), fg=_c("text_secondary"),
                 font=("Segoe UI", 9), width=10, anchor="w").pack(side="left")
        self._use_cookies_var = tk.BooleanVar(value=False)
        self._cookies_source_var = tk.StringVar(value="browser")
        self._cookies_file_var = tk.StringVar(value="")
        cookies_check = tk.Checkbutton(auth_row, text="Cookies", variable=self._use_cookies_var,
                                        bg=_c("surface"), fg=_c("text"),
                                        activebackground=_c("surface"), activeforeground=_c("text"),
                                        selectcolor=_c("surface"), relief="flat", font=("Segoe UI", 9),
                                        command=self._on_cookies_toggle)
        cookies_check.pack(side="left")
        installed_browsers = get_available_browsers()
        default_browser = installed_browsers[0] if installed_browsers else "chrome"
        self._browser_var = tk.StringVar(value=default_browser)
        browser_combo = ttk.Combobox(auth_row, textvariable=self._browser_var,
                                     values=installed_browsers if installed_browsers else ["chrome"],
                                     state="readonly", width=8, font=("Segoe UI", 9))
        browser_combo.pack(side="left", padx=(SPACING["sm"], 0))
        browser_combo.bind("<<ComboboxSelected>>", self._on_browser_changed)
        self._profile_var = tk.StringVar(value="Default")
        self._profile_combo = ttk.Combobox(auth_row, textvariable=self._profile_var,
                                            values=["Default"], state="readonly",
                                            width=10, font=("Segoe UI", 9))
        self._profile_combo.pack(side="left", padx=(SPACING["sm"], 0))
        self._cookies_file_btn = tk.Button(auth_row, text="📁",
                                            bg=_c("surface"), fg=_c("text"), relief="flat",
                                            font=("Segoe UI", 10), width=2,
                                            command=self._on_select_cookies_file)
        self._cookies_file_btn._theme = {"bg": "surface", "fg": "text"}
        self._cookies_file_btn.pack(side="left", padx=(SPACING["sm"], 0))
        add_hover_effect(self._cookies_file_btn, "hover", "surface")

        extra_row = tk.Frame(of, bg=_c("surface"))
        extra_row._bg_key = "surface"
        extra_row.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))
        tk.Label(extra_row, text="Options:", bg=_c("surface"), fg=_c("text_secondary"),
                 font=("Segoe UI", 9), width=10, anchor="w").pack(side="left")
        self._rate_limit_var = tk.StringVar(value="")
        rate_entry = tk.Entry(extra_row, textvariable=self._rate_limit_var,
                              bg=_c("input_bg"), fg=_c("text"), relief="flat",
                              font=("Segoe UI", 9), width=8)
        rate_entry.pack(side="left", padx=(0, SPACING["sm"]))
        tk.Label(extra_row, text="Rate (e.g. 1M)", bg=_c("surface"), fg=_c("text_secondary"),
                 font=("Segoe UI", 8)).pack(side="left", padx=(0, SPACING["md"]))
        self._split_chapters_var = tk.BooleanVar(value=False)
        split_check = tk.Checkbutton(extra_row, text="Split chapters", variable=self._split_chapters_var,
                                      bg=_c("surface"), fg=_c("text"),
                                      activebackground=_c("surface"), activeforeground=_c("text"),
                                      selectcolor=_c("surface"), relief="flat", font=("Segoe UI", 9))
        split_check.pack(side="left")

        self._options_frame.pack_forget()
        self._on_subtitles_toggle()

    def _create_queue_panel(self) -> None:
        parent = self._mw._main_content_frame
        self._queue_frame = tk.Frame(parent, bg=_c("surface"))
        self._queue_frame._bg_key = "surface"
        self._queue_frame.grid(row=2, column=0, columnspan=2, sticky="ew",
                                padx=SPACING["md"], pady=(0, SPACING["md"]))

        qheader = tk.Frame(self._queue_frame, bg=_c("surface"))
        qheader._bg_key = "surface"
        qheader.pack(fill="x", pady=(SPACING["sm"], SPACING["xs"]))
        tk.Label(qheader, text="QUEUE", bg=_c("surface"), fg=_c("text_secondary"),
                 font=FONT["label"]).pack(side="left", padx=SPACING["sm"])
        self._queue_count_label = tk.Label(qheader, text="0 queued", bg=_c("surface"),
                                            fg=_c("text_secondary"), font=FONT["small"])
        self._queue_count_label.pack(side="right", padx=SPACING["sm"])

        qcols = ("status", "title", "progress")
        self._queue_tree = ttk.Treeview(self._queue_frame, columns=qcols, show="headings",
                                         height=5, style="Modern.Treeview")
        self._queue_tree.heading("status", text="STATUS")
        self._queue_tree.heading("title", text="TITLE")
        self._queue_tree.heading("progress", text="PROGRESS")
        self._queue_tree.column("status", width=100)
        self._queue_tree.column("title", width=300)
        self._queue_tree.column("progress", width=80)

        qscroll = ttk.Scrollbar(self._queue_frame, orient="vertical", command=self._queue_tree.yview)
        self._queue_tree.configure(yscrollcommand=qscroll.set)
        self._queue_tree.pack(side="left", fill="both", expand=True,
                              padx=(SPACING["sm"], 0), pady=(0, SPACING["sm"]))
        qscroll.pack(side="right", fill="y", pady=(0, SPACING["sm"]), padx=(0, SPACING["sm"]))
        self._queue_tree.bind("<Button-3>", self._on_queue_right_click)

    def update_detail_panel(self, video: Video) -> None:
        self._detail_title.configure(text=video.title or "-")
        self._detail_uploader.configure(text=video.uploader or "-")
        self._load_thumbnail(video)
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
            self._browser_var.set(saved_browser if saved_browser in blist else (blist[0] if blist else "chrome"))
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
            self._retry_btn.pack(fill="x", pady=(0, SPACING["xs"]))
            add_hover_effect(self._retry_btn, "warning", "warning")

    def _load_thumbnail(self, video: Video) -> None:
        self._thumbnail_label.configure(text="[No thumbnail]")
        thumbnail_url = video.thumbnail
        if not thumbnail_url:
            return
        self._last_thumb_url = thumbnail_url

        def _fetch_and_set() -> None:
            try:
                from urllib.request import urlopen
                data = urlopen(thumbnail_url, timeout=5).read()
                self._mw._root.after(0, _set_thumbnail, data, thumbnail_url)
            except Exception:
                pass

        def _set_thumbnail(data: bytes, url: str) -> None:
            if getattr(self, '_last_thumb_url', None) != url:
                return
            try:
                from PIL import Image, ImageTk
                import io
                img = Image.open(io.BytesIO(data))
                max_w = 240
                max_h = 120
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                self._tk_image = ImageTk.PhotoImage(img)
                self._thumbnail_label.configure(image=self._tk_image, text="")
            except ImportError:
                self._thumbnail_label.configure(text=f"[Thumbnail: {url}]")
            except Exception:
                pass

        threading.Thread(target=_fetch_and_set, daemon=True).start()

    def _on_retry_download(self) -> None:
        video = self._mw._selected_video
        if video is None:
            return
        video.status = DownloadStatus.READY
        video.error_message = ""
        video.progress = 0.0
        self._apply_options_to_video(video)
        self._mw._controller.enqueue(video)
        self._mw._controller.start_downloads()
        self._mw._set_status(f"Retrying: {video.title}")

    def _toggle_options(self) -> None:
        if self._options_frame.winfo_ismapped():
            self._options_frame.pack_forget()
            self._detail_toggle_btn.configure(text="▶ OPTIONS")
        else:
            self._options_frame.pack(fill="both", expand=True, padx=SPACING["md"], pady=(0, SPACING["md"]))
            self._detail_toggle_btn.configure(text="▼ OPTIONS")

    def _on_concurrent_change(self) -> None:
        val = self._concurrent_var.get()
        if hasattr(self._mw, '_controller') and self._mw._controller:
            ds = self._mw._controller._download_service
            ds._max_concurrent = val

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

    def get_current_options(self) -> DownloadOptions | None:
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
                opts.cookies_profile = self._profile_var.get() if self._profile_var.get() != "Default" else None
        return opts

    def apply_options_to_video(self, video: Video) -> None:
        opts = self.get_current_options()
        if opts is not None:
            video.options = opts

    def _on_enqueue(self) -> None:
        selected = self._mw._results_table.get_selected_videos()
        if selected:
            opts = self.get_current_options()
            if opts is None:
                return
            for video in selected:
                video.options = opts
            self._mw._controller.enqueue_multiple(selected)
            self._mw._set_status(f"Added {len(selected)} to queue")
            return
        if self._mw._results_table.is_playlist and self._mw._results_table.playlist_videos:
            return
        video = self._mw._selected_video
        if video is None:
            return
        self.apply_options_to_video(video)
        self._mw._controller.enqueue(video)
        self._mw._set_status(f"Added to queue: {video.title}")

    def _add_all_to_queue(self) -> None:
        opts = self.get_current_options()
        if opts is None:
            return
        videos = self._mw._results_table.playlist_videos
        for video in videos:
            video.options = opts
        self._mw._controller.enqueue_multiple(videos)
        self._mw._set_status(f"Added {len(videos)} videos to queue")

    def _toggle_queue_panel(self) -> None:
        if self._queue_panel_visible:
            self._queue_frame.grid_remove()
            self._queue_panel_visible = False
            self._queue_toggle_btn.configure(text="Queue ▸")
        else:
            self._queue_frame.grid()
            self._queue_panel_visible = True
            self._queue_toggle_btn.configure(text="Queue ▾")
            self._update_queue_display()

    def _update_queue_display(self, snapshot: AppStateData | None = None) -> None:
        if snapshot is None:
            snapshot = self._mw._controller.state.get_snapshot()

        desired: list[tuple[str, tuple]] = []
        for v in snapshot.queue:
            desired.append((v.url, ("Queued", v.title[:60], "-")))
        for v in snapshot.active_downloads:
            desired.append((v.url, ("Downloading", v.title[:60], f"{v.progress:.0f}%")))
        for v in snapshot.completed_downloads:
            desired.append((v.url, ("Completed", v.title[:60], "100%")))

        desired_iids = {iid for iid, _ in desired}
        existing_iids = set(self._queue_tree.get_children())

        for iid in existing_iids - desired_iids:
            self._queue_tree.delete(iid)

        for iid, values in desired:
            if iid in existing_iids:
                current = self._queue_tree.item(iid, "values")
                if current != values:
                    self._queue_tree.item(iid, values=values)
            else:
                self._queue_tree.insert("", "end", iid=iid, values=values)

        for i, (iid, _) in enumerate(desired):
            self._queue_tree.move(iid, "", i)

        total = len(snapshot.queue) + len(snapshot.active_downloads) + len(snapshot.completed_downloads)
        self._queue_count_label.configure(text=f"{total} items")

    def _on_queue_right_click(self, event: tk.Event) -> None:
        item = self._queue_tree.identify_row(event.y)
        if not item:
            return
        self._queue_tree.selection_set(item)
        snapshot = self._mw._controller.state.get_snapshot()
        all_videos = list(snapshot.queue) + list(snapshot.active_downloads) + list(snapshot.completed_downloads)
        video = next((v for v in all_videos if v.url == item), None)
        if not video:
            return
        menu = tk.Menu(self._mw._root, tearoff=0, bg=_c("surface"), fg=_c("text"))
        menu.add_command(label="Remove from queue", command=lambda: self._mw._controller.remove_from_queue(video))
        menu.add_command(label="Open in browser", command=lambda: webbrowser.open(video.url))
        menu.tk_popup(event.x_root, event.y_root)

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None:
        is_busy = is_searching or is_downloading
        has_video = self._mw._selected_video is not None
        self._download_btn.configure(state="disabled" if is_busy or not has_video else "normal")
        self._open_folder_btn.configure(state="normal")
        is_playlist = self._mw._results_table.is_playlist
        has_playlist = bool(self._mw._results_table.playlist_videos)
        self._add_all_btn.configure(state="normal" if is_playlist and has_playlist else "disabled")
