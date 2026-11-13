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
        # Attribute checks only: the protocol describes instance state that is
        # assigned in ``MainWindow.__init__``, which this test deliberately skips.
        instance._root = Mock()
        instance._controller = Mock()
        instance._selected_video = None
        instance._results_cards = Mock()
        instance._search_bar = Mock()
        instance._notebook = Mock()
        instance._main_content_frame = Mock()

        assert isinstance(instance, MainWindowProtocol)

    def test_protocol_members_are_declared(self):
        names = set(MainWindowProtocol.__annotations__)
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
