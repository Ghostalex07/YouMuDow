"""Tests for the history panel widget."""

import tkinter as tk
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.domain.models import HistoryEntry
from youmudow.ui.widgets.history_panel import HistoryPanel


@pytest.fixture
def root():
    try:
        root = tk.Tk()
    except tk.TclError:  # pragma: no cover - headless without X
        pytest.skip("no display")
    root.withdraw()
    yield root
    root.destroy()


def _entry(title="Song", uploader="Artist", **kw):
    return HistoryEntry(
        title=title,
        url=kw.pop("url", f"https://x.test/{title}"),
        uploader=uploader,
        file_format=kw.pop("file_format", "mp3"),
        output_path=kw.pop("output_path", "/tmp/song.mp3"),
        downloaded_at=kw.pop("downloaded_at", "2026-11-18T10:00:00"),
        **kw,
    )


def _panel(root, entries=None):
    controller = Mock()
    controller.history.get_all.return_value = entries or []
    mw = Mock()
    mw._controller = controller
    mw._root = root
    mw._search_bar = None
    mw._notebook = Mock()
    return HistoryPanel(root, mw), controller


def test_empty_history_shows_the_empty_state(root):
    panel, _ = _panel(root)
    panel.refresh()
    assert panel._empty_state is not None
    assert not panel._tree.winfo_ismapped()


def test_entries_are_listed_and_filtered(root):
    panel, _ = _panel(root, [_entry("Alpha"), _entry("Beta", uploader="Other")])
    panel.refresh()
    assert len(panel._tree.get_children()) == 2

    panel._search_var.set("bet")
    panel._on_filter_change()
    assert panel._filtered == panel._all_entries[1:]
    assert len(panel._tree.get_children()) == 1


def test_filter_matches_the_uploader(root):
    panel, _ = _panel(root, [_entry("Alpha", uploader="Zeta")])
    panel.refresh()
    panel._search_var.set("zeta")
    panel._on_filter_change()
    assert len(panel._filtered) == 1


def test_selected_entry_round_trips(root):
    entries = [_entry("Alpha"), _entry("Beta")]
    panel, _ = _panel(root, entries)
    panel.refresh()
    first = panel._tree.get_children()[0]
    panel._tree.selection_set(first)
    assert panel._get_selected_entry() is entries[0]


def test_selection_without_rows_returns_none(root):
    panel, _ = _panel(root)
    panel.refresh()
    assert panel._get_selected_entry() is None


def test_remove_deletes_the_selected_entry(root):
    entries = [_entry("Alpha")]
    panel, controller = _panel(root, entries)
    panel.refresh()
    panel._tree.selection_set(panel._tree.get_children()[0])
    panel._on_remove()
    controller.history.remove.assert_called_once_with(entries[0])


def test_redownload_reuses_the_search_bar(root):
    entries = [_entry("Alpha")]
    panel, _ = _panel(root, entries)
    panel.refresh()
    panel._tree.selection_set(panel._tree.get_children()[0])
    search_bar = Mock()
    panel._mw._search_bar = search_bar

    panel._on_redownload()

    search_bar.search_var.set.assert_called_once_with(entries[0].url)
    panel._mw._on_search.assert_called_once()
    panel._mw._notebook.select.assert_called_once_with(0)


def test_clear_history_asks_before_deleting(root, monkeypatch):
    panel, controller = _panel(root, [_entry("Alpha")])
    monkeypatch.setattr("youmudow.ui.widgets.history_panel.messagebox.askyesno", lambda *a: False)
    panel._on_clear_history()
    controller.history.clear.assert_not_called()

    monkeypatch.setattr("youmudow.ui.widgets.history_panel.messagebox.askyesno", lambda *a: True)
    panel._on_clear_history()
    controller.history.clear.assert_called_once()


def test_right_click_without_a_row_opens_no_menu(root, monkeypatch):
    panel, _ = _panel(root, [_entry("Alpha")])
    panel.refresh()
    monkeypatch.setattr(panel._tree, "identify_row", lambda y: "")
    panel._on_right_click(Mock(y=5, x_root=0, y_root=0))
    assert panel._tree.selection() == ()


def test_redownload_without_a_selection_does_nothing(root):
    panel, _ = _panel(root)
    panel.refresh()
    panel._on_redownload()
    panel._mw._on_search.assert_not_called()


def test_right_click_builds_the_context_menu(root, monkeypatch):
    entries = [_entry("Alpha")]
    panel, _ = _panel(root, entries)
    panel.refresh()
    monkeypatch.setattr(tk.Menu, "tk_popup", lambda self, x, y: None)
    item = panel._tree.get_children()[0]
    monkeypatch.setattr(panel._tree, "identify_row", lambda y: item)

    panel._on_right_click(Mock(y=5, x_root=0, y_root=0))

    assert panel._tree.selection() == (item,)
