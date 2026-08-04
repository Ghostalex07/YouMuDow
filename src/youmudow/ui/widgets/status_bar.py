"""Status bar widget for YouMuDow."""

import tkinter as tk

from youmudow.ui.styles.constants import FONT, SPACING, _c


class StatusBar(tk.Frame):
    def __init__(self, parent: tk.Widget, main_window: object) -> None:
        super().__init__(parent, bg=_c("surface"))
        self._mw = main_window
        self._bg_key = "surface"
        self.grid(row=1, column=0, sticky="ew", padx=SPACING["md"], pady=SPACING["sm"])
        self.columnconfigure(0, weight=1)

        self._status_var = tk.StringVar(value="Ready")
        self._status_label = tk.Label(
            self,
            textvariable=self._status_var,
            bg=_c("surface"),
            fg=_c("text_secondary"),
            font=FONT["small"],
            anchor="w",
        )
        self._status_label.grid(row=0, column=0, sticky="w")

        progress_frame = tk.Frame(self, bg=_c("surface"), height=6)
        progress_frame._bg_key = "surface"
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(SPACING["sm"], 0))
        progress_frame.columnconfigure(0, weight=1)

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = tk.Canvas(
            progress_frame,
            bg=_c("surface"),
            height=6,
            highlightthickness=0,
            relief="flat",
        )
        self._progress_bar._bg_key = "bg"
        self._progress_bar.pack(fill="x")
        self._progress_rect = self._progress_bar.create_rectangle(
            0, 0, 0, 6, fill=_c("primary"), outline=""
        )

    def set_status(self, message: str) -> None:
        self._status_var.set(message)

    def update_progress_bar(self) -> None:
        try:
            width = self._progress_bar.winfo_width()
            width = max(width, 1)
            progress = self._progress_var.get() / 100.0
            x_pos = width * progress
            self._progress_bar.coords(self._progress_rect, 0, 0, x_pos, 6)
        except tk.TclError:
            pass

    @property
    def progress_var(self) -> tk.DoubleVar:
        return self._progress_var

    def set_progress_color(self, color: str) -> None:
        try:
            self._progress_bar.itemconfig(self._progress_rect, fill=color)
        except tk.TclError:
            pass
