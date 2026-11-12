"""Tests for loading, empty and error states across list widgets."""

import os
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)


@pytest.fixture
def root():
    import tkinter as tk

    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_results_cards_empty_state(root):
    from youmudow.ui.widgets.results_cards import ResultsCards

    w = ResultsCards(root, Mock(), Mock())
    w.clear_results()
    root.update_idletasks()
    assert w._empty_state is not None
    assert w._empty_state.winfo_manager() != ""


def test_history_panel_empty_state(root):
    from youmudow.ui.widgets.history_panel import HistoryPanel

    mw = Mock()
    mw._root = root
    panel = HistoryPanel(root, mw)
    panel._populate([])
    root.update_idletasks()
    assert panel._empty_state is not None
    assert panel._empty_state.winfo_manager() != ""


def test_queue_panel_empty_state(root):
    from youmudow.ui.widgets.queue_panel import QueuePanel

    mw = Mock()
    mw._root = root
    snapshot = Mock()
    snapshot.queue = []
    snapshot.active_downloads = []
    snapshot.completed_downloads = []
    snapshot.failed_downloads = []
    panel = QueuePanel(root, mw)
    panel.update_display(snapshot)
    root.update_idletasks()
    assert panel._empty_state is not None
    assert panel._empty_state.winfo_manager() != ""


def test_spinner_runs_while_searching(root):
    from youmudow.ui.widgets.search_bar import SearchBar

    mw = Mock()
    mw._root = root
    bar = SearchBar(root, mw)
    bar.update_button_states(is_searching=True, is_downloading=False)
    assert bar._spinner.is_running()
