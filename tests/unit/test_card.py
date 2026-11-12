"""Tests for the Card container component."""

import os
import tkinter as tk

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.ui.styles.constants import SPACING, _c
from youmudow.ui.widgets.components.card import Card


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_card_background_is_surface(root):
    c = Card(root)
    assert c.cget("background").lower() == _c("surface").lower()


def test_card_padding_default(root):
    c = Card(root)
    assert c.cget("padx") == SPACING["md"]
    assert c.cget("pady") == SPACING["md"]


def test_card_has_border(root):
    c = Card(root)
    assert c.cget("highlightthickness") == 1
    assert c.cget("highlightbackground").lower() == _c("border").lower()
