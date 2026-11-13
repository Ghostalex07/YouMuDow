"""Tests for the UI protocol definitions."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.protocols import MainWindowProtocol


class TestMainWindowProtocol:
    def test_main_window_satisfies_protocol(self):
        from youmudow.ui.window import MainWindow

        instance = MainWindow.__new__(MainWindow)
        # The protocol members are read-only properties backed by private
        # attributes, so the backing stores are what this test populates.
        instance._tk_root = Mock()
        instance._controller_impl = Mock()
        instance._selected_video_impl = None
        instance._results_cards_impl = Mock()
        instance._search_bar_impl = Mock()
        instance._notebook_widget = Mock()
        instance._main_content_frame_impl = Mock()

        assert isinstance(instance, MainWindowProtocol)

    def test_protocol_members_are_declared(self):
        # Protocol members declared as attributes live in ``__annotations__``;
        # those declared as read-only properties live in the class namespace.
        names = set(MainWindowProtocol.__annotations__)
        names |= {name for name in MainWindowProtocol.__dict__ if not name.startswith("_abc")}
        assert {
            "_root",
            "_controller",
            "_selected_video",
            "_results_cards",
            "_search_bar",
            "_notebook",
            "_main_content_frame",
        } <= names
        assert {
            "_on_search",
            "_on_cancel_search",
            "_on_cancel_download",
            "_on_download_now",
            "_on_open_folder",
            "_set_status",
        } <= set(MainWindowProtocol.__dict__)

    def test_missing_attribute_does_not_satisfy_protocol(self):
        class Partial:
            pass

        assert not isinstance(Partial(), MainWindowProtocol)
