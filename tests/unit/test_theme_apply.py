"""Tests for per-widget theme application.

These tests use a bare ``tk.Tk`` root, so a single widget can be styled and
inspected without building the whole application window.
"""

import os
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.ui.styles.colors import DARK_COLORS, LIGHT_COLORS
from youmudow.ui.styles.styles import StyleManager, apply_theme
from youmudow.ui.styles.theme_apply import (
    apply_theme_colors,
    apply_widget_colors,
    resolve_color,
)


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


class TestResolveColor:
    def test_resolves_mapped_key_to_palette_attribute(self):
        assert resolve_color(DARK_COLORS, "surface") == DARK_COLORS.SURFACE
        assert resolve_color(DARK_COLORS, "text_secondary") == DARK_COLORS.TEXT_SECONDARY

    def test_returns_hex_literal_unchanged(self):
        assert resolve_color(DARK_COLORS, "#123456") == "#123456"

    def test_uses_upper_case_attribute_for_unmapped_key(self):
        colors = SimpleNamespace(CUSTOM="#aabbcc")

        assert resolve_color(colors, "custom") == "#aabbcc"

    def test_falls_back_to_black_for_unknown_key(self):
        assert resolve_color(DARK_COLORS, "no_such_colour") == "#000000"


class TestApplyWidgetColors:
    def test_frame_uses_bg_key_when_present(self, root):
        frame = tk.Frame(root, bg="#ffffff")
        frame._bg_key = "surface"

        apply_widget_colors(frame, DARK_COLORS)

        assert frame.cget("bg") == DARK_COLORS.SURFACE

    def test_frame_without_bg_key_uses_background(self, root):
        frame = tk.Frame(root, bg="#ffffff")

        apply_widget_colors(frame, DARK_COLORS)

        assert frame.cget("bg") == DARK_COLORS.BACKGROUND

    def test_label_takes_parent_background_and_text_color(self, root):
        parent = tk.Frame(root, bg="#222233")
        label = tk.Label(parent, bg="#ffffff", fg="#000000")

        apply_widget_colors(label, DARK_COLORS)

        assert label.cget("bg") == parent.cget("bg")
        assert label.cget("fg") == DARK_COLORS.TEXT

    def test_button_honours_theme_mapping(self, root):
        button = tk.Button(root)
        button._theme = {
            "bg": "primary",
            "fg": "bg",
            "activebg": "accent",
            "activefg": "surface",
        }

        apply_widget_colors(button, DARK_COLORS)

        assert button.cget("bg") == DARK_COLORS.PRIMARY
        assert button.cget("fg") == DARK_COLORS.BACKGROUND
        assert button.cget("activebackground") == DARK_COLORS.ACCENT
        assert button.cget("activeforeground") == DARK_COLORS.SURFACE

    def test_button_theme_falls_back_to_bg_and_text_for_missing_keys(self, root):
        button = tk.Button(root)
        button._theme = {"bg": "surface"}

        apply_widget_colors(button, DARK_COLORS)

        assert button.cget("bg") == DARK_COLORS.SURFACE
        assert button.cget("fg") == DARK_COLORS.TEXT
        assert button.cget("activebackground") == DARK_COLORS.SURFACE
        assert button.cget("activeforeground") == DARK_COLORS.TEXT

    def test_button_without_theme_uses_surface_and_hover(self, root):
        button = tk.Button(root, bg="#ffffff")

        apply_widget_colors(button, DARK_COLORS)

        assert button.cget("bg") == DARK_COLORS.SURFACE
        assert button.cget("fg") == DARK_COLORS.TEXT
        assert button.cget("activebackground") == DARK_COLORS.HOVER

    def test_entry_sets_text_color_as_insert_background(self, root):
        entry = tk.Entry(root)

        apply_widget_colors(entry, DARK_COLORS)

        assert entry.cget("bg") == DARK_COLORS.SURFACE
        assert entry.cget("insertbackground") == DARK_COLORS.TEXT

    def test_checkbutton_selectcolor_matches_parent_background(self, root):
        parent = tk.Frame(root, bg="#222233")
        check = tk.Checkbutton(parent)

        apply_widget_colors(check, DARK_COLORS)

        assert check.cget("selectcolor") == parent.cget("bg")
        assert check.cget("bg") == parent.cget("bg")

    def test_canvas_uses_bg_key_when_present(self, root):
        canvas = tk.Canvas(root, bg="#ffffff")
        canvas._bg_key = "hover"

        apply_widget_colors(canvas, DARK_COLORS)

        assert canvas.cget("bg") == DARK_COLORS.HOVER

    def test_menu_uses_surface_and_text_colors(self, root):
        menu = tk.Menu(root)

        apply_widget_colors(menu, DARK_COLORS)

        assert str(menu.cget("bg")) == DARK_COLORS.SURFACE
        assert str(menu.cget("fg")) == DARK_COLORS.TEXT

    def test_label_falls_back_to_background_when_parent_has_no_bg(self, root):
        parent = ttk.Frame(root)
        label = tk.Label(parent, bg="#ffffff")

        apply_widget_colors(label, DARK_COLORS)

        assert label.cget("bg") == DARK_COLORS.BACKGROUND

    def test_checkbutton_falls_back_to_surface_when_parent_has_no_bg(self, root):
        parent = ttk.Frame(root)
        check = tk.Checkbutton(parent)

        apply_widget_colors(check, DARK_COLORS)

        assert check.cget("selectcolor") == DARK_COLORS.SURFACE

    def test_unconfigurable_widget_does_not_raise(self):
        class FrozenFrame:
            def winfo_class(self):
                return "Frame"

            def configure(self, **kwargs):
                raise tk.TclError("widget is frozen")

        apply_widget_colors(FrozenFrame(), DARK_COLORS)

    def test_widget_class_without_rule_is_left_untouched(self, root):
        toplevel = tk.Toplevel(root)
        toplevel.withdraw()
        toplevel.configure(bg="#abcdef")
        ttk_frame = ttk.Frame(root)

        apply_widget_colors(toplevel, DARK_COLORS)
        apply_widget_colors(ttk_frame, DARK_COLORS)

        assert toplevel.cget("bg") == "#abcdef"


class TestApplyThemeColors:
    def test_recurses_into_nested_children(self, root):
        outer = tk.Frame(root, bg="#ffffff")
        inner = tk.Frame(outer, bg="#eeeeee")
        inner._bg_key = "surface"
        label = tk.Label(inner, bg="#dddddd")
        button = tk.Button(inner, bg="#cccccc")

        apply_theme_colors(outer, DARK_COLORS)

        assert outer.cget("bg") == DARK_COLORS.BACKGROUND
        assert inner.cget("bg") == DARK_COLORS.SURFACE
        assert label.cget("bg") == DARK_COLORS.SURFACE
        assert label.cget("fg") == DARK_COLORS.TEXT
        assert button.cget("bg") == DARK_COLORS.SURFACE

    def test_destroyed_widget_is_ignored_without_raising(self, root):
        frame = tk.Frame(root)
        frame.destroy()

        apply_theme_colors(frame, DARK_COLORS)


class TestApplyTheme:
    def test_apply_theme_paints_ttk_and_tk(self, root):
        apply_theme(root, LIGHT_COLORS)
        btn = tk.Button(root)
        btn.pack()
        apply_theme(root, DARK_COLORS)
        assert btn.cget("bg").lower() == DARK_COLORS.SURFACE.lower()

    def test_treeview_styled_by_manager(self):
        mgr = StyleManager()
        mgr.configure(DARK_COLORS)
        assert mgr.style.lookup("Modern.Treeview", "background")
