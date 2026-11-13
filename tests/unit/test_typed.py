"""Tests for the typed Tkinter helpers."""

import tkinter as tk

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.typed import configure_widget, setattr_any


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


class TestConfigureWidget:
    def test_sets_options(self, root):
        frame = tk.Frame(root)
        configure_widget(frame, bg="#123456")
        assert frame.cget("bg") == "#123456"

    def test_swallows_tcl_error(self):
        class Frozen:
            def configure(self, **kwargs):
                raise tk.TclError("nope")

        configure_widget(Frozen(), bg="#123456")  # must not raise


class TestSetattrAny:
    def test_sets_attribute(self):
        obj = tk.Frame.__new__(tk.Frame)
        setattr_any(obj, "_bg_key", "surface")
        assert obj._bg_key == "surface"
