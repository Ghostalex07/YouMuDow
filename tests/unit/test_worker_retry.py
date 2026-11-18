"""Retry behaviour of the download worker."""

import time
from pathlib import Path

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video
from youmudow.services.download_events import DownloadEventType
from youmudow.services.download_worker import DownloadWorker


class FlakyAdapter:
    def __init__(self, failures: int):
        self.calls = 0
        self._failures = failures

    def download(self, video, output_path, progress_callback=None, cancel_event=None, **kwargs):
        self.calls += 1
        if self.calls <= self._failures:
            raise RuntimeError("transient")
        video.status = DownloadStatus.DONE
        return video


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def _run_one(adapter, max_retries, retry_delay=0.01):
    events = []
    worker = DownloadWorker(
        1,
        adapter,
        lambda: Path("/tmp"),
        events.append,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
    worker.start()
    worker.submit(Video(title="T", url="u"))
    _wait_until(
        lambda: any(
            e.type in (DownloadEventType.COMPLETED, DownloadEventType.ERROR) for e in events
        )
    )
    worker.stop()
    return adapter.calls, events[-1].type


def test_worker_retries_then_succeeds():
    calls, last = _run_one(FlakyAdapter(failures=2), max_retries=2)
    assert calls == 3
    assert last is DownloadEventType.COMPLETED


def test_worker_gives_up_after_max_retries():
    calls, last = _run_one(FlakyAdapter(failures=9), max_retries=1)
    assert calls == 2
    assert last is DownloadEventType.ERROR


def test_worker_without_retries_attempts_once():
    calls, last = _run_one(FlakyAdapter(failures=1), max_retries=0)
    assert calls == 1
    assert last is DownloadEventType.ERROR


def test_cancel_during_retry_wait_stops_the_worker():
    adapter = FlakyAdapter(failures=9)
    events = []
    worker = DownloadWorker(
        1, adapter, lambda: Path("/tmp"), events.append, max_retries=3, retry_delay=5.0
    )
    worker.start()
    worker.submit(Video(title="T", url="u"))
    assert _wait_until(lambda: adapter.calls == 1, timeout=1.0)
    worker.cancel()
    assert _wait_until(
        lambda: any(e.type is DownloadEventType.CANCELLED for e in events), timeout=1.0
    )
    worker.stop()
    assert adapter.calls == 1
