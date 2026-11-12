"""Tests for the EmptyState component."""

import os
import tkinter as tk

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.ui.styles.constants import _c
from youmudow.ui.widgets.components.empty_state import EmptyState


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_empty_state_message_and_action(root):
    calls = []
    e = EmptyState(
        root, message="No results", action_text="Retry", action_command=lambda: calls.append(1)
    )
    assert e._action_button is not None
    e._action_button.invoke()
    assert calls == [1]


def test_empty_state_message_label(root):
    e = EmptyState(root, message="Nothing here")
    assert e._message_label.cget("text") == "Nothing here"
    assert e._message_label.cget("foreground").lower() == _c("text_secondary").lower()


def test_empty_state_no_action_without_action_text(root):
    e = EmptyState(root, message="Empty")
    assert e._action_button is None
