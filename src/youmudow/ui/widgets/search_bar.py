"""Search bar widget for YouMuDow."""

import tkinter as tk
from tkinter import ttk

from youmudow.ui.styles.constants import SPACING, FONT, _c, add_hover_effect
from youmudow.domain.validators import is_supported_url


class SearchBar(tk.Frame):
    def __init__(self, parent: tk.Widget, main_window: object) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._mw = main_window
        self.grid(row=0, column=0, columnspan=2, sticky="ew",
                  padx=SPACING["md"], pady=SPACING["md"])

        entry_frame = tk.Frame(
            self, bg=_c("surface"),
            highlightthickness=1, highlightbackground=_c("border"),
        )
        entry_frame._bg_key = "surface"
        entry_frame.pack(side="left", fill="both", expand=True, padx=(0, SPACING["sm"]))
        entry_frame.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        self._search_combo = ttk.Combobox(
            entry_frame,
            textvariable=self._search_var,
            font=("Segoe UI", 12),
            style="Search.TCombobox",
        )
        self._search_combo.grid(row=0, column=0, sticky="ew", padx=SPACING["md"], pady=SPACING["md"])

        def _on_paste(event) -> str | None:
            try:
                clipboard = self._mw._root.clipboard_get()
            except tk.TclError:
                return None
            if is_supported_url(clipboard):
                self._search_var.set(clipboard)
                return "break"
            return None

        self._search_combo.bind("<Return>", lambda _: self._mw._on_search())
        self._search_combo.bind("<Control-Return>", lambda _: self._mw._on_download_now() if self._mw._selected_video else self._mw._on_search())
        self._search_combo.bind("<Control-v>", _on_paste)
        self._search_combo.bind("<Control-V>", _on_paste)
        self._search_combo.bind("<Control-a>", self._on_select_all)
        self._search_combo.bind("<Control-A>", self._on_select_all)
        self._search_combo.bind("<Control-BackSpace>", self._on_delete_word)

        self._search_btn = tk.Button(
            self, text="Search",
            bg=_c("primary"), fg="#FFFFFF",
            activebackground=_c("secondary"), activeforeground="#FFFFFF",
            relief="flat", bd=0, font=FONT["h2"],
            command=lambda: self._mw._on_search(),
        )
        self._search_btn._theme = {"bg": "primary", "fg": "#FFFFFF", "activebg": "secondary", "activefg": "#FFFFFF"}
        self._search_btn.pack(side="left", padx=(SPACING["sm"], 0))
        add_hover_effect(self._search_btn, "secondary", "primary")

        self._cancel_btn = tk.Button(
            self, text="Cancel",
            bg=_c("surface"), fg=_c("text"),
            activebackground=_c("hover"), activeforeground=_c("text"),
            relief="flat", bd=0, font=FONT["body"],
            command=lambda: self._mw._on_cancel_search(),
        )
        self._cancel_btn._theme = {"bg": "surface", "fg": "text", "activebg": "hover", "activefg": "text"}
        self._cancel_btn.pack(side="left", padx=(SPACING["xs"], 0))
        self._cancel_btn.configure(state="disabled")
        add_hover_effect(self._cancel_btn, "hover", "surface")

        self._cancel_dl_btn = tk.Button(
            self, text="Stop DL",
            bg=_c("error"), fg="#FFFFFF",
            activebackground=_c("warning"), activeforeground="#000000",
            relief="flat", bd=0, font=FONT["body"],
            command=lambda: self._mw._on_cancel_download(),
        )
        self._cancel_dl_btn._theme = {"bg": "error", "fg": "#FFFFFF", "activebg": "warning", "activefg": "#000000"}
        self._cancel_dl_btn.pack(side="left", padx=(SPACING["xs"], 0))
        self._cancel_dl_btn.configure(state="disabled")
        add_hover_effect(self._cancel_dl_btn, "warning", "error")

        self._placeholder = "Search or paste URL (YouTube, SoundCloud, Vimeo...)"
        self._search_combo.set("")

        def _on_focus_in(event: tk.Event) -> None:
            if self._search_var.get() == self._placeholder:
                self._search_var.set("")

        def _on_focus_out(event: tk.Event) -> None:
            if not self._search_var.get().strip():
                self._search_combo.set(self._placeholder)

        self._search_combo.bind("<FocusIn>", _on_focus_in)
        self._search_combo.bind("<FocusOut>", _on_focus_out)
        self._search_combo.focus()

    @property
    def search_var(self) -> tk.StringVar:
        return self._search_var

    @property
    def search_entry(self) -> ttk.Combobox:
        return self._search_combo

    def update_history(self, history: list[str]) -> None:
        self._search_combo["values"] = history

    def _on_select_all(self, event: tk.Event) -> str | None:
        self._search_combo.select_range(0, "end")
        return "break"

    def _on_delete_word(self, event: tk.Event) -> str | None:
        current = self._search_var.get()
        if current:
            words = current.split()
            if words:
                self._search_var.set(" ".join(words[:-1]))
        return "break"

    def get_query(self) -> str:
        text = self._search_var.get().strip()
        if text == self._placeholder:
            return ""
        return text

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None:
        is_busy = is_searching or is_downloading
        self._search_btn.configure(state="disabled" if is_busy else "normal")
        self._cancel_btn.configure(state="normal" if is_searching else "disabled")
        self._cancel_dl_btn.configure(state="normal" if is_downloading else "disabled")


