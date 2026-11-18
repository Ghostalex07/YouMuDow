"""Tests for durable queue storage."""

import json
from pathlib import Path

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video
from youmudow.services.download_service import DownloadService
from youmudow.services.queue_store import load_queue, save_queue


class FakeAdapter:
    def download(self, video, output_path, progress_callback=None, cancel_event=None):
        video.status = DownloadStatus.DONE
        return video

    def set_log_callback(self, callback):
        pass


def test_queue_round_trip(tmp_path):
    video = Video(
        title="T",
        url="https://x.test/1",
        uploader="U",
        duration=42,
        thumbnail="https://x.test/t.jpg",
        options=DownloadOptions(
            file_format="flac", quality="best", subtitles=True, subtitle_lang="es"
        ),
    )
    path = tmp_path / "queue.json"
    save_queue(path, [video])
    restored = load_queue(path)
    assert len(restored) == 1
    assert restored[0].title == "T"
    assert restored[0].options.file_format == "flac"
    assert restored[0].options.subtitle_lang == "es"
    assert restored[0].status is DownloadStatus.READY


def test_corrupt_queue_is_ignored_and_kept(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_queue(path) == []
    assert path.exists()


def test_restore_does_not_touch_the_filesystem(tmp_path):
    path = tmp_path / "queue.json"
    save_queue(path, [Video(title="T", url="https://x.test/1")])
    service = DownloadService(
        adapter=FakeAdapter(),
        queue_file=path,
        default_output_path=tmp_path / "deleted-folder",
    )
    assert service.restore_queue() == 1
    assert service.queue_size == 1


def test_entries_without_url_are_dropped(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text(
        '[{"title": "no url"}, {"url": "https://x.test/1", "title": "ok"}]',
        encoding="utf-8",
    )
    assert [v.title for v in load_queue(path)] == ["ok"]


def test_service_persists_and_restores_the_pending_queue(tmp_path):
    path = tmp_path / "queue.json"
    service = DownloadService(adapter=FakeAdapter(), queue_file=path, default_output_path=tmp_path)
    service.add_to_queue(Video(title="A", url="https://x.test/a"))
    service.add_to_queue(Video(title="B", url="https://x.test/b"))
    service.flush_queue()
    assert json.loads(path.read_text(encoding="utf-8"))[0]["url"] == "https://x.test/a"

    restarted = DownloadService(
        adapter=FakeAdapter(), queue_file=path, default_output_path=tmp_path
    )
    assert restarted.restore_queue() == 2
    assert restarted.queue_size == 2


def test_clearing_the_queue_empties_the_file(tmp_path):
    path = tmp_path / "queue.json"
    service = DownloadService(adapter=FakeAdapter(), queue_file=path, default_output_path=tmp_path)
    service.add_to_queue(Video(title="A", url="https://x.test/a"))
    service.clear_queue()
    service.flush_queue()
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_unwritable_queue_file_does_not_break_enqueueing(tmp_path):
    path: Path = tmp_path / "missing" / "dir" / "queue.json"
    service = DownloadService(adapter=FakeAdapter(), queue_file=path, default_output_path=tmp_path)
    service.add_to_queue(Video(title="A", url="https://x.test/a"))
    assert service.queue_size == 1
