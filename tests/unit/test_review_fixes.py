"""Regressions found by the resilience-branch review."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock

from youmudow.app.config import DEFAULT_CONFIG
from youmudow.app.controller import AppController
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import Video
from youmudow.services import diagnostics_service, queue_store
from youmudow.services.download_service import DownloadService
from youmudow.services.queue_store import save_queue
from youmudow.ui.tray import TrayIcon


def _drain(service, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if service.active_count == 0:
            return
        time.sleep(0.01)


# --- C1: a restored queue must be startable -------------------------------


def test_restore_queue_fills_the_state_queue_so_downloads_can_start(tmp_path):
    path = tmp_path / "queue.json"
    save_queue(path, [Video(title="A", url="https://x.test/a")])
    service = DownloadService(adapter=Mock(), queue_file=path, default_output_path=tmp_path)
    controller = AppController(search_service=Mock(), download_service=service)

    assert controller.restore_queue() == 1
    assert [v.url for v in controller.state.get_queue()] == ["https://x.test/a"]

    service.start = Mock()  # type: ignore[method-assign]
    controller.start_downloads()
    service.start.assert_called_once()


def test_restored_videos_are_not_queued_twice_when_starting(tmp_path):
    path = tmp_path / "queue.json"
    save_queue(path, [Video(title="A", url="https://x.test/a")])
    adapter = Mock()
    adapter.download.return_value = Video(title="A", url="https://x.test/a")
    service = DownloadService(adapter=adapter, queue_file=path, default_output_path=tmp_path)
    controller = AppController(search_service=Mock(), download_service=service)

    controller.restore_queue()
    controller.start_downloads()
    try:
        assert service.queue_size == 0
        _drain(service)
        assert adapter.download.call_count == 1
    finally:
        service.stop()


# --- I1: quitting from the tray must save the settings --------------------


# --- I2: a corrupt queue file must survive startup ------------------------


def test_restore_keeps_a_corrupt_queue_file_untouched(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text("{not json", encoding="utf-8")
    service = DownloadService(adapter=Mock(), queue_file=path)

    assert service.restore_queue() == 0
    assert path.read_text(encoding="utf-8") == "{not json"


# --- I4 / I5: diagnostics redaction and log scrubbing ---------------------


def test_sensitive_keys_only_names_real_config_keys():
    assert diagnostics_service.SENSITIVE_KEYS <= set(DEFAULT_CONFIG)
    assert "profile" in diagnostics_service.SENSITIVE_KEYS


def test_report_redacts_the_browser_profile():
    report = diagnostics_service.build_report(config={"profile": "Ada Lovelace", "format": "mp3"})
    assert "Ada Lovelace" not in report


def test_log_tail_scrubs_the_home_directory():
    home = str(Path.home())
    report = diagnostics_service.build_report(log_tail=f"Destination: {home}/Music/a.mp3")
    assert home not in report
    assert "~/Music/a.mp3" in report


# --- I6: persistence is serialized across threads ------------------------


def test_persisting_from_two_threads_does_not_interleave(tmp_path, monkeypatch):
    path = tmp_path / "queue.json"
    service = DownloadService(adapter=Mock(), queue_file=path)
    entered = []
    first_in = threading.Event()
    release = threading.Event()

    def slow_save(destination, videos):
        entered.append(1)
        first_in.set()
        release.wait(2.0)
        queue_store.save_queue(destination, videos)

    monkeypatch.setattr("youmudow.services.download_service.save_queue", slow_save)

    first = threading.Thread(
        target=service.add_to_queue, args=(Video(title="A", url="https://x/a"),)
    )
    first.start()
    assert first_in.wait(1.0)

    second = threading.Thread(
        target=service.add_to_queue, args=(Video(title="B", url="https://x/b"),)
    )
    second.start()
    second.join(0.15)
    assert len(entered) == 1, "the second writer entered while the first was still saving"

    release.set()
    first.join(2.0)
    second.join(2.0)
    assert not second.is_alive()


# --- I7: an in-flight download is re-queued on shutdown ------------------


def test_stopping_requeues_the_active_download(tmp_path):
    path = tmp_path / "queue.json"
    started = threading.Event()
    blocker = threading.Event()

    class SlowAdapter:
        def download(self, video, output_path, progress_callback=None, cancel_event=None):
            started.set()
            blocker.wait(2.0)
            video.status = DownloadStatus.CANCELLED
            return video

    service = DownloadService(adapter=SlowAdapter(), queue_file=path)
    service.add_to_queue(Video(title="A", url="https://x/a"))
    service.start()
    assert started.wait(2.0)
    service.stop()
    blocker.set()

    restarted = DownloadService(adapter=Mock(), queue_file=path)
    assert restarted.restore_queue() == 1


# --- C3: the tray only reports success when the icon is live -------------


class _FakeIcon:
    def __init__(self, name, image, title, menu):
        self.menu = menu
        self.visible = False
        self.stopped = False

    def run(self, setup=None):
        self.visible = True
        if setup is not None:
            setup(self)

    def stop(self):
        self.stopped = True


def test_tray_reports_failure_when_the_backend_raises(monkeypatch):
    fake = Mock()
    fake.Icon.return_value.run.side_effect = RuntimeError("no status notifier host")
    fake.Menu = lambda *items: items
    fake.MenuItem = lambda text, action, **kwargs: (text, action)
    monkeypatch.setitem(__import__("sys").modules, "pystray", fake)

    tray = TrayIcon(lambda: None, lambda: None, lambda: None)
    assert tray.start(timeout=0.2) is False


def test_tray_reports_success_once_the_icon_is_up(monkeypatch):
    fake = Mock()
    fake.Icon.return_value = _FakeIcon("youmudow", None, "YouMuDow", [])
    fake.Menu = lambda *items: items
    fake.MenuItem = lambda text, action, **kwargs: (text, action)
    monkeypatch.setitem(__import__("sys").modules, "pystray", fake)

    tray = TrayIcon(lambda: None, lambda: None, lambda: None)
    assert tray.start(timeout=1.0) is True
    tray.stop()
