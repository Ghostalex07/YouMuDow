"""Tests for the RoundedButton canvas component."""

import os
import tkinter as tk

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.ui.styles.constants import _c
from youmudow.ui.widgets.components.rounded_button import RoundedButton


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_button_invokes_command(root):
    calls = []
    b = RoundedButton(root, "Go", command=lambda: calls.append(1))
    b.invoke()
    assert calls == [1]


def test_button_disable_blocks_command(root):
    calls = []
    b = RoundedButton(root, "Go", command=lambda: calls.append(1))
    b.set_enabled(False)
    b.invoke()
    assert calls == []


def test_button_set_text(root):
    b = RoundedButton(root, "A")
    b.set_text("B")
    assert b._label_text == "B"


def test_button_variant_fill(root):
    primary = RoundedButton(root, "x", variant="primary")
    secondary = RoundedButton(root, "x", variant="secondary")
    danger = RoundedButton(root, "x", variant="danger")
    ghost = RoundedButton(root, "x", variant="ghost")

    assert primary._fill_color == _c("primary")
    assert secondary._fill_color == _c("surface")
    assert danger._fill_color == _c("error")
    assert ghost._fill_color is None
