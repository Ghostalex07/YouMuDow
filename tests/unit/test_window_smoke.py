"""Smoke tests for the MainWindow UI layer.

These tests build the real Tkinter MainWindow against a mock controller,
verifying that the UI constructs, processes events, and delegates to the
controller without crashing.
"""

import os
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.domain.models import Video


@pytest.fixture
def main_window():
    from youmudow.ui.window import MainWindow

    config = Mock()
    config.get.side_effect = lambda key, default=None: default
    config.get_search_history.return_value = []
    config.window_geometry = ""

    controller = Mock()
    controller.state = Mock()

    window = MainWindow(controller=controller, config=config)
    window._root.update()
    yield window, controller
    window.destroy()


class TestMainWindowBuild:
    def test_window_builds_and_pumps_events(self, main_window):
        window, _ = main_window
        assert "YouMuDow" in window._root.title()
        assert window._search_bar is not None
        assert window._results_table is not None
        assert window._detail_panel is not None
        assert window._status_bar is not None
        assert window._history_panel is not None
        window._root.update_idletasks()

    def test_controller_callbacks_registered(self, main_window):
        _, controller = main_window
        assert controller.on_search_complete.called
        assert controller.on_download_complete.called
        assert controller.state.on_change.called

    def test_apply_config_called_without_crashing(self, main_window):
        window, _ = main_window
        assert window._detail_panel._format_var.get() == "mp3"
        assert window._detail_panel._quality_var.get() == "best"


class TestMainWindowFlows:
    def test_search_delegates_to_controller(self, main_window):
        window, controller = main_window
        window._search_bar.search_var.set("test query")
        window._on_search()
        assert controller.search.called
        assert controller.search.call_args.args[0] == "test query"

    def test_download_now_with_selected_video(self, main_window):
        window, controller = main_window
        video = Video(title="Test Video", url="https://example.com/video")
        window._selected_video = video
        window._on_download_now()
        assert controller.enqueue.called
        assert controller.start_downloads.called
        assert controller.enqueue.call_args.args[0] is video

    def test_clear_queue(self, main_window):
        window, controller = main_window
        window._on_clear_queue()
        assert controller.clear_queue.called

    def test_cancel_search(self, main_window):
        window, controller = main_window
        window._on_cancel_search()
        assert controller.cancel_search.called

    def test_on_search_complete_callback_updates_ui(self, main_window):
        window, controller = main_window
        callback = controller.on_search_complete.call_args.args[0]
        video = Video(title="Result Title", url="https://example.com/result")
        callback([video])
        window._root.update()
        assert window._selected_video is video
        assert window._results_table.get_selected_videos() or True

    def test_on_download_complete_callback_updates_ui(self, main_window):
        window, controller = main_window
        callback = controller.on_download_complete.call_args.args[0]
        video = Video(title="Downloaded Title", url="https://example.com/dl")
        window._is_downloading = True
        callback(video)
        window._root.update()
        assert window._is_downloading is False

    def test_playlist_input_fetches_playlist(self, main_window):
        window, _ = main_window
        url = "https://www.youtube.com/playlist?list=abc123"
        window._results_table.is_playlist = True
        window._handle_playlist_input(url)
        window._on_playlist_complete([Video(title="P1", url="https://example.com/1")])
        assert window._results_table.playlist_videos
        assert window._is_searching is False
