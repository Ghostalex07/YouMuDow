"""Search bar widget for YouMuDow."""

import tkinter as tk

from youmudow.domain.validators import is_supported_url
from youmudow.ui.protocols import MainWindowProtocol
from youmudow.ui.styles.constants import FONT, SPACING, _c
from youmudow.ui.widgets.components.rounded_button import RoundedButton
from youmudow.ui.widgets.components.search_entry import SearchEntry
from youmudow.ui.widgets.components.spinner import Spinner

_PLACEHOLDER = "Search or paste URL (YouTube, SoundCloud, Vimeo...)"


class SearchBar(tk.Frame):
    def __init__(self, parent: tk.Widget, main_window: MainWindowProtocol) -> None:
        super().__init__(parent, bg=_c("bg"))
        self._mw = main_window
        self.grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=SPACING["xl"], pady=SPACING["lg"]
        )

        self._search_var = tk.StringVar()

        self._entry = SearchEntry(
            self,
            placeholder=_PLACEHOLDER,
            textvariable=self._search_var,
            command=self._on_submit,
        )
        self._entry.pack(side="left", fill="both", expand=True, padx=(0, SPACING["sm"]))

        self._spinner = Spinner(self, size=18, color="primary")

        def _on_paste(event) -> str | None:
            try:
                clipboard = self._mw._root.clipboard_get()
            except tk.TclError:
                return None
            if is_supported_url(clipboard):
                self._search_var.set(clipboard)
                return "break"
            return None

        self._entry.bind_shortcut(
            "<Control-Return>",
            lambda _: (
                self._mw._on_download_now() if self._mw._selected_video else self._mw._on_search()
            ),
        )
        self._entry.bind_shortcut("<Control-v>", _on_paste)
        self._entry.bind_shortcut("<Control-V>", _on_paste)
        self._entry.bind_shortcut("<Control-a>", self._on_select_all)
        self._entry.bind_shortcut("<Control-A>", self._on_select_all)
        self._entry.bind_shortcut("<Control-BackSpace>", self._on_delete_word)

        self._search_btn = RoundedButton(
            self,
            "Search",
            command=lambda: self._mw._on_search(),
            variant="primary",
            font=FONT["h3"],
        )
        self._search_btn.pack(side="left", padx=(SPACING["sm"], 0))

        self._cancel_btn = RoundedButton(
            self,
            "Cancel",
            command=lambda: self._mw._on_cancel_search(),
            variant="secondary",
        )
        self._cancel_btn.pack(side="left", padx=(SPACING["xs"], 0))
        self._cancel_btn.set_enabled(False)

        self._cancel_dl_btn = RoundedButton(
            self,
            "Stop",
            command=lambda: self._mw._on_cancel_download(),
            variant="danger",
        )
        self._cancel_dl_btn.pack(side="left", padx=(SPACING["xs"], 0))
        self._cancel_dl_btn.set_enabled(False)

        self._entry.focus_set()

    @property
    def search_var(self) -> tk.StringVar:
        return self._search_var

    @property
    def search_entry(self) -> SearchEntry:
        return self._entry

    def update_history(self, history: list[str]) -> None:
        self._entry.set_history(history)

    def _on_submit(self) -> None:
        self._mw._on_search()

    def _on_select_all(self, event: tk.Event) -> str | None:
        self._entry.select_all()
        return "break"

    def _on_delete_word(self, event: tk.Event) -> str | None:
        current = self._search_var.get()
        if current:
            words = current.split()
            if words:
                self._search_var.set(" ".join(words[:-1]))
        return "break"

    def get_query(self) -> str:
        return self._entry.get().strip()

    def update_button_states(self, is_searching: bool, is_downloading: bool) -> None:
        is_busy = is_searching or is_downloading
        self._search_btn.set_enabled(not is_busy)
        self._cancel_btn.set_enabled(is_searching)
        self._cancel_dl_btn.set_enabled(is_downloading)
        if is_searching:
            self._spinner.start()
            self._spinner.pack(side="left", before=self._search_btn, padx=(SPACING["xs"], 0))
        else:
            self._spinner.stop()
            self._spinner.pack_forget()
