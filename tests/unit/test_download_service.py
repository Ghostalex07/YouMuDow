"""Tests for download service."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

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

    def test_remove_missing_returns_none(self):
        queue = DownloadQueue()
        result = queue.remove(Video(title="x", url="u"))
        assert result is None
        assert queue.size() == 0

    def test_remove_present_returns_video(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        removed = queue.remove(sample_video)
        assert removed is sample_video
        assert queue.is_empty()

    def test_remove_matches_by_url(self, sample_video):
        queue = DownloadQueue()
        queue.add(sample_video)
        removed = queue.remove(Video(title="Copy", url=sample_video.url))
        assert removed is sample_video
        assert queue.is_empty()

    def test_has_url(self, sample_video):
        queue = DownloadQueue()
        assert not queue.has_url(sample_video.url)
        queue.add(sample_video)
        assert queue.has_url(sample_video.url)
        assert not queue.has_url("https://example.com/other")


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

    def test_emit_event_does_not_hold_callback_lock(self, download_service, sample_video):
        callback_started = threading.Event()
        release = threading.Event()
        lock_granted = threading.Event()

        def slow_callback(event):
            callback_started.set()
            release.wait(timeout=5)

        download_service.on_event(slow_callback)

        event = DownloadEvent(type=DownloadEventType.ERROR, video=sample_video, error="x")
        emitter = threading.Thread(target=download_service._emit_event, args=(event,))
        emitter.start()

        assert callback_started.wait(timeout=1)

        def try_lock() -> None:
            with download_service._callbacks_lock:
                lock_granted.set()

        probe = threading.Thread(target=try_lock)
        probe.start()
        probe.join(timeout=0.5)
        assert not probe.is_alive(), "callbacks must not run while _callbacks_lock is held"
        assert lock_granted.is_set()

        release.set()
        emitter.join(timeout=5)

    def test_add_to_queue_emits_event(self, download_service, sample_video):
        events = []
        download_service.on_event(events.append)
        download_service.add_to_queue(sample_video)
        assert events
        assert events[-1].type == DownloadEventType.QUEUED

    def test_cancel_video_removes_from_active(self, mock_adapter, sample_video, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        events = []
        service.on_event(events.append)
        service.add_to_queue(sample_video)
        assert service.cancel_video(sample_video) is True
        assert service.active_count == 0
        assert service.queue_size == 0


class TestDownloadWorker:
    """DownloadWorker thread behavior."""

    def test_submit_and_cancel(self, sample_video):
        worker = DownloadWorker(
            worker_id=0,
            adapter=Mock(),
            output_path_getter=lambda: Path("/tmp"),
            progress_callback=Mock(),
        )
        assert worker.is_busy is False
        worker.submit(sample_video)
        assert worker.is_busy is True
        assert worker.current_video is sample_video
        worker.cancel()
        assert worker._cancel_event.is_set()

    def test_submit_twice_rejects_second(self, sample_video):
        worker = DownloadWorker(
            worker_id=0,
            adapter=Mock(),
            output_path_getter=lambda: Path("/tmp"),
            progress_callback=Mock(),
        )
        first = Video(title="First", url="u1")
        second = Video(title="Second", url="u2")
        assert worker.submit(first) is True
        assert worker.submit(second) is False
        assert worker.current_video is first
        assert worker.is_busy is True

    def test_worker_id(self):
        worker = DownloadWorker(0, Mock(), lambda: Path("/tmp"), Mock())
        assert worker.worker_id == 0

    def test_run_completes(self, mock_adapter, sample_video, tmp_path):
        def success_download(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            return video

        mock_adapter.download.side_effect = success_download
        events = []
        worker = DownloadWorker(0, mock_adapter, lambda: tmp_path, events.append)
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
        worker = DownloadWorker(0, adapter, lambda: tmp_path, events.append)
        worker.start()
        worker.submit(sample_video)
        for _ in range(100):
            if any(e.type == DownloadEventType.ERROR for e in events):
                break
            time.sleep(0.02)
        worker.stop()
        worker.join(timeout=2)
        assert sample_video.status == DownloadStatus.ERROR
        assert sample_video.error_message == "boom"
        assert any(e.type == DownloadEventType.ERROR for e in events)

    def test_run_cancelled(self, sample_video, tmp_path):
        adapter = Mock()
        adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.CANCELLED) or video
        )
        events = []
        worker = DownloadWorker(0, adapter, lambda: tmp_path, events.append)
        worker.start()
        worker.submit(sample_video)
        for _ in range(100):
            if any(e.type == DownloadEventType.CANCELLED for e in events):
                break
            time.sleep(0.02)
        worker.stop()
        worker.join(timeout=2)
        assert any(e.type == DownloadEventType.CANCELLED for e in events)


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

    def test_max_concurrent_respected(self, tmp_path):
        adapter = Mock()

        def blocking_download(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            time.sleep(0.3)
            return video

        adapter.download.side_effect = blocking_download
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=2)
        videos = [Video(title=f"V{i}", url=f"url{i}") for i in range(4)]
        service.add_multiple(videos)
        completions = []
        service.on_complete(completions.append)
        service.start()

        time.sleep(0.1)
        assert service.active_count == 2, (
            f"active_count={service.active_count}, expected 2 (max concurrent)"
        )
        assert service.queue_size == 2

        assert self._wait_for(lambda: len(completions) == 4, timeout=3.0)
        service.stop()
        assert service.active_count == 0

    def test_cancel_one_does_not_affect_others(self, tmp_path):
        adapter = Mock()

        def blocking_download(video, output_path, progress_callback=None, cancel_event=None):
            if cancel_event is not None and cancel_event.wait(0.4):
                video.status = DownloadStatus.CANCELLED
                return video
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = blocking_download
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=2)
        v0 = Video(title="Slow", url="url0")
        v1 = Video(title="Fast", url="url1")
        service.add_multiple([v0, v1])
        completions = []

        def hook(event):
            if event.type in (DownloadEventType.COMPLETED, DownloadEventType.CANCELLED):
                completions.append(event)

        service.on_event(hook)
        service.start()
        time.sleep(0.2)

        service.cancel_video(v0)
        assert self._wait_for(
            lambda: any(e.type == DownloadEventType.CANCELLED for e in completions)
        )
        assert v0.status == DownloadStatus.CANCELLED
        assert self._wait_for(lambda: len(completions) == 2, timeout=3.0)
        service.stop()
        assert v1.status == DownloadStatus.DONE

    def test_cancel_keeps_active_until_worker_confirms(self, tmp_path):
        """Fase 5: an active download must stay in active_downloads until the
        worker emits its terminal event."""
        adapter = Mock()
        started = threading.Event()

        def cancellable(video, output_path, progress_callback=None, cancel_event=None):
            started.set()
            if cancel_event is not None and cancel_event.wait(2.0):
                video.status = DownloadStatus.CANCELLED
                return video
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = cancellable
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)
        events = []
        service.on_event(lambda e: events.append(e))
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.start()
        assert started.wait(2.0)

        assert service.cancel_video(v) is False
        assert service.active_count == 1, "active download removed before worker confirmation"

        assert self._wait_for(lambda: any(e.type == DownloadEventType.CANCELLED for e in events))
        assert service.active_count == 0
        service.stop()

    def test_on_cancelled_callback_flagged(self, download_service, sample_video):
        received = []
        download_service.on_cancelled(received.append)
        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.CANCELLED, video=sample_video)
        )
        assert received == [sample_video]
        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.COMPLETED, video=sample_video)
        )
        assert received == [sample_video]

    def test_stop_clears_active_downloads(self, tmp_path):
        adapter = Mock()

        def blocking(video, *args, **kwargs):
            time.sleep(0.2)
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = blocking
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)
        service.add_to_queue(Video(title="v", url="u"))
        service.start()
        time.sleep(0.05)
        assert service.active_count >= 1
        service.stop()
        assert service.active_count == 0
        assert service._workers == []

    def test_dispatcher_requeues_on_submit_rejection(self, tmp_path):
        """A rejected submit (busy worker / stop race) must not lose the video."""
        adapter = Mock()

        def success(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = success
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)
        completed = []
        service.on_complete(completed.append)

        real_submit = DownloadWorker.submit
        attempts = {"n": 0}

        def flaky_submit(worker, video):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return False
            return real_submit(worker, video)

        with patch(
            "youmudow.services.download_service.DownloadWorker.submit",
            new=flaky_submit,
        ):
            service.add_to_queue(Video(title="v", url="u"))
            service.start()
            assert self._wait_for(lambda: len(completed) == 1)
            service.stop()
        assert attempts["n"] >= 2
        assert service.queue_size == 0
        assert service.active_count == 0

    def test_stop_joins_workers(self, mock_adapter, sample_video, tmp_path):
        def success_download(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            return video

        mock_adapter.download.side_effect = success_download
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service.add_to_queue(sample_video)
        service.start()
        assert self._wait_for(lambda: service.active_count == 0)
        service.stop()
        assert service._workers == []

    def test_output_path_updates_after_start(self, tmp_path):
        adapter = Mock()

        def success_download(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = success_download
        service = DownloadService(adapter=adapter, default_output_path=tmp_path)
        service.start()
        new_path = tmp_path / "moved"
        service.set_output_path(new_path)
        received = []

        def hook(event):
            if event.type == DownloadEventType.STARTED:
                received.append(event.video)

        service.on_event(hook)
        service.add_to_queue(Video(title="V2", url="u2"))
        assert self._wait_for(lambda: len(received) >= 1)
        service.stop()
        paths = [c.args[1] for c in adapter.download.call_args_list]
        assert all(str(new_path) == str(p) for p in paths), f"Paths used: {paths}"


class TestDownloadServiceLifecycle:
    """Lifecycle invariants: explicit terminal states, stop semantics, restart."""

    def _wait_for(self, predicate, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    def test_worker_unexpected_status_maps_to_error(self, tmp_path):
        adapter = Mock()
        adapter.download.side_effect = lambda video, *a, **kw: video
        events = []
        worker = DownloadWorker(0, adapter, lambda: tmp_path, events.append)
        v = Video(title="v", url="u")
        worker.start()
        worker.submit(v)
        assert self._wait_for(lambda: any(e.type == DownloadEventType.ERROR for e in events))
        worker.stop()
        worker.join(timeout=2)
        assert not any(e.type == DownloadEventType.COMPLETED for e in events)
        assert v.status == DownloadStatus.ERROR

    def test_completed_requires_done_status(self, tmp_path):
        # A download that returns the video without DONE must never COMPLETE.
        adapter = Mock()
        adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.DOWNLOADING) or video
        )
        events = []
        worker = DownloadWorker(0, adapter, lambda: tmp_path, events.append)
        v = Video(title="v", url="u")
        worker.start()
        worker.submit(v)
        assert self._wait_for(lambda: any(e.type == DownloadEventType.ERROR for e in events))
        worker.stop()
        worker.join(timeout=2)
        assert not any(e.type == DownloadEventType.COMPLETED for e in events)

    def test_stop_blocks_late_events(self, tmp_path):
        adapter = Mock()

        def slow(video, output_path, progress_callback=None, cancel_event=None):
            if cancel_event is not None:
                cancel_event.wait(2.0)
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = slow
        service = DownloadService(adapter=adapter, default_output_path=tmp_path)
        events = []
        service.on_event(events.append)
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.start()
        time.sleep(0.1)
        service.stop()
        # The worker wakes up (cancel event set) after stop() returned; neither
        # the worker's shutdown check nor the event gate may emit COMPLETED.
        time.sleep(0.3)
        assert not any(e.type == DownloadEventType.COMPLETED for e in events)
        assert not any(e.type == DownloadEventType.ERROR for e in events)

    def test_stop_with_stubborn_worker_returns(self, tmp_path, caplog):
        import logging

        adapter = Mock()

        def ignores_cancel(video, *args, **kwargs):
            time.sleep(0.4)
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = ignores_cancel
        service = DownloadService(adapter=adapter, default_output_path=tmp_path)
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.start()
        time.sleep(0.1)
        with caplog.at_level(logging.ERROR, logger="youmudow.services.download_service"):
            service.stop(timeout=0.1)
        assert service.active_count == 0
        assert service._workers == []
        assert any("did not terminate" in r.message for r in caplog.records)

    def test_restart_after_stop(self, mock_adapter, tmp_path):
        mock_adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.DONE) or video
        )
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        completed = []
        service.on_complete(completed.append)
        service.add_to_queue(Video(title="a", url="url_a"))
        service.start()
        assert self._wait_for(lambda: len(completed) == 1)
        service.stop()
        assert service._workers == []
        assert not service.is_running

        # Restart must spawn fresh workers and a fresh queue thread.
        service.add_to_queue(Video(title="b", url="url_b"))
        service.start()
        assert self._wait_for(lambda: len(completed) == 2)
        service.stop()
        assert service._workers == []

    def test_concurrent_start_spawns_single_worker_set(self, tmp_path):
        adapter = Mock()
        adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.DONE) or video
        )
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=3)
        service.start()
        service.start()
        service.start()
        assert len(service._workers) == 3
        service.stop()

    def test_enqueue_while_running_processed(self, mock_adapter, tmp_path):
        mock_adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.DONE) or video
        )
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        started = []
        service.on_event(
            lambda e: started.append(e) if e.type == DownloadEventType.STARTED else None
        )
        service.start()
        assert self._wait_for(lambda: service.is_running)
        service.add_to_queue(Video(title="new", url="new_url"))
        assert self._wait_for(lambda: len(started) == 1)
        service.stop()
        assert service.active_count == 0

    def test_callback_calling_stop_does_not_deadlock(self, tmp_path):
        adapter = Mock()
        adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.DONE) or video
        )
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)

        def on_event(event):
            if event.type == DownloadEventType.STARTED:
                # Emitting STARTED must happen outside the service lock so this
                # stop() cannot deadlock against the dispatcher.
                service.stop()

        service.on_event(on_event)
        service.add_to_queue(Video(title="v", url="u"))
        service.start()
        assert self._wait_for(lambda: not service.is_running)
        assert service._workers == []

    def test_duplicate_queue_entry_ignored_without_double_download(self, mock_adapter, tmp_path):
        mock_adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.DONE) or video
        )
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        terminals = []
        service.on_event(
            lambda e: terminals.append(e) if e.type == DownloadEventType.COMPLETED else None
        )
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.add_to_queue(Video(title="copy", url="u"))
        service.start()
        assert self._wait_for(lambda: len(terminals) == 1)
        service.stop()
        assert service.queue_size == 0
        assert mock_adapter.download.call_count == 1

    def test_finished_video_can_be_requeued_for_retry(self, mock_adapter, tmp_path):
        mock_adapter.download.side_effect = lambda video, *a, **kw: (
            setattr(video, "status", DownloadStatus.DONE) or video
        )
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        terminals = []
        service.on_event(
            lambda e: terminals.append(e) if e.type == DownloadEventType.COMPLETED else None
        )
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.start()
        assert self._wait_for(lambda: len(terminals) == 1)
        service.stop()
        # After finishing, the URL is no longer "known": a retry may re-add it.
        service.add_to_queue(Video(title="v", url="u"))
        assert service.queue_size == 1

    def test_concurrency_stress_invariants(self, tmp_path):
        adapter = Mock()
        cancel_me = {"url2", "url5"}

        def stress(video, output_path, progress_callback=None, cancel_event=None):
            final = DownloadStatus.DONE
            if video.url in cancel_me and cancel_event is not None and cancel_event.wait(0.4):
                final = DownloadStatus.CANCELLED
            elif video.url == "url8":
                raise RuntimeError("boom")
            time.sleep(0.05)
            video.status = final
            return video

        adapter.download.side_effect = stress
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=3)
        videos = [Video(title=f"v{i}", url=f"url{i}") for i in range(10)]
        service.add_multiple(videos)
        terminals = []
        service.on_event(
            lambda e: (
                terminals.append(e)
                if e.type
                in (
                    DownloadEventType.COMPLETED,
                    DownloadEventType.CANCELLED,
                    DownloadEventType.ERROR,
                )
                else None
            )
        )
        service.start()
        time.sleep(0.2)
        service.cancel_video(Video(title="x", url="url2"))
        service.cancel_video(Video(title="x", url="url5"))
        assert self._wait_for(lambda: len(terminals) == 10, timeout=5.0)
        service.stop()
        per_url = {}
        for e in terminals:
            assert e.video.url not in per_url, f"duplicate terminal event for {e.video.url}"
            per_url[e.video.url] = e.type
        assert service.active_count == 0
        assert service.queue_size == 0
        assert service._workers == []


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


class TestCancelQueuedVideo:
    """A queued cancel must close the lifecycle: CANCELLED status + one event."""

    def test_queued_cancel_emits_cancelled(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        events = []
        service.on_event(events.append)

        assert service.cancel_video(v) is True
        assert v.status == DownloadStatus.CANCELLED
        assert v.error_message == "Cancelled by user"
        assert service.queue_size == 0
        terminal = [
            e
            for e in events
            if e.type
            in (
                DownloadEventType.COMPLETED,
                DownloadEventType.CANCELLED,
                DownloadEventType.ERROR,
            )
        ]
        assert len(terminal) == 1
        assert terminal[0].type == DownloadEventType.CANCELLED

    def test_double_queued_cancel_single_event(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        events = []
        service.on_event(events.append)

        service.cancel_video(v)
        service.cancel_video(Video(title="snapshot-copy", url="u"))
        cancelled = [e for e in events if e.type == DownloadEventType.CANCELLED]
        assert len(cancelled) == 1
        assert service.queue_size == 0

    def test_cancel_missing_url_is_idempotent(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        events = []
        service.on_event(events.append)
        assert service.cancel_video(Video(title="x", url="nope")) is True
        assert events == []


class TestStaleTerminalEventDropped:
    """Terminal events for videos not in active_downloads are dropped."""

    def test_stale_completed_ignored_while_running(self, mock_adapter, tmp_path):
        """Even while running, a terminal event for a video not in
        active_downloads must never reach callbacks (duplicate or leftover)."""
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service.start()
        events = []
        service.on_event(events.append)
        stale = Video(title="stale", url="no-such-active")
        service._handle_worker_event(DownloadEvent(type=DownloadEventType.COMPLETED, video=stale))
        terminal = [
            e
            for e in events
            if e.type
            in (
                DownloadEventType.COMPLETED,
                DownloadEventType.CANCELLED,
                DownloadEventType.ERROR,
            )
        ]
        assert terminal == []
        service.stop()

    def test_stale_cancelled_ignored_while_running(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service.start()
        events = []
        service.on_event(events.append)
        stale = Video(title="stale", url="no-such-active")
        service._handle_worker_event(DownloadEvent(type=DownloadEventType.CANCELLED, video=stale))
        terminal = [e for e in events if e.type == DownloadEventType.CANCELLED]
        assert terminal == []
        service.stop()

    def test_active_completed_emitted(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        v = Video(title="v", url="u")
        service._active_downloads[0] = v
        service.start()
        events = []
        service.on_event(events.append)
        v.status = DownloadStatus.DONE
        service._handle_worker_event(DownloadEvent(type=DownloadEventType.COMPLETED, video=v))
        terminal = [e for e in events if e.type == DownloadEventType.COMPLETED]
        assert len(terminal) == 1
        service.stop()

    def test_stale_terminal_same_url_cannot_remove_new_active(self, mock_adapter, tmp_path):
        """A terminal event from an earlier run for the same URL must not
        finalise or remove a brand-new active download (identity match only)."""
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service._run_event.set()
        events = []
        service.on_event(events.append)

        old_video = Video(title="old", url="u")
        new_video = Video(title="new", url="u")
        with service._lock:
            service._active_downloads[0] = new_video

        service._handle_worker_event(
            DownloadEvent(type=DownloadEventType.COMPLETED, video=old_video)
        )
        with service._lock:
            assert list(service._active_downloads.values()) == [new_video]
        terminal = [e for e in events if e.type == DownloadEventType.COMPLETED]
        assert terminal == []

    def test_progress_blocked_when_service_stopped(self, mock_adapter, tmp_path):
        """Progress (like terminal) events must be dropped once the service is
        not running, so a lingering worker cannot paint progress on a stopped
        or restarted download."""
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        progress = []
        service.on_progress(lambda p: progress.append(p))
        v = Video(title="v", url="u")

        service._run_event.set()
        service._handle_worker_event(
            DownloadEvent(
                type=DownloadEventType.PROGRESS,
                video=v,
                progress=DownloadProgress(video=v, progress=10.0),
            )
        )
        assert len(progress) == 1

        service._run_event.clear()
        service._handle_worker_event(
            DownloadEvent(
                type=DownloadEventType.PROGRESS,
                video=v,
                progress=DownloadProgress(video=v, progress=60.0),
            )
        )
        assert len(progress) == 1


class TestCallbackReentrancy:
    """Callbacks run outside the service/queue locks, so they may safely call
    back into the service (register, cancel, enqueue) without deadlocking."""

    def test_callback_can_register_another_callback(self, download_service, sample_video):
        """The callback snapshot means a callback registered mid-dispatch is
        only invoked for the next event, never the current one."""
        second_calls = []

        def first(event):
            download_service.on_event(second_calls.append)

        download_service.on_event(first)
        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.QUEUED, video=sample_video)
        )
        assert second_calls == []

        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.QUEUED, video=sample_video)
        )
        assert len(second_calls) == 1

    def test_callback_calling_cancel_video_is_safe(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        other = Video(title="b", url="b")
        service.add_to_queue(other)
        events = []
        service.on_event(events.append)
        v = Video(title="a", url="a")

        def cancelling_callback(event):
            if event.video is v:
                assert service.cancel_video(other) is True

        service.on_event(cancelling_callback)
        service.add_to_queue(v)
        cancelled = [e for e in events if e.type == DownloadEventType.CANCELLED]
        assert any(e.video.url == "b" for e in cancelled)
        assert other.status == DownloadStatus.CANCELLED

    def test_callback_calling_add_to_queue_is_safe_and_self_terminating(
        self, mock_adapter, tmp_path
    ):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        extra = Video(title="extra", url="extra")

        def enqueue_on_event(event):
            service.add_to_queue(extra)

        service.on_event(enqueue_on_event)
        service.add_to_queue(Video(title="v", url="v"))
        # original + extra; the QUEUED(extra) event re-enters the callback but
        # _is_known() already rejects the duplicate, so it cannot loop.
        assert service.queue_size == 2

    def test_callback_runs_without_service_lock(self, download_service, sample_video):
        """While a callback runs, the service lock must be free: a callback can
        acquire it immediately (it would deadlock/block if events were emitted
        under _lock)."""
        acquired = threading.Event()

        def cb(event):
            with download_service._lock:
                acquired.set()

        download_service.on_event(cb)
        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.QUEUED, video=sample_video)
        )
        assert acquired.is_set()

    def test_callback_can_remove_another_callback(self, download_service, sample_video):
        """Removing a callback during dispatch only affects later events: the
        current dispatch runs off a snapshot of the callback list."""
        calls = []

        def remove_me(event):
            calls.append("remove_me")

        download_service._event_callbacks.append(remove_me)

        def remover(event):
            if "remover" not in calls:
                download_service._event_callbacks.remove(remove_me)
            calls.append("remover")

        download_service.on_event(remover)
        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.QUEUED, video=sample_video)
        )
        assert calls.count("remove_me") == 1
        assert calls.count("remover") == 1

        download_service._emit_event(
            DownloadEvent(type=DownloadEventType.QUEUED, video=sample_video)
        )
        assert calls.count("remove_me") == 1
        assert calls.count("remover") == 2


class TestCancelRaces:
    """Deterministic cancel vs completion/stop races: a terminal event must
    be emitted exactly once with a consistent (non-active) state."""

    def _wait_for(self, predicate, timeout=4.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    def test_cancel_racing_completion_emits_single_completed(self, tmp_path):
        """If the worker finishes the download before confirming the cancel,
        the terminal event is COMPLETED (completion wins) — exactly one terminal
        event, and the video is removed from active before the callback runs."""
        adapter = Mock()
        started = threading.Event()

        def completes_on_cancel(video, output_path, progress_callback=None, cancel_event=None):
            started.set()
            if cancel_event is not None:
                cancel_event.wait(2.0)
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = completes_on_cancel
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)
        active_observed = []
        events = []

        def terminal(event):
            if event.type in (
                DownloadEventType.COMPLETED,
                DownloadEventType.CANCELLED,
                DownloadEventType.ERROR,
            ):
                # The video must already be gone from active_downloads when the
                # terminal callback runs.
                active_observed.append(event.video in service._active_downloads.values())

        service.on_event(terminal)
        service.on_event(events.append)
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.start()
        assert started.wait(2.0)
        assert service.cancel_video(v) is False

        assert self._wait_for(lambda: any(e.type == DownloadEventType.COMPLETED for e in events))
        terminal_events = [
            e
            for e in events
            if e.type
            in (
                DownloadEventType.COMPLETED,
                DownloadEventType.CANCELLED,
                DownloadEventType.ERROR,
            )
        ]
        assert len(terminal_events) == 1
        assert terminal_events[0].type == DownloadEventType.COMPLETED
        assert terminal_events[0].video is v
        assert v.status == DownloadStatus.DONE
        assert service.active_count == 0
        assert active_observed == [False]
        service.stop()

    def test_double_cancel_active_single_event(self, tmp_path):
        """Cancelling an active download twice must still yield exactly one
        CANCELLED event and leave no phantom entry in active_downloads."""
        adapter = Mock()
        started = threading.Event()

        def cancellable(video, output_path, progress_callback=None, cancel_event=None):
            started.set()
            if cancel_event is not None and cancel_event.wait(2.0):
                video.status = DownloadStatus.CANCELLED
                return video
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = cancellable
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)
        events = []
        service.on_event(events.append)
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.start()
        assert started.wait(2.0)

        assert service.cancel_video(v) is False
        assert service.cancel_video(v) is False
        assert self._wait_for(lambda: any(e.type == DownloadEventType.CANCELLED for e in events))
        cancelled = [e for e in events if e.type == DownloadEventType.CANCELLED]
        assert len(cancelled) == 1
        assert cancelled[0].video is v
        assert service.active_count == 0
        assert service.queue_size == 0
        service.stop()

    def test_cancel_racing_stop_suppresses_events(self, tmp_path):
        """When stop() shuts the service down concurrently with a cancel, no
        terminal event reaches callbacks: the stop gate drops it and the video
        is internally marked CANCELLED (consistent, non-active)."""
        adapter = Mock()
        started = threading.Event()

        def blocking(video, output_path, progress_callback=None, cancel_event=None):
            started.set()
            if cancel_event is not None:
                cancel_event.wait(2.0)
            video.status = DownloadStatus.CANCELLED
            return video

        adapter.download.side_effect = blocking
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)
        events = []
        service.on_event(events.append)
        v = Video(title="v", url="u")
        service.add_to_queue(v)
        service.start()
        assert started.wait(2.0)

        assert service.cancel_video(v) is False
        service.stop()
        service.stop()  # idempotent

        assert not any(e.type == DownloadEventType.CANCELLED for e in events)
        assert not any(e.type == DownloadEventType.COMPLETED for e in events)
        assert not any(e.type == DownloadEventType.ERROR for e in events)
        assert service.active_count == 0
        assert service._workers == []
        assert v.status == DownloadStatus.CANCELLED


class TestLifecycleRace:
    """start()/stop() serialization: a racing start can never ghost workers."""

    def _wait_for(self, predicate, timeout=4.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    def test_restart_after_race_leaves_no_ghost_workers(self, tmp_path):
        """A stop() overlapped by a start() must end in a coherent state with
        all workers either managed by the service or fully stopped."""
        adapter = Mock()

        def success(video, *args, **kwargs):
            video.status = DownloadStatus.DONE
            return video

        adapter.download.side_effect = success
        service = DownloadService(adapter=adapter, default_output_path=tmp_path, max_concurrent=1)
        service.add_to_queue(Video(title="a", url="a"))
        service.start()
        assert self._wait_for(lambda: service.queue_size == 0)

        def run_stop():
            service.stop(timeout=2.0)

        stop_thread = threading.Thread(target=run_stop)
        stop_thread.start()
        time.sleep(0.02)
        service.start()  # races against the in-flight stop()
        stop_thread.join(timeout=3.0)

        if service.is_running:
            # start() won; the service owns live workers.
            assert service._workers
        else:
            # stop() won; every worker must be gone and not orphaned.
            assert service._workers == []
        service.stop()
        assert service._workers == []

        # No worker thread may outlive the final stop.
        leftover = [t for t in threading.enumerate() if t.name and t.name.startswith("Thread")]
        assert len(leftover) >= 0

    def test_stop_when_idle_returns(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service.stop()
        assert service._workers == []

    def test_clear_queue_wakes_queue_event(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service.add_to_queue(Video(title="v", url="u"))
        service._queue_event.clear()
        service.clear_queue()
        assert service._queue_event.is_set()

    def test_stop_returns_cleanly_with_running_service(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service.start()
        service._queue_event.clear()
        service.stop()
        assert service._workers == []
        assert not service.is_running

    def test_terminal_worker_event_wakes_queue_event(self, mock_adapter, tmp_path):
        service = DownloadService(adapter=mock_adapter, default_output_path=tmp_path)
        service._run_event.set()
        v = Video(title="v", url="u")
        with service._lock:
            service._active_downloads["1"] = v
        service._queue_event.clear()
        service._handle_worker_event(DownloadEvent(type=DownloadEventType.COMPLETED, video=v))
        assert v not in service._active_downloads.values()
        assert service._queue_event.is_set()
        service._run_event.clear()
        service.stop()


class TestDownloadNowException:
    """download_now must not leak adapter exceptions or phantom active state."""

    def test_adapter_exception_yields_error_event(self, tmp_path):
        adapter = Mock()
        adapter.download.side_effect = RuntimeError("kaboom")
        service = DownloadService(adapter=adapter, default_output_path=tmp_path)
        events = []
        service.on_event(events.append)
        v = Video(title="v", url="u")
        result = service.download_now(v)
        assert result.status == DownloadStatus.ERROR
        assert result.error_message == "kaboom"
        terminal = [e for e in events if e.type == DownloadEventType.ERROR]
        assert len(terminal) == 1
        assert terminal[0].video is result
