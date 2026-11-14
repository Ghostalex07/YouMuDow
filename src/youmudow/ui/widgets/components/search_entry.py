"""SearchEntry component: a placeholder-aware text entry with a focus ring."""

import tkinter as tk
from collections.abc import Callable

from youmudow.ui.styles.constants import FONT, SPACING, _c
from youmudow.ui.typed import configure_widget


class SearchEntry(tk.Frame):
    """A flat text entry that shows a placeholder when empty and fires a command on Return."""

    def __init__(
        self,
        master,
        *,
        placeholder: str = "",
        textvariable: tk.StringVar | None = None,
        command: Callable[[], None] | None = None,
        history: list[str] | None = None,
    ) -> None:
        super().__init__(master, background=_c("surface"))
        self._bg_key = "surface"
        self._command = command
        self._placeholder = placeholder
        self._showing_placeholder = False
        self._history: list[str] = list(history or [])
        self._history_listbox: tk.Listbox | None = None
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
        self._entry.pack(
            fill="both",
            expand=True,
            padx=(SPACING["md"], SPACING["xl"]),
            pady=SPACING["sm"],
            ipady=4,
        )

        self._clear_button = tk.Label(
            self,
            text="\u00d7",
            font=FONT["body"],
            cursor="hand2",
            padx=SPACING["xs"],
            background=_c("surface"),
            foreground=_c("text_secondary"),
        )
        self._clear_button.bind("<Button-1>", self._on_clear_click)

        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<Return>", self._on_return)
        self._entry.bind("<Down>", self._on_down)
        self._entry.bind("<Up>", self._on_up)
        self._entry.bind("<Escape>", self._on_escape)

        self._var.trace_add("write", self._on_var_changed)
        self._show_placeholder_if_empty()

    def _on_var_changed(self, *_args) -> None:
        """Keep the placeholder state in sync when the variable changes externally."""
        if self._showing_placeholder and self._var.get() != self._placeholder:
            self._showing_placeholder = False
            self._entry.config(foreground=_c("text"))
        elif not self._showing_placeholder and not self._var.get():
            self._show_placeholder_if_empty()
        self._update_clear_button()

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
        self._update_clear_button()

    def _on_return(self, _event):
        if self._history_listbox is not None and self.history_is_open():
            self._on_history_select(None)
            return
        if self._command is not None:
            self._command()

    def _on_down(self, _event) -> str | None:
        if self.history_is_open():
            self._move_history_selection(1)
            return "break"
        if self._history:
            self.open_history()
            return "break"
        return None

    def _on_up(self, _event) -> str | None:
        if not self.history_is_open():
            return None
        self._move_history_selection(-1)
        return "break"

    def _on_escape(self, _event) -> str | None:
        if not self.history_is_open():
            return None
        self.close_history()
        return "break"

    def _move_history_selection(self, step: int) -> None:
        """Move the highlight through the dropdown, wrapping at the ends."""
        if not self.history_is_open():
            self.open_history()
        listbox = self._ensure_history_listbox()
        size = listbox.size()
        if size == 0:
            return
        selection = listbox.curselection()
        index = selection[0] if selection else (-1 if step > 0 else 0)
        index = (index + step) % size
        listbox.selection_clear(0, "end")
        listbox.selection_set(index)
        listbox.activate(index)
        listbox.see(index)

    def get(self) -> str:
        """Return the typed text, or an empty string while the placeholder shows."""
        if self._showing_placeholder:
            return ""
        if self._var.get() == self._placeholder:
            return ""
        return self._var.get()

    def set(self, value: str) -> None:
        self._var.set(value)
        if value == "":
            self._show_placeholder_if_empty()
        else:
            self._showing_placeholder = False
            self._entry.config(foreground=_c("text"))

    def clear(self) -> None:
        """Empty the field, close the dropdown and restore the placeholder."""
        self.close_history()
        self._var.set("")
        self._showing_placeholder = False
        self._show_placeholder_if_empty()

    def focus_set(self) -> None:
        self._entry.focus_set()

    def bind_shortcut(self, sequence: str, handler: Callable[[tk.Event], str | None]) -> None:
        """Bind a key sequence on the text entry without exposing the widget."""
        self._entry.bind(sequence, handler)

    def select_all(self) -> None:
        """Select the whole query, so a paste replaces it instead of appending."""
        self._entry.select_range(0, "end")

    def _update_clear_button(self) -> None:
        """Show the clear affordance only while there is something to clear."""
        if self.get():
            self._clear_button.place(relx=1.0, rely=0.5, anchor="e", x=-SPACING["md"])
        else:
            self._clear_button.place_forget()

    def _on_clear_click(self, _event) -> str:
        self.clear()
        self.focus_set()
        return "break"

    # ------------------------------------------------------------------
    # History dropdown
    # ------------------------------------------------------------------

    def _ensure_history_listbox(self) -> tk.Listbox:
        """Create the dropdown on first use so an unused entry stays cheap."""
        if self._history_listbox is None:
            listbox = tk.Listbox(
                self,
                relief="flat",
                bd=0,
                highlightthickness=1,
                activestyle="none",
                exportselection=False,
            )
            configure_widget(
                listbox,
                bg=_c("surface"),
                fg=_c("text"),
                selectbackground=_c("primary"),
                selectforeground="#FFFFFF",
                highlightbackground=_c("border"),
                highlightcolor=_c("primary"),
            )
            listbox.bind("<Double-Button-1>", self._on_history_select)
            listbox.bind("<Return>", self._on_history_select)
            listbox.bind("<FocusOut>", self._on_history_focus_out)
            self._history_listbox = listbox
        return self._history_listbox

    def open_history(self) -> None:
        """Show the history dropdown below the entry, if there is any history."""
        if not self._history:
            return
        listbox = self._ensure_history_listbox()
        listbox.delete(0, "end")
        for item in self._history:
            listbox.insert("end", item)
        listbox.place(relx=0, rely=1, anchor="nw", width=self.winfo_width())
        listbox.lift()

    def close_history(self) -> None:
        """Hide the history dropdown if it is open."""
        if self._history_listbox is not None:
            self._history_listbox.place_forget()

    def history_is_open(self) -> bool:
        """Whether the history dropdown is currently visible."""
        if self._history_listbox is None:
            return False
        return bool(self._history_listbox.winfo_manager())

    def set_history(self, history: list[str]) -> None:
        """Replace the stored history, refreshing an open dropdown."""
        self._history = list(history)
        if self.history_is_open():
            self.open_history()

    def _on_history_select(self, _event) -> None:
        listbox = self._history_listbox
        if listbox is None:
            return
        selection = listbox.curselection()
        if not selection:
            return
        value = listbox.get(selection[0])
        self.close_history()
        self.set(value)
        if self._command is not None:
            self._command()

    def _on_history_focus_out(self, _event) -> None:
        self.close_history()
