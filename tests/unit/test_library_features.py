"""Controller-level behaviour for the library and batch tools."""

from datetime import datetime

from youmudow.app.controller import AppController
from youmudow.domain.models import HistoryEntry
from youmudow.services.download_service import DownloadService
from youmudow.services.library_store import LibraryStore


def _controller(tmp_path):
    store = LibraryStore(tmp_path / "db.sqlite")
    downloads = DownloadService(adapter=object(), default_output_path=tmp_path, library_store=store)
    return AppController(download_service=downloads, library_store=store, config=None), store


def test_enqueue_urls_adds_one_video_per_link(tmp_path):
    controller, _ = _controller(tmp_path)
    added = controller.enqueue_urls(
        ["https://youtube.com/watch?v=a", "https://youtube.com/watch?v=b"]
    )
    assert added == 2
    assert [video.url for video in controller.state.get_queue()] == [
        "https://youtube.com/watch?v=a",
        "https://youtube.com/watch?v=b",
    ]


def test_enqueue_urls_skips_duplicates(tmp_path):
    controller, _ = _controller(tmp_path)
    controller.enqueue_urls(["https://youtube.com/watch?v=a"])
    added = controller.enqueue_urls(
        ["https://youtube.com/watch?v=a", "https://youtube.com/watch?v=b"]
    )
    assert added == 1


def test_library_stats_and_missing_entries(tmp_path):
    controller, store = _controller(tmp_path)
    store.add_history(
        HistoryEntry(
            title="Gone",
            url="https://youtube.com/watch?v=gone",
            uploader="Chan",
            file_format="mp3",
            output_path=str(tmp_path / "gone.mp3"),
            downloaded_at=datetime.now().astimezone().isoformat(),
        )
    )
    assert controller.library_stats()["count"] == 1
    assert [entry.title for entry in controller.missing_downloads()] == ["Gone"]


def test_requeue_missing_enqueues_the_lost_downloads(tmp_path):
    controller, store = _controller(tmp_path)
    store.add_history(
        HistoryEntry(
            title="Gone",
            url="https://youtube.com/watch?v=gone",
            uploader="Chan",
            file_format="mp3",
            output_path=str(tmp_path / "gone.mp3"),
            downloaded_at=datetime.now().astimezone().isoformat(),
        )
    )
    assert controller.requeue_missing() == 1
    assert [video.title for video in controller.state.get_queue()] == ["Gone"]


def test_move_in_queue_reorders_state_and_service(tmp_path):
    controller, _ = _controller(tmp_path)
    controller.enqueue_urls(
        [
            "https://youtube.com/watch?v=a",
            "https://youtube.com/watch?v=b",
            "https://youtube.com/watch?v=c",
        ]
    )
    queue = controller.state.get_queue()
    assert controller.move_in_queue(queue[2], 0) is True
    assert next(video.url for video in controller.state.get_queue()).endswith("c")


def test_pause_and_resume_downloads(tmp_path):
    controller, _ = _controller(tmp_path)
    controller.pause_downloads()
    assert controller.downloads_paused is True
    controller.resume_downloads()
    assert controller.downloads_paused is False
