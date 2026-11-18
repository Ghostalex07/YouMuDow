"""In-app user guide, shown in its own closable notebook tab."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from youmudow.ui.styles.constants import FONT, SPACING, _c

GUIDE_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "Searching",
        (
            "Type a name in the search bar and press Enter, or paste a link to a "
            "video, playlist or channel. Results appear as cards on the left; "
            "clicking one fills the detail panel on the right."
        ),
    ),
    (
        "Playlists and channels",
        (
            "Paste a playlist link, an @handle, or a channel URL (with or without "
            "/videos, /shorts or /streams). The first page loads a number of "
            "entries equal to the playlist limit (1-500, 50 by default). Use "
            "Load more to append the next page; a short page means the playlist "
            "is finished and the button disables. Add all queues every entry that "
            "is currently loaded."
        ),
    ),
    (
        "Formats and presets",
        (
            "Choose the output format and quality, or pick a preset: Music 320 "
            "(MP3), Video 1080 (MP4) or Archive FLAC. Editing any option switches "
            "the preset back to Custom. Presets never change the output folder, "
            "the cookies or the rate limit."
        ),
    ),
    (
        "Preview before downloading",
        (
            "Selecting a result shows its uploader, duration and the estimated "
            "size for the format you picked. The estimate is recomputed when you "
            "change format or quality, and it is only an estimate: the real size "
            "depends on the source."
        ),
    ),
    (
        "Queue, concurrency and retries",
        (
            "Add the selected video, or Download Now to skip the queue. The queue "
            "panel shows pending, active and finished entries. Concurrent "
            "downloads is configurable; failed downloads are retried with a "
            "growing wait (2 retries by default, 0-5), and cancelling during a "
            "retry stops it at once. The pending queue is saved and restored the "
            "next time you open the app."
        ),
    ),
    (
        "Subtitles and chapters",
        (
            "Enable subtitles and pick the language list (for example es,en), "
            "optionally embedding them. Split chapters writes one file per chapter "
            "and embeds chapter marks when the format supports it."
        ),
    ),
    (
        "Cookies and rate limiting",
        (
            "Private or age-restricted videos may need cookies: read them from a "
            "supported browser profile or from a Netscape cookies.txt file. The "
            "rate limit accepts yt-dlp syntax such as 500K or 2M."
        ),
    ),
    (
        "System tray",
        (
            "View > Keep Running in Tray keeps the queue alive when you close the "
            "window, with Show, Start downloads and Quit. Quit uses the same "
            "shutdown path as File > Exit, so the settings are saved. On Linux the "
            "tray needs a status-notifier host."
        ),
    ),
    (
        "Logs and diagnostics",
        (
            "Debug Mode shows the log panel with the yt-dlp output. File > Export "
            "Logs saves it. Help > Export Diagnostics writes version, platform, "
            "yt-dlp, ffmpeg, YouTube environment, a redacted configuration and the "
            "end of the log into one file you can attach to a bug report."
        ),
    ),
    (
        "Command line",
        (
            "youmudow-cli download <url> --format mp3 --output DIR downloads "
            "without opening the window; --limit N sets how many playlist entries "
            "to take. youmudow-cli search <query> lists matches."
        ),
    ),
)


class GuidePanel(tk.Frame):
    """Scrollable, read-only guide with a close button."""

    def __init__(self, parent: tk.Widget, on_close: Callable[[], None]) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._text: tk.Text
        self._close_btn: tk.Button
        self._build(on_close)

    def _build(self, on_close: Callable[[], None]) -> None:
        header = tk.Frame(self, bg=_c("bg"))
        header.pack(fill="x", padx=SPACING["md"], pady=(SPACING["md"], SPACING["xs"]))

        tk.Label(
            header,
            text="User Guide",
            bg=_c("bg"),
            fg=_c("text"),
            font=FONT["h1"],
        ).pack(side="left")

        self._close_btn = tk.Button(
            header,
            text="Close",
            command=on_close,
            bg=_c("surface"),
            fg=_c("text"),
            activebackground=_c("hover"),
            activeforeground=_c("text"),
            relief="flat",
            padx=SPACING["sm"],
            pady=SPACING["xs"],
            font=FONT["body"],
            cursor="hand2",
        )
        self._close_btn.pack(side="right")

        body = tk.Frame(self, bg=_c("bg"))
        body.pack(fill="both", expand=True, padx=SPACING["md"], pady=(0, SPACING["md"]))

        scrollbar = ttk.Scrollbar(body, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(
            body,
            bg=_c("surface"),
            fg=_c("text"),
            insertbackground=_c("text"),
            relief="flat",
            bd=0,
            wrap="word",
            padx=SPACING["md"],
            pady=SPACING["sm"],
            font=FONT["body"],
            yscrollcommand=scrollbar.set,
        )
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self._text.yview)

        self._text.tag_configure("title", font=FONT["h1"], spacing3=SPACING["xs"])
        self._text.tag_configure("body", font=FONT["body"], spacing3=SPACING["md"])
        for title, text in GUIDE_SECTIONS:
            self._text.insert("end", f"{title}\n", "title")
            self._text.insert("end", f"{text}\n", "body")
        self._text.configure(state="disabled")
