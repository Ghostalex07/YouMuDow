"""TTK style definitions for YouMuDow."""

import tkinter as tk
from tkinter import ttk

from youmudow.ui.styles.colors import Colors


class StyleManager:
    """Manages ttk styles for the application."""

    def __init__(self, root: tk.Tk | None = None) -> None:
        self._style = ttk.Style()
        self._root = root
        self._colors: Colors | None = None

    def configure(self, colors: Colors) -> None:
        self._colors = colors
        self._apply_base_styles()
        self._apply_widget_styles()

    def _apply_base_styles(self) -> None:
        if self._colors is None:
            return

        self._style.configure(".", background=self._colors.BACKGROUND)

        self._style.configure(
            "TFrame",
            background=self._colors.BACKGROUND,
        )
        self._style.configure(
            "TLabel",
            background=self._colors.BACKGROUND,
            foreground=self._colors.TEXT,
        )
        self._style.configure(
            "TButton",
            background=self._colors.PRIMARY,
            foreground="#FFFFFF",
        )
        self._style.configure(
            "TEntry",
            fieldbackground=self._colors.BACKGROUND,
            foreground=self._colors.TEXT,
            bordercolor=self._colors.BORDER,
        )
        self._style.configure(
            "TCombobox",
            fieldbackground=self._colors.BACKGROUND,
            background=self._colors.PRIMARY,
            foreground=self._colors.TEXT,
        )

    def _apply_widget_styles(self) -> None:
        if self._colors is None:
            return

        self._style.configure(
            "SearchBar.TFrame",
            background=self._colors.BACKGROUND,
        )
        self._style.configure(
            "SearchButton.TButton",
            background=self._colors.PRIMARY,
            foreground="#FFFFFF",
            padding=(10, 5),
        )
        self._style.map(
            "SearchButton.TButton",
            background=[("active", self._colors.SECONDARY)],
        )

        self._style.configure(
            "Results.Treeview",
            background=self._colors.BACKGROUND,
            foreground=self._colors.TEXT,
            fieldbackground=self._colors.BACKGROUND,
            rowheight=28,
        )
        self._style.map(
            "Results.Treeview",
            background=[("selected", self._colors.SELECTION)],
            foreground=[("selected", self._colors.TEXT)],
        )
        self._style.configure(
            "Results.Treeview.Heading",
            background=self._colors.FOREGROUND,
            foreground=self._colors.TEXT,
            relief="flat",
        )

        self._style.configure(
            "Detail.TLabelframe",
            background=self._colors.BACKGROUND,
            foreground=self._colors.TEXT,
        )
        self._style.configure(
            "Detail.TLabelframe.Label",
            background=self._colors.BACKGROUND,
            foreground=self._colors.TEXT,
            font=("TkDefaultFont", 10, "bold"),
        )

        self._style.configure(
            "ActionButton.TButton",
            padding=(15, 8),
        )
        self._style.map(
            "ActionButton.TButton",
            background=[
                ("active", self._colors.SECONDARY),
                ("disabled", self._colors.DISABLED),
            ],
        )

        self._style.configure(
            "StatusBar.TLabel",
            background=self._colors.FOREGROUND,
            foreground=self._colors.TEXT_SECONDARY,
            font=("TkDefaultFont", 9),
        )

        self._style.configure(
            "Primary.TButton",
            background=self._colors.PRIMARY,
            foreground="#FFFFFF",
            padding=(15, 8),
        )
        self._style.map(
            "Primary.TButton",
            background=[
                ("active", self._colors.SECONDARY),
                ("disabled", self._colors.DISABLED),
            ],
        )


def configure_styles(root: tk.Tk, colors: Colors) -> StyleManager:
    manager = StyleManager(root)
    manager.configure(colors)
    return manager
