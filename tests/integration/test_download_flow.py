from youmudow.domain.models import Video

from conftest import pump


def test_queue_drains_and_updates_the_ui(stack):
    video = Video(title="Song", url="https://example.com/song")
    stack.controller.enqueue(video)
    stack.controller.start_downloads()
    pump(stack.window, lambda: len(stack.download_adapter.downloaded) == 1)
    pump(stack.window, lambda: stack.window._is_downloading is False, timeout=3.0)
    assert stack.downloads.queue_size == 0
    assert stack.download_adapter.progress_steps == [50.0]


def test_failing_download_reports_error_without_hanging(stack):
    stack.download_adapter.fail_urls.add("https://example.com/bad")
    stack.controller.enqueue(Video(title="Bad", url="https://example.com/bad"))
    stack.controller.start_downloads()
    pump(stack.window, lambda: stack.window._is_downloading is False, timeout=5.0)
    assert stack.download_adapter.downloaded == []
    assert stack.downloads.queue_size == 0


def test_completion_notification_is_sent(stack, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "youmudow.services.notification_service.notify",
        lambda title, message: calls.append((title, message)),
    )
    stack.controller.enqueue(Video(title="Song", url="https://example.com/song"))
    stack.controller.start_downloads()
    pump(stack.window, lambda: bool(calls), timeout=3.0)
    assert calls and calls[0][0] == "YouMuDow"
