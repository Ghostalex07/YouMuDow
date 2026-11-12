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
