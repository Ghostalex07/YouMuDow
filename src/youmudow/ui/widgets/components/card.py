"""Card container: a surface-colored panel with a subtle border and padding."""

import tkinter as tk

from youmudow.ui.styles.constants import SPACING, _c


class Card(tk.Frame):
    """A flat container with the surface color, a 1px border, and even padding."""

    def __init__(self, master, *, padding: int = SPACING["md"], **kwargs):
        super().__init__(
            master,
            background=_c("surface"),
            highlightbackground=_c("border"),
            highlightthickness=1,
            padx=padding,
            pady=padding,
            **kwargs,
        )
