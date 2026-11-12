"""SearchEntry component: a placeholder-aware text entry with a focus ring."""

import tkinter as tk

from youmudow.ui.styles.constants import FONT, SPACING, _c


class SearchEntry(tk.Frame):
    """A flat text entry that shows a placeholder when empty and fires a command on Return."""

    def __init__(self, master, *, placeholder="", textvariable=None, command=None):
        super().__init__(master, background=_c("surface"))
        self._command = command
        self._placeholder = placeholder
        self._showing_placeholder = False
        self._var = textvariable if textvariable is not None else tk.StringVar(self)

        self._entry = tk.Entry(
            self,
            textvariable=self._var,
            font=FONT["body"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=_c("border"),
            highlightcolor=_c("primary"),
            background=_c("surface"),
            foreground=_c("text"),
            insertbackground=_c("text"),
        )
        self._entry.pack(fill="both", expand=True, padx=SPACING["md"], pady=SPACING["sm"], ipady=4)

        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<Return>", self._on_return)

        self._show_placeholder_if_empty()

    def _on_focus_in(self, _event):
        self._entry.config(highlightcolor=_c("primary"))
        if self._showing_placeholder:
            self._var.set("")
            self._showing_placeholder = False
            self._entry.config(foreground=_c("text"))

    def _on_focus_out(self, _event):
        self._entry.config(highlightcolor=_c("border"))
        self._show_placeholder_if_empty()

    def _show_placeholder_if_empty(self):
        if self._placeholder and not self._var.get():
            self._var.set(self._placeholder)
            self._showing_placeholder = True
            self._entry.config(foreground=_c("text_secondary"))
        else:
            self._showing_placeholder = False
            self._entry.config(foreground=_c("text"))

    def _on_return(self, _event):
        if self._command is not None:
            self._command()

    def get(self) -> str:
        return "" if self._showing_placeholder else self._var.get()

    def set(self, value: str) -> None:
        self._var.set(value)
        if value == "":
            self._show_placeholder_if_empty()
        else:
            self._showing_placeholder = False
            self._entry.config(foreground=_c("text"))

    def clear(self) -> None:
        self._var.set("")
        self._show_placeholder_if_empty()

    def focus_set(self) -> None:
        self._entry.focus_set()
