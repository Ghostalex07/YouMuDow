"""Reusable status bar widget."""

import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Frame):
    """Reusable status bar widget with message and progress."""

    def __init__(
        self,
        parent: tk.Widget,
        show_progress: bool = True,
    ) -> None:
        super().__init__(parent, relief="sunken")
        self._show_progress = show_progress

        if show_progress:
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=0)
            self.rowconfigure(1, weight=0)
            self._create_status_label()
            self._create_progress_bar()
        else:
            self.columnconfigure(0, weight=1)
            self._create_status_label()

    def _create_status_label(self) -> None:
        self._status_var = tk.StringVar(value="Ready")
        row = 1 if self._show_progress else 0
        self._status_label = ttk.Label(
            self,
            textvariable=self._status_var,
            anchor="w",
            padding=(5, 2),
        )
        self._status_label.grid(row=row, column=0, sticky="ew")

    def _create_progress_bar(self) -> None:
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            self,
            variable=self._progress_var,
            maximum=100,
            mode="determinate",
        )
        self._progress_bar.grid(row=0, column=0, sticky="ew")

    def set_status(self, message: str) -> None:
        self._status_var.set(message)

    def get_status(self) -> str:
        return self._status_var.get()

    def set_progress(self, value: float) -> None:
        self._progress_var.set(value)

    def get_progress(self) -> float:
        return self._progress_var.get()

    def clear_progress(self) -> None:
        self._progress_var.set(0)

    def show_progress_bar(self, show: bool) -> None:
        if show and not self._show_progress:
            self._show_progress = True
            self.rowconfigure(0, weight=0)
            self.rowconfigure(1, weight=0)
            for widget in self.grid_slaves():
                widget.grid_forget()
            self._create_progress_bar()
            self._create_status_label()
        elif not show and self._show_progress:
            self._show_progress = False
            for widget in self.grid_slaves():
                widget.grid_forget()
            self._create_status_label()
