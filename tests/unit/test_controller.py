"""Tests for AppController."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from youmudow.app.controller import AppController
from youmudow.app.state import AppMode, AppState
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


class TestControllerSearchFlows:
    """Async search and metadata flow tests."""

    @pytest.fixture
    def controller(self):
        svc = Mock()
        svc.search.return_value = []
        svc.get_metadata.return_value = None
        svc.get_playlist.return_value = []
        dl = Mock()
        ts = Mock()
        sm = Mock()
        hist = Mock()
        c = AppController(
            search_service=svc,
            download_service=dl,
            thumbnail_service=ts,
            state_manager=sm,
            history_service=hist,
        )
        c._search_complete_callback = Mock()
        c._download_complete_callback = Mock()
        return c

    def test_perform_search_enriches_thumbnail(self, controller):
        v = Video(title="T", url="https://youtube.com/watch?v=abc", thumbnail="")
        controller._search_service.search.return_value = [v]
        controller._thumbnail_service.get_thumbnail_url.return_value = "thumb"
        controller._perform_search("query")
        assert v.thumbnail == "thumb"
        controller._state_manager.set_search_results.assert_called_once_with([v])
        controller._state_manager.set_state.assert_called_with(AppState.IDLE)
        controller._search_complete_callback.assert_called_once_with([v])

    def test_perform_search_keeps_existing_thumbnail(self, controller):
        v = Video(title="T", url="https://youtube.com/watch?v=abc", thumbnail="existing")
        controller._search_service.search.return_value = [v]
        controller._perform_search("query")
        controller._thumbnail_service.get_thumbnail_url.assert_not_called()

    def test_perform_search_non_youtube_no_thumbnail(self, controller):
        v = Video(title="T", url="https://soundcloud.com/track/x", thumbnail="")
        controller._search_service.search.return_value = [v]
        controller._perform_search("query")
        controller._thumbnail_service.get_thumbnail_url.assert_not_called()
        controller._search_complete_callback.assert_called_once_with([v])

    def test_perform_search_error(self, controller):
        controller._search_service.search.side_effect = Exception("boom")
        controller._perform_search("query")
        controller._state_manager.set_error.assert_called_once()

    def test_perform_search_url_success(self, controller):
        v = Video(title="T", url="https://youtube.com/watch?v=abc")
        controller._search_service.get_metadata.return_value = v
        controller._thumbnail_service.get_thumbnail_url.return_value = "th"
        controller._perform_search_url("https://youtube.com/watch?v=abc&x=1", 0)
        controller._search_complete_callback.assert_called_once_with([v])
        controller._state_manager.set_state.assert_called_with(AppState.IDLE)

    def test_perform_search_url_stale_epoch(self, controller):
        controller._search_epoch = 5
        controller._perform_search_url("https://youtube.com/watch?v=abc", 3)
        controller._search_service.get_metadata.assert_not_called()

    def test_perform_search_url_error(self, controller):
        controller._search_service.get_metadata.side_effect = Exception("boom")
        controller._perform_search_url("https://youtube.com/watch?v=abc", 0)
        controller._state_manager.set_error.assert_called_once()
        controller._state_manager.set_state.assert_called_with(AppState.IDLE)

    def test_search_playlist_empty_url(self, controller):
        assert controller.search_playlist("") == []

    def test_search_playlist_enriches_thumbnail(self, controller):
        v = Video(title="T", url="https://youtube.com/watch?v=abc", thumbnail="")
        controller._search_service.get_playlist.return_value = [v]
        controller._thumbnail_service.get_thumbnail_url.return_value = "th"
        result = controller.search_playlist("https://youtube.com/playlist?list=x")
        assert result == [v]
        assert v.thumbnail == "th"

    def test_search_playlist_error(self, controller):
        controller._search_service.get_playlist.side_effect = Exception("boom")
        assert controller.search_playlist("https://youtube.com/playlist?list=x") == []
        controller._state_manager.set_error.assert_called_once()

    def test_start_downloads_empty_queue(self, controller):
        controller._state_manager.get_queue.return_value = []
        controller.start_downloads()
        controller._download_service.add_multiple.assert_not_called()

    def test_remove_from_queue_cancels(self, controller):
        v = Video(title="T", url="u")
        controller.remove_from_queue(v)
        controller._download_service.cancel_video.assert_called_once_with(v)

    def test_stop_downloads_sets_idle(self, controller):
        controller.stop_downloads()
        controller._state_manager.set_state.assert_called_with(AppState.IDLE)

    def test_download_now(self, controller):
        v = Video(title="T", url="u")
        controller._download_service.download_now.return_value = v
        result = controller.download_now(v)
        assert result is v
        controller._state_manager.start_download.assert_called_once_with(v)

    def test_cancel_download(self, controller):
        v = Video(title="T", url="u")
        controller.cancel_download(v)
        controller._state_manager.cancel_download.assert_called_once_with(v)

    def test_set_debug_mode_false(self, controller):
        controller.set_debug_mode(False)
        controller._state_manager.set_mode.assert_called_with(AppMode.NORMAL)

    def test_resolve_history_path_existing(self, controller, tmp_path):
        f = tmp_path / "song.mp3"
        f.write_text("x")
        v = Video(title="Song", url="u", path=f)
        assert controller._resolve_history_path(v, "mp3") == f

    def test_resolve_history_path_output_dir(self, controller, tmp_path):
        controller._download_service.get_output_path.return_value = tmp_path
        v = Video(title="Song", url="u")
        assert controller._resolve_history_path(v, "mp3") == tmp_path / "Song.mp3"

    def test_reset(self, controller):
        from youmudow.services.download_service import DownloadService

        controller.reset()
        assert controller._search_thread is None
        assert isinstance(controller._download_service, DownloadService)
        controller._state_manager.reset.assert_called_once()


class TestControllerCallbacks:
    """Download and log callbacks registered by the controller."""

    @pytest.fixture
    def controller(self):
        svc = Mock()
        dl = Mock()
        ts = Mock()
        sm = Mock()
        hist = Mock()
        c = AppController(
            search_service=svc,
            download_service=dl,
            thumbnail_service=ts,
            state_manager=sm,
            history_service=hist,
        )
        c._download_complete_callback = Mock()
        return c

    def _callback(self, controller, method):
        return getattr(controller._download_service, method).call_args[0][0]

    def test_on_complete(self, controller):
        from youmudow.domain.enums import DownloadStatus
        from youmudow.domain.models import DownloadOptions

        v = Video(
            title="Song",
            url="u",
            status=DownloadStatus.DONE,
            options=DownloadOptions(file_format="mp3"),
        )
        cb = self._callback(controller, "on_complete")
        with (
            patch("youmudow.services.notification_service.notify") as notify,
            patch.object(controller, "_resolve_history_path", return_value=Path("/out/song.mp3")),
        ):
            cb(v)
        controller._state_manager.finish_download.assert_called_once_with(v)
        notify.assert_called_once()
        controller._history.add.assert_called_once()
        controller._download_complete_callback.assert_called_once_with(v)

    def test_on_error(self, controller):
        from youmudow.domain.enums import DownloadStatus

        v = Video(title="Song", url="u", status=DownloadStatus.ERROR, error_message="boom")
        cb = self._callback(controller, "on_error")
        cb(v)
        controller._state_manager.finish_download.assert_called_once_with(v)
        controller._download_complete_callback.assert_called_once_with(v)

    def test_on_progress(self, controller):
        from youmudow.services.download_service import DownloadProgress

        v = Video(title="Song", url="u")
        progress = DownloadProgress(video=v, progress=42.0, speed="1MiB/s", eta="00:10")
        cb = self._callback(controller, "on_progress")
        cb(progress)
        controller._state_manager.update_progress.assert_called_once()

    def test_on_progress_no_video(self, controller):
        from youmudow.services.download_service import DownloadProgress

        cb = self._callback(controller, "on_progress")
        cb(DownloadProgress(progress=10.0))
        controller._state_manager.update_progress.assert_not_called()

    def test_on_progress_debug_log(self, controller):
        from youmudow.services.download_service import DownloadProgress

        controller.set_debug_mode(True)
        v = Video(title="Song", url="u")
        cb = self._callback(controller, "on_progress")
        with patch("youmudow.app.controller.emit_log") as emit:
            cb(DownloadProgress(video=v, progress=50.0, speed="", eta=""))
        emit.assert_called()

    def test_on_started_event(self, controller):
        from youmudow.services.download_service import DownloadEvent, DownloadEventType

        v = Video(title="Song", url="u")
        cb = self._callback(controller, "on_event")
        cb(DownloadEvent(type=DownloadEventType.STARTED, video=v))

    def test_log_callback_levels(self, controller):
        cb = controller._search_service.set_log_callback.call_args[0][0]
        with patch("youmudow.app.controller.emit_log") as emit:
            cb("[ERROR] something")
            cb("[WARNING] x")
            cb("[DONE] y")
            cb("[download] z")
            cb("plain")
        levels = [call.args[1] for call in emit.call_args_list]
        assert levels == ["error", "warning", "success", "info", "info"]
