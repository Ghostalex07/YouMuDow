"""Tests for the Spinner canvas component."""

import os
import tkinter as tk

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.ui.styles.constants import _c
from youmudow.ui.widgets.components.spinner import Spinner


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_spinner_starts_stopped(root):
    s = Spinner(root)
    assert s.is_running() is False


def test_spinner_start_stop(root):
    s = Spinner(root)
    s.start()
    assert s.is_running() is True
    s.stop()
    assert s.is_running() is False


def test_spinner_start_is_idempotent(root):
    s = Spinner(root)
    s.start()
    s.start()
    s.stop()
    assert s.is_running() is False


def test_spinner_default_color_is_primary(root):
    s = Spinner(root)
    assert s._resolve_color() == _c("primary")


def test_spinner_explicit_color_key(root):
    s = Spinner(root, color="error")
    assert s._resolve_color() == _c("error")
