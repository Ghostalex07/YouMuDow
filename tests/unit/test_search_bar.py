"""Tests for the wired SearchBar."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.widgets.components.rounded_button import RoundedButton
from youmudow.ui.widgets.components.search_entry import SearchEntry
from youmudow.ui.widgets.search_bar import SearchBar


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def mw():
    m = Mock()
    m._root = tk.Tk()
    m._root.withdraw()
    m._controller = Mock()
    m._selected_video = None
    return m


class TestSearchBarWiring:
    def test_uses_search_entry(self, root, mw):
        bar = SearchBar(root, mw)
        assert isinstance(bar.search_entry, SearchEntry)

    def test_uses_rounded_buttons(self, root, mw):
        bar = SearchBar(root, mw)
        assert isinstance(bar._search_btn, RoundedButton)
        assert isinstance(bar._cancel_btn, RoundedButton)
        assert isinstance(bar._cancel_dl_btn, RoundedButton)

    def test_update_history_forwards_to_entry(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_history(["url1", "url2"])
        assert bar.search_entry._history == ["url1", "url2"]

    def test_get_query_is_empty_when_placeholder_shown(self, root, mw):
        bar = SearchBar(root, mw)
        assert bar.get_query() == ""

    def test_get_query_returns_typed_text(self, root, mw):
        bar = SearchBar(root, mw)
        bar.search_var.set("hello")
        assert bar.get_query() == "hello"

    def test_search_button_invokes_search(self, root, mw):
        mw._on_search = Mock()
        bar = SearchBar(root, mw)
        bar._search_btn.invoke()
        mw._on_search.assert_called_once()

    def test_cancel_button_disabled_while_not_searching(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_button_states(False, False)
        assert not bar._cancel_btn.is_enabled()

    def test_cancel_button_enabled_while_searching(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_button_states(True, False)
        assert bar._cancel_btn.is_enabled()

    def test_stop_button_enabled_while_downloading(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_button_states(False, True)
        assert bar._cancel_dl_btn.is_enabled()

    def test_paste_url_triggers_search_on_return(self, root, mw):
        mw._on_search = Mock()
        bar = SearchBar(root, mw)
        bar.search_var.set("https://youtu.be/abc12345678")
        bar.search_entry._on_return(None)
        mw._on_search.assert_called_once()

    def test_clear_closes_history_dropdown_and_empties_query(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_history(["url1", "url2"])
        bar.search_var.set("https://youtu.be/abc12345678")
        bar.search_entry.open_history()
        assert bar.search_entry.history_is_open()

        bar.search_entry.clear()

        assert not bar.search_entry.history_is_open()
        assert bar.get_query() == ""
