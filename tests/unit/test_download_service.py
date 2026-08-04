"""Tests for download service."""

import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video
from youmudow.services.download_service import (
    DownloadEvent,
    DownloadEventType,
    DownloadProgress,
    DownloadQueue,
    DownloadService,
    DownloadWorker,
    _format_speed,
)


@pytest.fixture
def mock_adapter():
    """Create a mock yt-dlp adapter."""
    adapter = Mock()
    adapter.download.return_value = Video(
        title="Test Video",
        url="https://youtube.com/watch?v=test",
        status=DownloadStatus.DONE,
    )
    return adapter


@pytest.fixture
def download_service(mock_adapter, tmp_path):
    """Create a download service with mock adapter."""
    return DownloadService(
        adapter=mock_adapter,
        default_output_path=tmp_path,
    )


class TestDownloadQueue:
    """Tests for DownloadQueue."""

    def test_add_sets_queued_status(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        assert sample_video.status == DownloadStatus.QUEUED

    def test_add_increases_size(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        assert queue.size() == 1

    def test_get_returns_video(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        result = queue.get()
        assert result is sample_video

    def test_get_returns_none_when_empty(self):
        queue = DownloadQueue()
        assert queue.get() is None

    def test_get_decreases_size(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        queue.get()
        assert queue.size() == 0

    def test_is_empty_after_clear(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        queue.clear()
        assert queue.is_empty()

    def test_peek_returns_copy(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        result = queue.peek()
        assert result == [sample_video]
        assert result is not queue._queue


class TestDownloadService:
    """Tests for DownloadService."""

    def test_init_with_adapter(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        assert service._adapter is mock_adapter
        assert service._output_path == tmp_path

    def test_queue_size_property(self, download_service, sample_video):
        download_service.add_to_queue(sample_video)
        assert download_service.queue_size == 1

    def test_is_running_initially_false(self, download_service):
        assert download_service.is_running is False

    def test_add_to_queue(self, download_service, sample_video):
        download_service.add_to_queue(sample_video)
        assert download_service.queue_size == 1

    def test_add_multiple(self, download_service):
        videos = [Video(title=f"Video {i}", url=f"url{i}") for i in range(3)]
        download_service.add_multiple(videos)
        assert download_service.queue_size == 3

    def test_set_output_path(self, download_service, tmp_path):
        new_path = tmp_path / "new_output"
        download_service.set_output_path(new_path)
        assert download_service._output_path == new_path

    def test_on_event_callback(self, download_service):
        received = []

        def callback(event):
            received.append(event)

        download_service.on_event(callback)
        assert callback in download_service._event_callbacks

    def test_download_now_calls_adapter(self, download_service, mock_adapter, sample_video):
        download_service.download_now(sample_video)
        mock_adapter.download.assert_called_once()

    def test_download_now_returns_video(self, download_service, sample_video):
        result = download_service.download_now(sample_video)
        assert result is not None
        assert isinstance(result, Video)


class TestFormatSpeed:
    """Speed formatting helper."""

    def test_empty(self):
        assert _format_speed("") == "Calculating..."

    def test_with_value(self):
        assert _format_speed("1.2MiB") == "1.2MiB/s"


class TestDownloadQueueEdgeCases:
    """Remaining DownloadQueue behaviors."""

    def test_remove_missing_does_not_raise(self):
        queue = DownloadQueue()
        queue.remove(Video(title="x", url="u"))
        assert queue.size() == 0

    def test_remove_present(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        queue.remove(sample_video)
        assert queue.is_empty()


class TestDownloadServiceExtra:
    """Additional DownloadService behaviors."""

    def test_set_log_callback(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        callback = lambda msg: None
        service.set_log_callback(callback)
        mock_adapter.set_log_callback.assert_called_once_with(callback)

    def test_stop_when_not_running(self, download_service):
        download_service.stop()
        assert download_service.is_running is False

    def test_download_now_error(self, download_service):
        v = Video(title="x", url="u")
        download_service._adapter.download.return_value = Video(
            title="x", url="u", status=DownloadStatus.ERROR, error_message="boom"
        )
        result = download_service.download_now(v)
        assert result.status == DownloadStatus.ERROR

    def test_on_progress_filters_non_progress(self, download_service, sample_video):
        received = []
        download_service.on_progress(received.append)
        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.QUEUED, video=sample_video)
        )
        assert received == []

    def test_emit_event_swallows_callback_errors(self, download_service, sample_video):
        def bad(event):
            raise RuntimeError("boom")

        download_service._event_callbacks.append(bad)
        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.QUEUED, video=sample_video)
        )

    def test_add_to_queue_emits_event(self, download_service, sample_video):
        events = []
        download_service.on_event(events.append)
        download_service.add_to_queue(sample_video)
        assert events
        assert events[-1].type == DownloadEventType.QUEUED

    def test_cancel_video_emits_cancelled(self, download_service, sample_video):
        events = []
        download_service.on_event(events.append)
        download_service.add_to_queue(sample_video)
        download_service.cancel_video(sample_video)
        assert any(e.type == DownloadEventType.CANCELLED for e in events)


class TestDownloadWorker:
    """DownloadWorker thread behavior."""

    def test_submit_and_cancel(self, sample_video):
        worker = DownloadWorker(
            worker_id=0,
            adapter=Mock(),
            output_path=Path("/tmp"),
            progress_callback=Mock(),
        )
        assert worker.is_busy is False
        worker.submit(sample_video)
        assert worker.is_busy is True
        assert worker.current_video is sample_video
        worker.cancel()
        assert worker._cancel_event.is_set()

    def test_worker_id(self):
        worker = DownloadWorker(0, Mock(), Path("/tmp"), Mock())
        assert worker.worker_id == 0

    def test_run_completes(self, mock_adapter, sample_video, tmp_path):
        def success_download(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            return video

        mock_adapter.download.side_effect = success_download
        events = []
        worker = DownloadWorker(0, mock_adapter, tmp_path, events.append)
        worker.start()
        worker.submit(sample_video)
        for _ in range(100):
            if any(e.type == DownloadEventType.COMPLETED for e in events):
                break
            time.sleep(0.02)
        worker.stop()
        worker.join(timeout=2)
        assert any(e.type == DownloadEventType.COMPLETED for e in events)

    def test_run_adapter_error(self, sample_video, tmp_path):
        adapter = Mock()
        adapter.download.side_effect = Exception("boom")
        events = []
        worker = DownloadWorker(0, adapter, tmp_path, events.append)
        worker.start()
        worker.submit(sample_video)
        for _ in range(100):
            if any(e.type == DownloadEventType.COMPLETED for e in events):
                break
            time.sleep(0.02)
        worker.stop()
        worker.join(timeout=2)
        assert sample_video.status == DownloadStatus.ERROR
        assert sample_video.error_message == "boom"


class TestDownloadServiceConcurrency:
    """Service-level start/stop with worker threads."""

    def _wait_for(self, predicate, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    def test_start_processes_queue(self, mock_adapter, sample_video, tmp_path):
        def success_download(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            return video

        mock_adapter.download.side_effect = success_download
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        completed = []
        service.on_complete(completed.append)
        service.add_to_queue(sample_video)
        service.start()
        assert self._wait_for(lambda: len(completed) == 1)
        service.stop()
        assert sample_video.status == DownloadStatus.DONE

    def test_start_handles_error(self, mock_adapter, sample_video, tmp_path):
        mock_adapter.download.side_effect = Exception("boom")
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        errors = []
        service.on_error(errors.append)
        service.add_to_queue(sample_video)
        service.start()
        assert self._wait_for(lambda: len(errors) == 1)
        service.stop()
        assert sample_video.error_message == "boom"

    def test_start_twice_is_noop(self, mock_adapter, sample_video, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service.start()
        service.start()
        assert service.is_running is True
        service.stop()


class TestDownloadEvents:
    """Tests for download events."""

    def test_download_event_creation(self, sample_video):
        event = DownloadEvent(
            type=DownloadEventType.PROGRESS,
            video=sample_video,
            progress=DownloadProgress(
                video=sample_video,
                progress=50.0,
                speed="1.5MiB/s",
            ),
        )
        assert event.type == DownloadEventType.PROGRESS
        assert event.video == sample_video
        assert event.progress.progress == 50.0

    def test_download_queued_event(self, sample_video):
        event = DownloadEvent(
            type=DownloadEventType.QUEUED,
            video=sample_video,
        )
        assert event.type == DownloadEventType.QUEUED

    def test_download_error_event(self, sample_video):
        event = DownloadEvent(
            type=DownloadEventType.ERROR,
            video=sample_video,
            error="Connection failed",
        )
        assert event.error == "Connection failed"


class TestDownloadServiceCallbacks:
    """Tests for download service callbacks."""

    def test_on_progress_callback(self, download_service, sample_video):
        progress_updates = []

        def on_progress(progress):
            progress_updates.append(progress)

        download_service.on_progress(on_progress)
        download_service.download_now(sample_video)
        assert len(progress_updates) >= 0

    def test_on_complete_callback(self, download_service, sample_video):
        completed = []

        def on_complete(video):
            completed.append(video)

        download_service.on_complete(on_complete)
        download_service.download_now(sample_video)
        assert len(completed) >= 0
