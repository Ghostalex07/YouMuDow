"""Queue reordering and pausing."""

import time

from youmudow.domain.models import Video
from youmudow.services.download_queue import DownloadQueue
from youmudow.services.download_service import DownloadService


class _RecordingAdapter:
    def __init__(self):
        self.done: list[str] = []

    def download(self, video, output_path, progress_callback=None, cancel_event=None):
        self.done.append(video.url)
        from youmudow.domain.enums import DownloadStatus

        video.status = DownloadStatus.DONE
        return video


def test_move_entry_reorders_the_queue():
    queue = DownloadQueue()
    a = Video(title="A", url="https://x.test/a", queue_id="1")
    b = Video(title="B", url="https://x.test/b", queue_id="2")
    c = Video(title="C", url="https://x.test/c", queue_id="3")
    for video in (a, b, c):
        queue.add(video)

    assert queue.move_entry(c, 0) is True
    assert [video.url for video in queue.peek()] == [
        "https://x.test/c",
        "https://x.test/a",
        "https://x.test/b",
    ]


def test_move_entry_rejects_unknown_videos():
    queue = DownloadQueue()
    queue.add(Video(title="A", url="https://x.test/a", queue_id="1"))
    assert queue.move_entry(Video(title="Z", url="https://x.test/z", queue_id="9"), 0) is False


def test_service_pauses_and_resumes_dispatching(tmp_path):
    adapter = _RecordingAdapter()
    service = DownloadService(adapter=adapter, default_output_path=tmp_path)
    service.add_to_queue(Video(title="A", url="https://x.test/a"))
    service.pause()
    service.start()
    try:
        time.sleep(0.3)
        assert service.is_paused is True
        assert adapter.done == []

        service.resume()
        deadline = time.monotonic() + 3.0
        while not adapter.done and time.monotonic() < deadline:
            time.sleep(0.01)
        assert adapter.done == ["https://x.test/a"]
    finally:
        service.stop()
