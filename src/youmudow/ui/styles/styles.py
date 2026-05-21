"""TTK style definitions for YouMuDow.

Modern dark theme with smooth visuals and consistent styling.
"""

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
        self._apply_custom_widgets()

    def _apply_base_styles(self) -> None:
        if self._colors is None:
            return

        c = self._colors

        self._style.theme_use("clam")

        self._style.configure(".", background=c.BACKGROUND)

        self._style.configure("TFrame", background=c.BACKGROUND)
        self._style.configure("TLabel", background=c.BACKGROUND, foreground=c.TEXT)
        self._style.configure("TLabelframe", background=c.BACKGROUND, foreground=c.TEXT)
        self._style.configure("TLabelframe.Label", background=c.BACKGROUND, foreground=c.TEXT)

        self._style.configure(
            "TEntry",
            fieldbackground=c.SURFACE,
            foreground=c.TEXT,
            borderwidth=0,
            relief="flat",
        )
        self._style.configure("TEntry", insertcolor=c.TEXT)

        self._style.configure(
            "TCombobox",
            fieldbackground=c.SURFACE,
            foreground=c.TEXT,
            background=c.SURFACE,
            borderwidth=0,
            relief="flat",
        )

    def _apply_widget_styles(self) -> None:
        if self._colors is None:
            return

        c = self._colors

        self._style.configure(
            "TButton",
            background=c.PRIMARY,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(16, 10),
            font=("Segoe UI", 10),
        )
        self._style.map(
            "TButton",
            background=[
                ("active", c.SECONDARY),
                ("pressed", c.PRIMARY),
                ("disabled", c.DISABLED),
            ],
            foreground=[("disabled", c.TEXT_SECONDARY)],
        )

        self._style.configure(
            "Primary.TButton",
            background=c.PRIMARY,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(16, 10),
            font=("Segoe UI", 10, "bold"),
        )
        self._style.map(
            "Primary.TButton",
            background=[
                ("active", c.SECONDARY),
                ("pressed", c.PRIMARY),
                ("disabled", c.DISABLED),
            ],
        )

        self._style.configure(
            "Secondary.TButton",
            background=c.SURFACE,
            foreground=c.TEXT,
            borderwidth=1,
            bordercolor=c.BORDER,
            padding=(16, 10),
            font=("Segoe UI", 10),
        )
        self._style.map(
            "Secondary.TButton",
            background=[
                ("active", c.HOVER),
                ("pressed", c.SURFACE),
                ("disabled", c.DISABLED),
            ],
        )

        self._style.configure(
            "Success.TButton",
            background=c.SUCCESS,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(16, 10),
            font=("Segoe UI", 10),
        )
        self._style.map(
            "Success.TButton",
            background=[
                ("active", "#16A34A"),
                ("pressed", c.SUCCESS),
                ("disabled", c.DISABLED),
            ],
        )

        self._style.configure(
            "Treeview",
            background=c.SURFACE,
            foreground=c.TEXT,
            fieldbackground=c.SURFACE,
            borderwidth=0,
            rowheight=36,
            font=("Segoe UI", 10),
        )
        self._style.configure(
            "Treeview.Heading",
            background=c.SURFACE,
            foreground=c.TEXT_SECONDARY,
            borderwidth=0,
            padding=8,
            font=("Segoe UI", 9, "bold"),
        )
        self._style.map(
            "Treeview",
            background=[("selected", c.SELECTION)],
            foreground=[("selected", c.TEXT)],
        )

        self._style.configure(
            "Horizontal.TProgressbar",
            background=c.PRIMARY,
            borderwidth=0,
            thickness=6,
        )
        self._style.configure(
            "Success.Horizontal.TProgressbar",
            background=c.SUCCESS,
            borderwidth=0,
            thickness=6,
        )

    def _apply_custom_widgets(self) -> None:
        if self._colors is None:
            return

        c = self._colors

        self._style.configure(
            "Search.TEntry",
            fieldbackground=c.SURFACE,
            foreground=c.TEXT,
            borderwidth=0,
            padding=10,
            font=("Segoe UI", 11),
        )

        self._style.configure(
            "Search.TCombobox",
            fieldbackground=c.SURFACE,
            foreground=c.TEXT,
            background=c.SURFACE,
            arrowcolor=c.TEXT,
            borderwidth=1,
            relief="solid",
        )
        self._style.map(
            "Search.TCombobox",
            fieldbackground=[("focus", c.SURFACE)],
            foreground=[("focus", c.TEXT)],
        )

        self._style.configure(
            "Card.TFrame",
            background=c.SURFACE,
            relief="flat",
        )

        self._style.configure(
            "Modern.TNotebook",
            background=c.BACKGROUND,
            borderwidth=0,
        )
        self._style.configure(
            "Modern.TNotebook.Tab",
            background=c.SURFACE,
            foreground=c.TEXT_SECONDARY,
            padding=(20, 6),
            font=("Segoe UI", 10),
        )
        self._style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", c.BACKGROUND), ("active", c.HOVER)],
            foreground=[("selected", c.TEXT)],
        )


def configure_styles(root: tk.Tk, colors: Colors) -> StyleManager:
    manager = StyleManager(root)
    manager.configure(colors)
    return manager
