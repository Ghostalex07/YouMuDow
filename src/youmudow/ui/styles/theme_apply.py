"""Per-widget theme application for the Tkinter UI.

Each Tk widget class gets one small styling rule, and the recursive walk over
the widget tree is a separate function. Keeping the rules as a table means the
theme repaint can be unit tested with a bare ``tk.Tk`` root instead of a whole
application window, and adding a widget class no longer grows a mega-method.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

from youmudow.ui.styles.constants import _COLOR_MAP

ColorRule = Callable[[tk.Widget, Any], None]


def resolve_color(colors: Any, key: str) -> str:
    """Resolve a colour key (``"surface"``) or a literal (``"#112233"``)."""
    if key.startswith("#"):
        return key
    return getattr(colors, _COLOR_MAP.get(key, key.upper()), "#000000")


def _parent_background(widget: tk.Widget, colors: Any) -> str:
    try:
        return str(widget.master.cget("bg"))
    except (tk.TclError, AttributeError):
        return str(colors.BACKGROUND)


def _style_frame(widget: tk.Widget, colors: Any) -> None:
    widget.configure(bg=resolve_color(colors, getattr(widget, "_bg_key", "bg")))
    border_key = getattr(widget, "_border_key", None)
    if border_key is not None:
        widget.configure(highlightbackground=resolve_color(colors, border_key))


def _style_label(widget: tk.Widget, colors: Any) -> None:
    widget.configure(bg=_parent_background(widget, colors), fg=colors.TEXT)


def _style_button(widget: tk.Widget, colors: Any) -> None:
    theme = getattr(widget, "_theme", None)
    if theme:
        background = theme.get("bg", "surface")
        foreground = theme.get("fg", "text")
        widget.configure(
            bg=resolve_color(colors, background),
            fg=resolve_color(colors, foreground),
            activebackground=resolve_color(colors, theme.get("activebg", background)),
            activeforeground=resolve_color(colors, theme.get("activefg", foreground)),
        )
        return
    widget.configure(
        bg=colors.SURFACE,
        fg=colors.TEXT,
        activebackground=colors.HOVER,
        activeforeground=colors.TEXT,
    )


def _style_entry(widget: tk.Widget, colors: Any) -> None:
    widget.configure(
        bg=colors.SURFACE,
        fg=colors.TEXT,
        insertbackground=colors.TEXT,
        highlightbackground=colors.BORDER,
        highlightcolor=colors.PRIMARY,
    )


def _style_toggle(widget: tk.Widget, colors: Any) -> None:
    try:
        parent_bg = str(widget.master.cget("bg"))
    except (tk.TclError, AttributeError):
        parent_bg = str(colors.SURFACE)
    widget.configure(
        bg=parent_bg,
        fg=colors.TEXT,
        selectcolor=parent_bg,
        activebackground=parent_bg,
        activeforeground=colors.TEXT,
    )


def _style_canvas(widget: tk.Widget, colors: Any) -> None:
    widget.configure(bg=resolve_color(colors, getattr(widget, "_bg_key", "bg")))


def _style_menu(widget: tk.Widget, colors: Any) -> None:
    widget.configure(bg=colors.SURFACE, fg=colors.TEXT)


_RULES: dict[str, ColorRule] = {
    "Frame": _style_frame,
    "Labelframe": _style_frame,
    "Label": _style_label,
    "Button": _style_button,
    "Entry": _style_entry,
    "Checkbutton": _style_toggle,
    "Radiobutton": _style_toggle,
    "Canvas": _style_canvas,
    "Menu": _style_menu,
}


def apply_widget_colors(widget: tk.Widget, colors: Any) -> None:
    """Apply the colour rule for this widget's class, if it has one.

    Widget classes without a rule (for example ttk widgets, which are styled
    through ``ttk.Style``) are left untouched.
    """
    try:
        rule = _RULES.get(widget.winfo_class())
    except tk.TclError:
        return
    if rule is None:
        return
    try:
        rule(widget, colors)
    except tk.TclError:
        pass


def apply_theme_colors(widget: tk.Widget, colors: Any) -> None:
    """Apply theme colours to ``widget`` and every descendant it owns."""
    apply_widget_colors(widget, colors)
    try:
        children = widget.winfo_children()
    except tk.TclError:
        children = []
    for child in children:
        apply_theme_colors(child, colors)
    # Canvas ``window`` items are not ``winfo_children``, so recurse into
    # them explicitly (scrollable card lists embed their content this way).
    try:
        if widget.winfo_class() == "Canvas":
            for item in widget.find_all():
                if widget.type(item) == "window":
                    child = widget.nametowidget(widget.itemcget(item, "window"))
                    apply_theme_colors(child, colors)
    except tk.TclError:
        pass
