"""Tests for the SearchEntry component."""

import os
import tkinter as tk

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.ui.widgets.components.search_entry import SearchEntry


@pytest.fixture
def root():
    # Return-event delivery needs a mapped, focusable window, so this fixture
    # does not withdraw the root the way the other component tests do.
    root = tk.Tk()
    root.geometry("200x100+0+0")
    root.update()
    yield root
    root.destroy()


def test_placeholder_shown_when_empty(root):
    e = SearchEntry(root, placeholder="Search…")
    assert e.get() == ""


def test_return_fires_command(root):
    calls = []
    e = SearchEntry(root, command=lambda: calls.append(1))
    e.pack()
    root.update()
    # `event_generate("<Return>")` is unreliable under headless X (xvfb): it
    # depends on input focus and keysym delivery, which no WM grants there.
    # Invoke the bound handler directly instead — this is exactly what the
    # <Return> binding delegates to, and it is deterministic everywhere.
    assert e._entry.bind("<Return>")  # the Return binding is wired
    e._on_return(None)
    assert calls == [1]


def test_set_and_clear(root):
    e = SearchEntry(root)
    e.set("abc")
    assert e.get() == "abc"
    e.clear()
    assert e.get() == ""


class TestSearchEntryHistory:
    def test_history_dropdown_does_not_open_without_history(self, root):
        e = SearchEntry(root, history=[])
        e.open_history()
        assert not e.history_is_open()

    def test_history_dropdown_opens_with_history(self, root):
        e = SearchEntry(root, history=["url1", "url2"])
        e.open_history()
        assert e.history_is_open()

    def test_set_history_updates_dropdown_contents(self, root):
        e = SearchEntry(root, history=["url1"])
        e.open_history()
        e.set_history(["a", "b"])
        assert list(e._history_listbox.get(0, "end")) == ["a", "b"]

    def test_selecting_history_item_sets_field_and_fires_command(self, root):
        calls = []
        e = SearchEntry(root, command=lambda: calls.append(1), history=["url1"])
        e.open_history()
        e._history_listbox.selection_set(0)
        e._on_history_select(None)
        assert e.get() == "url1"
        assert calls == [1]

    def test_close_history_hides_dropdown(self, root):
        e = SearchEntry(root, history=["url1"])
        e.open_history()
        e.close_history()
        assert not e.history_is_open()

    def test_clear_closes_history(self, root):
        e = SearchEntry(root, history=["url1"])
        e.open_history()
        e.clear()
        assert not e.history_is_open()
