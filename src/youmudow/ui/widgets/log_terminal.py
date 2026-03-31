"""Log terminal widget for YouMuDow.

Displays real-time log output in a terminal-like format.
"""

import tkinter as tk
from tkinter import ttk
import datetime


MAX_LINES = 1000


class LogTerminal(ttk.Frame):
    """Terminal-like widget for displaying log output."""

    def __init__(
        self,
        parent: tk.Widget,
        show_timestamp: bool = True,
        max_lines: int = MAX_LINES,
        **kwargs: object,
    ) -> None:
        super().__init__(parent)
        self._show_timestamp = show_timestamp
        self._max_lines = max_lines
        self._line_count = 0

        self._create_widgets()
        self._configure_tags()

    def _create_widgets(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 5))

        self._clear_btn = ttk.Button(
            toolbar,
            text="Clear",
            command=self.clear,
        )
        self._clear_btn.pack(side="left")

        self._auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Auto-scroll",
            variable=self._auto_scroll_var,
        ).pack(side="left", padx=(10, 0))

        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True)

        self._text = tk.Text(
            text_frame,
            wrap="none",
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            relief="flat",
            state="disabled",
        )
        self._text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
        scrollbar.configure(command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _configure_tags(self) -> None:
        self._text.tag_configure("info", foreground="#d4d4d4")
        self._text.tag_configure("warning", foreground="#dcdcaa")
        self._text.tag_configure("error", foreground="#f14c4c")
        self._text.tag_configure("success", foreground="#6a9955")
        self._text.tag_configure("timestamp", foreground="#808080")
        self._text.tag_configure("debug", foreground="#569cd6")
        self._text.tag_configure("separator", foreground="#569cd6")

    def append(self, message: str, level: str = "info", timestamp: str | None = None) -> None:
        """Append a log message to the terminal."""
        if not message:
            return

        self._text.configure(state="normal")

        if self._show_timestamp and timestamp:
            ts = f"[{timestamp}] "
            self._text.insert("end", ts, "timestamp")
        elif self._show_timestamp:
            ts = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
            self._text.insert("end", ts, "timestamp")

        self._text.insert("end", message + "\n", level)

        self._line_count += 1

        if self._line_count > self._max_lines:
            self._trim_lines()

        self._text.configure(state="disabled")

        if self._auto_scroll_var.get():
            self._text.see("end")

    def append_separator(self, text: str = "") -> None:
        """Append a separator line."""
        self._text.configure(state="normal")
        if text:
            self._text.insert("end", f"--- {text} ---\n", "separator")
        else:
            self._text.insert("end", "-" * 40 + "\n", "separator")
        self._text.configure(state="disabled")

    def clear(self) -> None:
        """Clear all log output."""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
        self._line_count = 0

    def _trim_lines(self) -> None:
        """Remove oldest lines when max is reached."""
        lines_to_remove = self._max_lines // 10
        for _ in range(lines_to_remove):
            self._text.delete("1.0", "2.0")

    def set_auto_scroll(self, enabled: bool) -> None:
        """Enable or disable auto-scrolling."""
        self._auto_scroll_var.set(enabled)
