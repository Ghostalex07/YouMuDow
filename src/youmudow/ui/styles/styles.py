"""TTK style definitions for YouMuDow.

Clam-based theme with consistent widget styling.
"""

from tkinter import ttk

from youmudow.ui.styles.colors import Colors
from youmudow.ui.styles.constants import FONT


class StyleManager:
    """Manages ttk styles for the application."""

    def __init__(self) -> None:
        self._style = ttk.Style()
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
            borderwidth=1,
            relief="solid",
            bordercolor=c.BORDER,
            padding=6,
        )
        self._style.configure("TEntry", insertcolor=c.TEXT)

        self._style.configure(
            "TCombobox",
            fieldbackground=c.SURFACE,
            foreground=c.TEXT,
            background=c.SURFACE,
            arrowcolor=c.TEXT,
            borderwidth=1,
            relief="solid",
            bordercolor=c.BORDER,
            padding=4,
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
            padding=(12, 6),
            font=FONT["body"],
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
            "Secondary.TButton",
            background=c.SURFACE,
            foreground=c.TEXT,
            borderwidth=1,
            bordercolor=c.BORDER,
            padding=(12, 6),
        )
        self._style.map(
            "Secondary.TButton",
            background=[
                ("active", c.HOVER),
                ("pressed", c.SURFACE),
                ("disabled", c.DISABLED),
            ],
            foreground=[("disabled", c.TEXT_SECONDARY)],
        )

        self._style.configure(
            "Success.TButton",
            background=c.SUCCESS,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(12, 6),
        )
        self._style.map(
            "Success.TButton",
            background=[
                ("active", c.SUCCESS),
                ("pressed", c.SUCCESS),
                ("disabled", c.DISABLED),
            ],
            foreground=[("disabled", c.TEXT_SECONDARY)],
        )

        self._style.configure(
            "Danger.TButton",
            background=c.ERROR,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(12, 6),
        )
        self._style.map(
            "Danger.TButton",
            background=[
                ("active", c.ERROR),
                ("pressed", c.ERROR),
                ("disabled", c.DISABLED),
            ],
            foreground=[("disabled", c.TEXT_SECONDARY)],
        )

        self._style.configure(
            "Treeview",
            background=c.SURFACE,
            foreground=c.TEXT,
            fieldbackground=c.SURFACE,
            borderwidth=0,
            rowheight=36,
            font=FONT["body"],
        )
        self._style.configure(
            "Treeview.Heading",
            background=c.BACKGROUND,
            foreground=c.TEXT_SECONDARY,
            borderwidth=0,
            padding=(8, 6),
            font=FONT["label"],
        )
        self._style.map(
            "Treeview",
            background=[("selected", c.SELECTION)],
            foreground=[("selected", c.TEXT)],
        )

        self._style.configure(
            "Horizontal.TProgressbar",
            background=c.PRIMARY,
            troughcolor=c.BORDER,
            borderwidth=0,
            thickness=4,
        )

        self._style.configure(
            "TCheckbutton",
            background=c.SURFACE,
            foreground=c.TEXT,
            indicatorcolor=c.SURFACE,
            borderwidth=1,
            bordercolor=c.BORDER,
        )
        self._style.map(
            "TCheckbutton",
            background=[("active", c.SURFACE)],
            indicatorcolor=[
                ("selected", c.PRIMARY),
                ("!selected", c.SURFACE),
            ],
        )

        self._style.configure(
            "TSeparator",
            background=c.BORDER,
        )

    def _apply_custom_widgets(self) -> None:
        if self._colors is None:
            return

        c = self._colors

        self._style.configure(
            "Search.TCombobox",
            fieldbackground=c.SURFACE,
            foreground=c.TEXT,
            background=c.SURFACE,
            arrowcolor=c.TEXT,
            borderwidth=0,
            padding=8,
        )
        self._style.map(
            "Search.TCombobox",
            fieldbackground=[("focus", c.SURFACE)],
            foreground=[("focus", c.TEXT)],
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
            padding=(16, 6),
        )
        self._style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", c.BACKGROUND), ("active", c.HOVER)],
            foreground=[("selected", c.TEXT)],
        )


def configure_styles(colors: Colors) -> StyleManager:
    manager = StyleManager()
    manager.configure(colors)
    return manager
