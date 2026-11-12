"""A centered placeholder shown when a list has no content."""

import tkinter as tk

from youmudow.ui.styles.constants import FONT, _c
from youmudow.ui.widgets.components.rounded_button import RoundedButton


class EmptyState(tk.Frame):
    """A centered icon, message and optional action button."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        icon: str = "",
        message: str = "",
        action_text: str | None = None,
        action_command=None,
    ) -> None:
        super().__init__(master, background=_c("background"))
        self._icon_label = tk.Label(
            self,
            text=icon,
            font=FONT["h1"],
            background=_c("background"),
            foreground=_c("text_secondary"),
        )
        self._icon_label.pack(pady=(0, 8))
        self._message_label = tk.Label(
            self,
            text=message,
            font=FONT["body"],
            background=_c("background"),
            foreground=_c("text_secondary"),
        )
        self._message_label.pack()
        self._action_button: RoundedButton | None = None
        if action_text is not None:
            self._action_button = RoundedButton(
                self, action_text, command=action_command, variant="secondary"
            )
            self._action_button.pack(pady=(16, 0))
