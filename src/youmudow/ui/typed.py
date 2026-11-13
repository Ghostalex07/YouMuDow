"""Typed helpers for Tkinter's dynamically typed surface.

Tkinter's ``configure`` accepts arbitrary keyword arguments and mypy cannot
check them; widgets also carry dynamic attributes such as ``_bg_key``. These
helpers give both a single, checked entry point.
"""

from __future__ import annotations

import tkinter as tk

FontSpec = tuple[str, int] | tuple[str, int, str]


def configure_widget(widget: tk.Misc, **options: str) -> None:
    """Apply widget options, ignoring options the widget does not accept."""
    try:
        widget.configure(**options)
    except tk.TclError:
        pass


def setattr_any(obj: object, name: str, value: object) -> None:
    """Set a dynamic attribute on an otherwise statically typed object."""
    object.__setattr__(obj, name, value)
