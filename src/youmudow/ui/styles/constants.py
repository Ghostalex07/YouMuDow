"""UI constants, color resolution, and shared helpers."""

import platform
import tkinter as tk

from youmudow.ui.styles.theme import get_theme_manager

_SYSTEM = platform.system()

if _SYSTEM == "Windows":
    _SANS = "Segoe UI"
    _MONO = "Cascadia Code"
elif _SYSTEM == "Darwin":
    _SANS = "SF Pro Text"
    _MONO = "Menlo"
else:
    _SANS = "Ubuntu"
    _MONO = "Ubuntu Mono"

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "2xl": 32,
}

FONT = {
    "h1": (_SANS, 14, "bold"),
    "h2": (_SANS, 12, "bold"),
    "h3": (_SANS, 11, "bold"),
    "body": (_SANS, 10),
    "small": (_SANS, 9),
    "label": (_SANS, 9, "bold"),
    "mono": (_MONO, 10),
}

_COLOR_MAP = {
    "bg": "BACKGROUND",
    "surface": "SURFACE",
    "primary": "PRIMARY",
    "secondary": "SECONDARY",
    "accent": "ACCENT",
    "text": "TEXT",
    "text_secondary": "TEXT_SECONDARY",
    "border": "BORDER",
    "success": "SUCCESS",
    "warning": "WARNING",
    "error": "ERROR",
    "info": "DOWNLOADING",
    "hover": "HOVER",
    "selection": "SELECTION",
    "input_bg": "SURFACE",
}


def _c(key: str) -> str:
    colors = get_theme_manager().colors
    return getattr(colors, _COLOR_MAP.get(key, key.upper()), "#000000")


def add_hover_effect(
    widget: tk.Widget,
    enter_key: str,
    leave_key: str,
    enter_fg: str | None = None,
    leave_fg: str | None = None,
) -> None:
    def on_enter(e: tk.Event) -> None:
        widget.configure(bg=_c(enter_key))
        if enter_fg:
            widget.configure(fg=enter_fg)

    def on_leave(e: tk.Event) -> None:
        widget.configure(bg=_c(leave_key))
        if leave_fg:
            widget.configure(fg=leave_fg)

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)
