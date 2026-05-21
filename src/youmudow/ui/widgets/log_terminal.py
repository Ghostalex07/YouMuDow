"""Log terminal widget for YouMuDow.

Displays real-time log output in a terminal-like format.
Modern dark theme with syntax highlighting.
"""

import tkinter as tk
from tkinter import ttk
import datetime
import threading
from pathlib import Path


MAX_LINES = 1000

TERMINAL_SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 16,
}


TERMINAL_COLORS = {
    "background": "#0A0A10",
    "foreground": "#ECECF1",
    "info": "#8A8A99",
    "warning": "#FBBF24",
    "error": "#F87171",
    "success": "#34D399",
    "debug": "#60A5FA",
    "separator": "#2E2E38",
    "timestamp": "#5A5A6A",
    "download": "#A78BFA",
}


class LogTerminal(ttk.Frame):
    """Terminal-like widget for displaying log output with modern styling."""

    def __init__(
        self,
        parent: tk.Widget,
        show_timestamp: bool = True,
        max_lines: int = MAX_LINES,
    ) -> None:
        super().__init__(parent)
        self._show_timestamp = show_timestamp
        self._max_lines = max_lines
        self._line_count = 0
        self._lock = threading.Lock()
        self._pending_messages: list[tuple[str, str, str | None]] = []
        self._processing = False
        self._log_buffer: list[str] = []

        self._create_widgets()
        self._configure_tags()

    def _create_widgets(self) -> None:
        toolbar = tk.Frame(self, bg=TERMINAL_COLORS["background"])
        toolbar.pack(fill="x", pady=(0, 4))

        clear_btn = tk.Button(
            toolbar,
            text="Clear",
            bg=TERMINAL_COLORS["background"],
            fg=TERMINAL_COLORS["foreground"],
            activebackground=TERMINAL_COLORS["separator"],
            activeforeground=TERMINAL_COLORS["foreground"],
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            font=("Segoe UI", 9),
            command=self.clear,
        )
        clear_btn.pack(side="left")
        
        def add_hover(widget: tk.Widget) -> None:
            hover_bg = TERMINAL_COLORS["separator"]
            normal_bg = TERMINAL_COLORS["background"]
            def on_enter(e: tk.Event) -> None:
                widget.configure(bg=hover_bg)
            def on_leave(e: tk.Event) -> None:
                widget.configure(bg=normal_bg)
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
        
        add_hover(clear_btn)

        self._auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_check = tk.Checkbutton(
            toolbar,
            text="Auto-scroll",
            bg=TERMINAL_COLORS["background"],
            fg=TERMINAL_COLORS["foreground"],
            activebackground=TERMINAL_COLORS["background"],
            activeforeground=TERMINAL_COLORS["foreground"],
            selectcolor=TERMINAL_COLORS["background"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 9),
            variable=self._auto_scroll_var,
        )
        auto_scroll_check.pack(side="left", padx=(16, 0))

        container = tk.Frame(self, bg=TERMINAL_COLORS["background"], bd=1, relief="solid", highlightbackground=TERMINAL_COLORS["separator"])
        container.pack(fill="both", expand=True)

        text_frame = tk.Frame(container, bg=TERMINAL_COLORS["background"])
        text_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self._text = tk.Text(
            text_frame,
            wrap="none",
            font=("Cascadia Code", 10),
            bg=TERMINAL_COLORS["background"],
            fg=TERMINAL_COLORS["foreground"],
            insertbackground=TERMINAL_COLORS["foreground"],
            relief="flat",
            bd=0,
            padx=TERMINAL_SPACING["sm"],
            pady=TERMINAL_SPACING["sm"],
            state="disabled",
            highlightthickness=0,
        )
        self._text.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(text_frame, orient="vertical", bg=TERMINAL_COLORS["background"], activebackground=TERMINAL_COLORS["separator"], troughcolor=TERMINAL_COLORS["background"], relief="flat", bd=0)
        scrollbar.configure(command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _configure_tags(self) -> None:
        self._text.tag_configure("info", foreground=TERMINAL_COLORS["info"])
        self._text.tag_configure("warning", foreground=TERMINAL_COLORS["warning"])
        self._text.tag_configure("error", foreground=TERMINAL_COLORS["error"], font=("Cascadia Code", 10, "bold"))
        self._text.tag_configure("success", foreground=TERMINAL_COLORS["success"])
        self._text.tag_configure("timestamp", foreground=TERMINAL_COLORS["timestamp"])
        self._text.tag_configure("debug", foreground=TERMINAL_COLORS["debug"])
        self._text.tag_configure("separator", foreground=TERMINAL_COLORS["separator"])
        self._text.tag_configure("download", foreground=TERMINAL_COLORS["download"])
        self._text.tag_configure("metadata", foreground=TERMINAL_COLORS["download"])

    def append(self, message: str, level: str = "info", timestamp: str | None = None) -> None:
        """Append a log message to the terminal (thread-safe)."""
        if not message:
            return

        with self._lock:
            ts = timestamp or datetime.datetime.now().strftime("%H:%M:%S")
            self._log_buffer.append(f"[{ts}] [{level.upper()}] {message}")
            self._pending_messages.append((message, level, timestamp))
            if self._processing:
                return
            self._processing = True

        self.after_idle(self._process_pending)

    def _process_pending(self) -> None:
        """Process pending log messages from the queue."""
        with self._lock:
            if not self._pending_messages:
                self._processing = False
                return
            messages = self._pending_messages
            self._pending_messages = []

        for message, level, timestamp in messages:
            self._append_to_widget(message, level, timestamp)

        with self._lock:
            if self._pending_messages:
                self.after_idle(self._process_pending)
            else:
                self._processing = False

    def _append_to_widget(self, message: str, level: str, timestamp: str | None) -> None:
        """Internal method to append message to widget (must be called from main thread)."""
        try:
            self._text.configure(state="normal")

            if self._show_timestamp:
                ts = timestamp or datetime.datetime.now().strftime("%H:%M:%S")
                self._text.insert("end", f" {ts} ", "timestamp")

            level_tag = self._get_level_tag(message, level)
            self._text.insert("end", f"{message}\n", level_tag)

            self._line_count += 1

            if self._line_count > self._max_lines:
                self._trim_lines()

            self._text.configure(state="disabled")

            if self._auto_scroll_var.get():
                self._text.see("end")
        except tk.TclError:
            pass

    def _get_level_tag(self, message: str, level: str) -> str:
        if "[ERROR]" in message or "[FATAL]" in message:
            return "error"
        if "[DOWNLOAD]" in message:
            return "download"
        if "[download]" in message:
            return "debug"
        if "[DONE]" in message:
            return "success"
        if "[METADATA]" in message or "[AUTH]" in message or "[SUB]" in message:
            return "metadata"
        if "[WARNING]" in message or "[RETRY]" in message:
            return "warning"
        if "[CANCEL]" in message or "[INFO]" in message or "[PLAYLIST]" in message or "[SEARCH]" in message:
            return "info"
        return level

    def append_separator(self, text: str = "") -> None:
        """Append a separator line (thread-safe)."""
        sep_text = f" {'─' * 40} "
        if text:
            sep_text = f" {'─' * 15} {text} {'─' * 15} "
        
        def do_append() -> None:
            try:
                self._text.configure(state="normal")
                self._text.insert("end", sep_text + "\n", "separator")
                self._text.configure(state="disabled")
            except tk.TclError:
                pass
        
        self.after_idle(do_append)

    def clear(self) -> None:
        """Clear all log output (thread-safe)."""
        def do_clear() -> None:
            try:
                with self._lock:
                    self._pending_messages.clear()
                    self._processing = False
                self._text.configure(state="normal")
                self._text.delete("1.0", "end")
                self._text.configure(state="disabled")
                self._line_count = 0
            except tk.TclError:
                pass
        
        self.after_idle(do_clear)

    def get_logs(self) -> str:
        with self._lock:
            return "\n".join(self._log_buffer)

    def export_to_file(self, path: Path) -> None:
        content = self.get_logs()
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            f.write("\n")

    def _trim_lines(self) -> None:
        """Remove oldest lines when max is reached."""
        lines_to_remove = self._max_lines // 10
        for _ in range(lines_to_remove):
            self._text.delete("1.0", "2.0")
        self._line_count = max(0, self._line_count - lines_to_remove)

    def set_auto_scroll(self, enabled: bool) -> None:
        """Enable or disable auto-scrolling."""
        self._auto_scroll_var.set(enabled)
