"""Tests for StateManager."""
import pytest
from youmudow.app.state import StateManager, AppState, AppMode, AppStateData
from youmudow.domain.models import Video
from youmudow.domain.enums import DownloadStatus


class TestStateManager:
    def test_initial_state(self):
        sm = StateManager()
        assert sm.state == AppState.IDLE
        assert sm.mode == AppMode.NORMAL
        assert not sm.is_downloading
        assert not sm.is_searching
        assert sm.error_message == ""

    def test_set_state(self):
        sm = StateManager()
        sm.set_state(AppState.SEARCHING)
        assert sm.state == AppState.SEARCHING
        assert sm.is_searching

    def test_set_mode(self):
        sm = StateManager()
        sm.set_mode(AppMode.DEBUG)
        assert sm.mode == AppMode.DEBUG

    def test_set_error(self):
        sm = StateManager()
        sm.set_error("test error")
        assert sm.state == AppState.ERROR
        assert sm.error_message == "test error"

    def test_clear_error(self):
        sm = StateManager()
        sm.set_error("test")
        sm.clear_error()
        assert sm.state == AppState.IDLE
        assert sm.error_message == ""

    def test_search_results(self):
        sm = StateManager()
        results = [Video(title="A", url="url1"), Video(title="B", url="url2")]
        sm.set_search_results(results)
        assert sm.get_search_results() == results

    def test_add_to_queue(self):
        sm = StateManager()
        v = Video(title="Test", url="url")
        sm.add_to_queue(v)
        assert v in sm.get_queue()
        assert v.status == DownloadStatus.QUEUED

    def test_remove_from_queue(self):
        sm = StateManager()
        v = Video(title="Test", url="url")
        sm.add_to_queue(v)
        sm.remove_from_queue(v)
        assert v not in sm.get_queue()

    def test_clear_queue(self):
        sm = StateManager()
        sm.add_to_queue(Video(title="A", url="a"))
        sm.add_to_queue(Video(title="B", url="b"))
        sm.clear_queue()
        assert sm.get_queue() == []

    def test_start_download(self):
        sm = StateManager()
        v = Video(title="Test", url="url")
        sm.add_to_queue(v)
        sm.start_download(v)
        assert v not in sm.get_queue()
        assert v in sm.get_active_downloads()
        assert v.status == DownloadStatus.DOWNLOADING
        assert sm.is_downloading

    def test_finish_download(self):
        sm = StateManager()
        v = Video(title="Test", url="url")
        sm.add_to_queue(v)
        sm.start_download(v)
        sm.finish_download(v)
        assert v not in sm.get_active_downloads()
        assert v in sm.get_completed_downloads()
        assert not sm.is_downloading

    def test_update_progress(self):
        sm = StateManager()
        v = Video(title="Test", url="url")
        sm.add_to_queue(v)
        sm.start_download(v)
        sm.update_progress(v, 50.0)
        assert v.progress == 50.0

    def test_cancel_download(self):
        sm = StateManager()
        v = Video(title="Test", url="url")
        sm.add_to_queue(v)
        sm.start_download(v)
        sm.cancel_download(v)
        assert v not in sm.get_active_downloads()
        assert v in sm.get_queue()

    def test_snapshot(self):
        sm = StateManager()
        v = Video(title="Test", url="url")
        sm.add_to_queue(v)
        snap = sm.get_snapshot()
        assert isinstance(snap, AppStateData)
        assert v in snap.queue

    def test_on_change_callback(self):
        sm = StateManager()
        calls = []
        sm.on_change(lambda s: calls.append(1))
        sm.set_state(AppState.SEARCHING)
        assert len(calls) == 1

    def test_reset(self):
        sm = StateManager()
        sm.add_to_queue(Video(title="A", url="a"))
        sm.set_state(AppState.SEARCHING)
        sm.reset()
        assert sm.state == AppState.IDLE
        assert sm.get_queue() == []


class TestAppStateData:
    def test_defaults(self):
        d = AppStateData(
            search_results=[], queue=[], active_downloads=[],
            completed_downloads=[], state=AppState.IDLE,
            mode=AppMode.NORMAL, error_message="",
        )
        assert d.state == AppState.IDLE
        assert d.mode == AppMode.NORMAL
