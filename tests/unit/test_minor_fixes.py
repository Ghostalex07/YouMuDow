"""Regression tests for the deferred minors from the resilience branch review."""

import threading
import time
from pathlib import Path

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video
from youmudow.services.download_events import DownloadEventType
from youmudow.services.download_worker import DownloadWorker

TERMINAL = (DownloadEventType.COMPLETED, DownloadEventType.ERROR, DownloadEventType.CANCELLED)


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def _run(adapter, max_retries=1, retry_delay=0.01, log_callback=None):
    events: list = []
    worker = DownloadWorker(
        1,
        adapter,
        lambda: Path("/tmp"),
        events.append,
        max_retries=max_retries,
        retry_delay=retry_delay,
        log_callback=log_callback,
    )
    worker.start()
    worker.submit(Video(title="T", url="u"))
    assert _wait_until(lambda: any(e.type in TERMINAL for e in events))
    worker.stop()
    return events


class FailingAdapter:
    def __init__(self, failures=1):
        self.calls = 0
        self._failures = failures
        self.seen_retries: list = []

    def download(self, video, output_path, cb=None, cancel_event=None, **kwargs):
        self.calls += 1
        self.seen_retries.append(kwargs.get("retries"))
        if self.calls <= self._failures:
            raise RuntimeError("transient")
        video.status = DownloadStatus.DONE
        return video


def test_retry_progress_event_carries_a_renderable_payload():
    events = _run(FailingAdapter(failures=1))
    retry_progress = [
        e for e in events if e.type is DownloadEventType.PROGRESS and e.progress is not None
    ]
    assert retry_progress, "the retry must emit progress the UI can render"


def test_cancel_during_the_attempt_reports_cancelled_not_error():
    class CancellingAdapter:
        def download(self, video, output_path, cb=None, cancel_event=None, **kwargs):
            cancel_event.set()
            raise RuntimeError("stopped by user")

    events = _run(CancellingAdapter(), max_retries=3)
    assert events[-1].type is DownloadEventType.CANCELLED


def test_service_disables_ytdlp_internal_retries_when_it_retries_itself():
    from unittest.mock import Mock

    from youmudow.services.download_service import DownloadService

    adapter = Mock()
    DownloadService(adapter=adapter, max_retries=2)
    assert adapter.set_retry_override.call_args.args == (0,)

    adapter.reset_mock()
    DownloadService(adapter=adapter, max_retries=0)
    assert adapter.set_retry_override.call_args.args == (None,)


def test_retry_warning_reaches_the_on_screen_log():
    messages: list[str] = []
    _run(FailingAdapter(failures=2), retry_delay=0.01, log_callback=messages.append)
    assert any("[RETRY]" in message for message in messages)


def test_queue_persistence_runs_off_the_caller_thread(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from youmudow.services import download_service as ds_module
    from youmudow.services.download_service import DownloadService

    path = tmp_path / "queue.json"
    threads: list = []
    real_save = ds_module.save_queue

    def recording_save(target, videos):
        threads.append(threading.current_thread())
        real_save(target, videos)

    monkeypatch.setattr(ds_module, "save_queue", recording_save)
    service = DownloadService(adapter=Mock(), queue_file=path)
    service.add_to_queue(Video(title="A", url="https://x.test/a"))
    assert _wait_until(lambda: bool(threads), timeout=3.0), "the queue must be written"
    assert threads[0] is not threading.main_thread()


def test_queue_file_does_not_store_cookie_settings(tmp_path):
    from youmudow.domain.models import DownloadOptions
    from youmudow.services.queue_store import load_queue, save_queue

    path = tmp_path / "queue.json"
    options = DownloadOptions(
        use_cookies=True,
        cookies_file="/home/u/secret-cookies.txt",
        cookies_from_browser="firefox",
        cookies_profile="Work",
    )
    save_queue(path, [Video(title="A", url="https://x.test/a", options=options)])
    text = path.read_text(encoding="utf-8")
    assert "secret-cookies.txt" not in text
    assert "Work" not in text
    restored = load_queue(path)[0]
    assert restored.options.use_cookies is True


def test_reset_keeps_the_queue_file_and_retry_setting(tmp_path):
    from unittest.mock import Mock

    from youmudow.app.config import AppConfig
    from youmudow.app.controller import AppController

    config = AppConfig()
    config.set("max_retries", 3)
    queue = tmp_path / "queue.json"
    controller = AppController(search_service=Mock(), config=config, queue_file=queue)
    controller.reset()
    assert controller._download_service._queue_file == queue
    assert controller._download_service.max_retries == 3


def test_diagnostics_export_uses_the_live_config(tmp_path):
    from youmudow.services.diagnostics_service import export_diagnostics

    destination = export_diagnostics(
        tmp_path / "diag.txt", config={"format": "mp3", "cookies_file": "/home/u/secret.txt"}
    )
    report = destination.read_text(encoding="utf-8")
    assert "<redacted>" in report
    assert "/home/u/secret.txt" not in report


def test_log_tail_is_bounded_for_a_huge_log(tmp_path, monkeypatch):
    from youmudow.services import diagnostics_service

    monkeypatch.setattr(diagnostics_service, "CONFIG_DIR", tmp_path)
    log = tmp_path / diagnostics_service.LOG_FILE_NAME
    log.write_text("x" * 2_000_000 + "\nlast line\n", encoding="utf-8")
    tail = diagnostics_service._log_tail()
    assert "last line" in tail
    assert len(tail) < 300_000
