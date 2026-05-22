"""Tests for AppController."""
import pytest
from unittest.mock import Mock
from pathlib import Path

from youmudow.app.controller import AppController
from youmudow.app.state import AppState, AppMode
from youmudow.domain.models import Video


class TestAppController:
    @pytest.fixture
    def controller(self):
        svc = Mock()
        svc.search.return_value = []
        svc.get_metadata.return_value = None
        svc.get_playlist.return_value = []
        dl = Mock()
        dl.get_queue.return_value = []
        dl.queue_size = 0
        dl.is_running = False
        ts = Mock()
        ts.get_thumbnail_url.return_value = ""
        sm = Mock()
        sm.state = AppState.IDLE
        sm.mode = AppMode.NORMAL
        sm.get_search_results.return_value = []
        sm.get_queue.return_value = []
        sm.get_snapshot = Mock()
        c = AppController(
            search_service=svc,
            download_service=dl,
            thumbnail_service=ts,
            state_manager=sm,
        )
        c._search_complete_callback = Mock()
        c._download_complete_callback = Mock()
        return c

    def test_initial_state(self, controller):
        assert controller.state is not None

    def test_set_output_path(self, controller):
        p = Path("/tmp/test")
        controller.set_output_path(p)
        controller._download_service.set_output_path.assert_called_once_with(p)

    def test_get_output_path(self, controller):
        controller._download_service.get_output_path.return_value = Path("/tmp")
        assert controller.get_output_path() == Path("/tmp")

    def test_search_calls_service(self, controller):
        controller.search("test query")
        controller._search_service.search.assert_called_once()

    def test_search_empty_query_does_nothing(self, controller):
        controller.search("")
        controller._search_service.search.assert_not_called()

    def test_search_url_calls_get_metadata(self, controller):
        url = "https://youtube.com/watch?v=test"
        controller.search_url(url)
        import time
        time.sleep(0.1)
        controller._search_service.get_metadata.assert_called()

    def test_enqueue(self, controller):
        v = Video(title="Test", url="url")
        controller.enqueue(v)
        controller._state_manager.add_to_queue.assert_called_once_with(v)

    def test_enqueue_multiple(self, controller):
        v1 = Video(title="A", url="a")
        v2 = Video(title="B", url="b")
        controller.enqueue_multiple([v1, v2])
        assert controller._state_manager.add_to_queue.call_count == 2

    def test_start_downloads(self, controller):
        v = Video(title="Test", url="url")
        controller._state_manager.get_queue.return_value = [v]
        controller.start_downloads()
        controller._download_service.add_multiple.assert_called_once_with([v])
        controller._download_service.start.assert_called_once()

    def test_stop_downloads(self, controller):
        controller.stop_downloads()
        controller._download_service.stop.assert_called_once()

    def test_clear_queue(self, controller):
        controller.clear_queue()
        controller._state_manager.clear_queue.assert_called_once()

    def test_remove_from_queue(self, controller):
        v = Video(title="Test", url="url")
        controller.remove_from_queue(v)
        controller._state_manager.remove_from_queue.assert_called_once_with(v)

    def test_set_debug_mode(self, controller):
        controller.set_debug_mode(True)
        assert controller._debug_mode is True

    def test_cancel_search(self, controller):
        controller.cancel_search()
        controller._state_manager.set_state.assert_called_with(AppState.IDLE)

    def test_search_playlist(self, controller):
        controller._search_service.get_playlist.return_value = [
            Video(title="A", url="a"),
        ]
        result = controller.search_playlist("https://youtube.com/playlist?list=test")
        assert len(result) == 1
