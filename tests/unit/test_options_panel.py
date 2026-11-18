"""Tests for the OptionsPanel data-driven form builder."""

import os
import tkinter as tk
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def browser_catalog():
    """Pin browser discovery so construction does not depend on the host."""
    with (
        patch(
            "youmudow.ui.widgets.options_panel.get_available_browsers",
            return_value=["chrome", "firefox"],
        ),
        patch(
            "youmudow.ui.widgets.options_panel.get_all_browser_profiles",
            return_value={},
        ),
    ):
        yield


def test_options_rows_built_from_specs(root):
    from youmudow.ui.widgets.options_panel import OptionsPanel

    main_window = Mock()
    panel = OptionsPanel(root, main_window)

    assert panel._rows_count >= 6
    # The rows are real widgets parented to the options frame.
    assert len(panel._rows) == panel._rows_count
    assert panel._options_frame.winfo_manager() == ""


@pytest.fixture
def preset_panel(root):
    from youmudow.ui.widgets.options_panel import OptionsPanel

    return OptionsPanel(root, Mock())


def test_applying_a_preset_updates_the_controls(preset_panel):
    preset_panel.apply_preset("Video 1080")
    assert preset_panel._format_var.get() == "mp4"
    assert preset_panel._quality_var.get() == "1080p"
    assert preset_panel._preset_var.get() == "Video 1080"


def test_applying_a_preset_keeps_cookie_settings(preset_panel):
    preset_panel._use_cookies_var.set(True)
    preset_panel.apply_preset("Archive FLAC")
    assert preset_panel._use_cookies_var.get() is True


def test_preset_row_offers_custom_first(preset_panel):
    assert preset_panel._preset_values[0] == "Custom"
    assert preset_panel._preset_values[1:] == ["Music 320", "Video 1080", "Archive FLAC"]


def test_a_manual_format_change_returns_to_custom(preset_panel):
    preset_panel.apply_preset("Music 320")
    preset_panel._on_manual_option_change()
    assert preset_panel._preset_var.get() == "Custom"


def test_unknown_preset_falls_back_to_custom(preset_panel):
    preset_panel.apply_preset("Video 1080")
    preset_panel.apply_preset("nope")
    assert preset_panel._preset_var.get() == "Custom"
    assert preset_panel._format_var.get() == "mp4"
