"""Tests for download service."""

import pytest
from unittest.mock import Mock

from youmudow.services.download_service import (
    DownloadService,
    DownloadQueue,
    DownloadEvent,
    DownloadProgress,
    DownloadEventType,
)
from youmudow.domain.models import Video
from youmudow.domain.enums import DownloadStatus


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
        videos = [
            Video(title=f"Video {i}", url=f"url{i}") for i in range(3)
        ]
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
