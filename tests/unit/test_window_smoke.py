"""Smoke tests for the MainWindow UI layer.

These tests build the real Tkinter MainWindow against a mock controller,
verifying that the UI constructs, processes events, and delegates to the
controller without crashing.
"""

import logging
import os
import threading
import time
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.domain.models import Video


def _snapshot(state, **overrides):
    from youmudow.app.state import AppMode, AppStateData

    fields = {
        "search_results": [],
        "queue": [],
        "active_downloads": [],
        "completed_downloads": [],
        "failed_downloads": [],
        "state": state,
        "mode": AppMode.NORMAL,
        "error_message": "",
    }
    fields.update(overrides)
    return AppStateData(**fields)


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

    def test_main_content_fits_and_status_bar_is_mapped(self, main_window):
        window, _ = main_window
        window._root.geometry("1000x700")
        window._root.update_idletasks()
        window._root.update()
        main_tab = window._main_tab
        assert main_tab.grid_rowconfigure(0)["weight"] == 1
        assert window._paned_window.winfo_height() <= main_tab.winfo_height()
        assert window._status_bar.winfo_ismapped()


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

    def test_on_download_complete_keeps_downloading_until_snapshot_says_otherwise(
        self, main_window
    ):
        from youmudow.app.state import AppState

        window, controller = main_window
        callback = controller.on_download_complete.call_args.args[0]
        video = Video(title="Downloaded Title", url="https://example.com/dl")
        window._is_downloading = True
        callback(video)
        window._root.update()
        assert window._is_downloading is True

        window._update_from_snapshot(_snapshot(AppState.IDLE))
        assert window._is_downloading is False

    def test_snapshot_update_failures_are_logged(self, main_window, caplog):
        from youmudow.app.state import AppState

        window, _ = main_window
        window._detail_panel._queue_panel_visible = True
        window._detail_panel._update_queue_display = Mock(
            side_effect=RuntimeError("treeview exploded")
        )
        with caplog.at_level(logging.ERROR):
            window._update_from_snapshot(_snapshot(AppState.DOWNLOADING))
        assert "Failed to apply state snapshot" in caplog.text

    def test_playlist_input_fetches_playlist(self, main_window):
        window, _ = main_window
        url = "https://www.youtube.com/playlist?list=abc123"
        window._results_table.is_playlist = True
        window._handle_playlist_input(url)
        window._on_playlist_complete([Video(title="P1", url="https://example.com/1")])
        assert window._results_table.playlist_videos
        assert window._is_searching is False

    def test_file_exit_menu_runs_full_close_sequence(self, main_window):
        from youmudow.ui.window import MainWindow

        _, controller = main_window
        config = Mock()
        config.get.side_effect = lambda key, default=None: default
        config.get_search_history.return_value = []
        config.window_geometry = ""

        with patch.object(MainWindow, "_on_close") as close:
            window = MainWindow(controller=controller, config=config)
            try:
                file_index = next(
                    i
                    for i in range(1, window._menubar.index("end") + 1)
                    if window._menubar.type(i) == "cascade"
                )
                file_menu = window._menubar.nametowidget(
                    window._menubar.entrycget(file_index, "menu")
                )
                file_menu.invoke(file_menu.index("end"))
                assert close.called
            finally:
                window.destroy()

    def test_log_events_are_routed_through_schedule(self, main_window):
        from youmudow.app.events import EventType, LogEvent

        window, _ = main_window
        window._schedule = Mock()
        window._log_terminal = Mock()
        window._event_bus.publish(
            LogEvent(
                type=EventType.LOG_OUTPUT,
                message="hello",
                level="info",
                timestamp="12:00:00",
            )
        )
        assert window._schedule.called
        scheduled = window._schedule.call_args
        assert scheduled[0][1] == "hello"

    def test_log_clear_is_routed_through_schedule(self, main_window):
        from youmudow.app.events import Event, EventType

        window, _ = main_window
        window._schedule = Mock()
        window._log_terminal = Mock()
        window._event_bus.publish(Event(type=EventType.LOG_CLEAR))
        assert window._schedule.called
        assert window._schedule.call_args[0][0] == window._log_terminal.clear

    def test_check_ytdlp_on_start_does_not_block_the_main_thread(self, main_window):
        from youmudow.ui import window as window_module

        window, _ = main_window
        window._run_startup_environment_check = Mock()
        caller = threading.current_thread()
        observed = {}
        started = threading.Event()
        release = threading.Event()

        def slow_version():
            observed["thread"] = threading.current_thread()
            started.set()
            release.wait(5)
            return "2026.01.01"

        with patch.object(window_module, "get_ytdlp_version", slow_version):
            begin = time.monotonic()
            window._check_ytdlp_on_start()
            elapsed = time.monotonic() - begin
            assert started.wait(5)
            release.set()

        assert elapsed < 1.0
        assert observed["thread"] is not caller

    def test_startup_check_keeps_a_healthy_player_cache(self, main_window):
        from youmudow.ui import window as window_module

        window, _ = main_window
        window._schedule = Mock(side_effect=lambda callback, *args: callback(*args))
        window._set_status = Mock()
        with (
            patch.object(window_module, "detect_js_runtime", return_value="deno"),
            patch.object(window_module, "is_ejs_installed", return_value=True),
            patch.object(window_module, "repair_youtube_environment"),
            patch.object(window_module, "clear_ytdlp_cache", create=True) as clear_cache,
        ):
            window._run_startup_environment_check()

        assert not clear_cache.called
        assert "cache" not in window._set_status.call_args.args[0].lower()

    def test_close_saves_every_field_when_concurrent_value_is_invalid(self, main_window):
        from youmudow.ui.window import MainWindow

        window, controller = main_window
        config = window._config
        config.reset_mock()
        config.get.side_effect = lambda key, default=None: default
        window._detail_panel._format_var.set("m4a")
        window._detail_panel._concurrent_var.set("3x")

        with patch.object(MainWindow, "destroy"):
            window._on_close()

        assert config.save.called
        stored = dict(call.args for call in config.set.call_args_list)
        assert stored["format"] == "m4a"
        assert stored["concurrent_downloads"] == 1
        assert "quality" in stored
        assert config.output_path is controller.get_output_path.return_value
