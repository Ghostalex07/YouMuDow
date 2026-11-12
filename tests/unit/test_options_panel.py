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
