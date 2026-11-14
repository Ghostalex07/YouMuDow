"""Tests for the typed Tkinter helpers."""

import tkinter as tk

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.typed import configure_widget, readonly_property, setattr_any


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

    def test_accepts_non_string_values(self, root):
        entry = tk.Entry(root)
        configure_widget(entry, state="disabled")
        assert entry.cget("state") == "disabled"

    def test_accepts_a_mapping(self, root):
        entry = tk.Entry(root)
        configure_widget(entry, {"state": "disabled", "width": 12})
        assert entry.cget("state") == "disabled"
        assert int(entry.cget("width")) == 12


class TestSetattrAny:
    def test_sets_attribute(self):
        obj = tk.Frame.__new__(tk.Frame)
        setattr_any(obj, "_bg_key", "surface")
        assert obj._bg_key == "surface"


class TestReadonlyProperty:
    def test_reads_the_backing_attribute(self):
        class Widget:
            key = readonly_property("_real_key")

            def __init__(self):
                self._real_key = "surface"

        assert Widget().key == "surface"

    def test_rejects_assignment(self):
        class Widget:
            key = readonly_property("_real_key")

            def __init__(self):
                self._real_key = "surface"

        with pytest.raises(AttributeError):
            Widget().key = "other"
