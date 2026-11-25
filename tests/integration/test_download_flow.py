from conftest import pump

from youmudow.domain.models import Video


def _settled(stack, attempts=1):
    """Wait for the attempt to happen *and* the service to go idle.

    Checking only the counters is racy: they are already zero before the
    dispatcher picks the item up.
    """
    idle = stack.downloads.active_count == 0 and stack.downloads.queue_size == 0
    return len(stack.download_adapter.attempts) >= attempts and idle


def test_queue_drains_and_updates_the_ui(stack):
    video = Video(title="Song", url="https://example.com/song")
    stack.controller.enqueue(video)
    stack.controller.start_downloads()
    pump(stack.window, lambda: len(stack.download_adapter.downloaded) == 1)
    pump(stack.window, lambda: _settled(stack), timeout=3.0)
    assert stack.downloads.queue_size == 0
    assert stack.download_adapter.progress_steps == [50.0]


def test_failing_download_reports_error_without_hanging(stack, monkeypatch):
    messages = []
    monkeypatch.setattr(stack.window, "_set_status", lambda *a, **k: messages.append(a[0]))
    stack.download_adapter.fail_urls.add("https://example.com/bad")
    stack.controller.enqueue(Video(title="Bad", url="https://example.com/bad"))
    stack.controller.start_downloads()
    pump(stack.window, lambda: _settled(stack), timeout=5.0)
    pump(
        stack.window,
        lambda: any("error" in str(message).lower() for message in messages),
        timeout=2.0,
    )
    assert stack.download_adapter.downloaded == []
    assert stack.controller.state.get_snapshot().active_downloads == []
    assert any("error" in str(message).lower() for message in messages)


def test_adapter_exception_reaches_the_worker_error_path(stack, monkeypatch):
    messages = []
    monkeypatch.setattr(stack.window, "_set_status", lambda *a, **k: messages.append(a[0]))
    stack.download_adapter.raise_urls.add("https://example.com/boom")
    stack.controller.enqueue(Video(title="Boom", url="https://example.com/boom"))
    stack.controller.start_downloads()
    pump(stack.window, lambda: _settled(stack), timeout=5.0)
    pump(stack.window, lambda: bool(messages), timeout=2.0)
    assert stack.controller.state.get_snapshot().active_downloads == []
    assert any("error" in str(message).lower() for message in messages)


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


def test_failures_are_summarized_and_can_be_retried(stack):
    stack.download_adapter.fail_urls.add("https://example.com/bad")
    stack.controller.enqueue(Video(title="Bad", url="https://example.com/bad"))
    stack.controller.start_downloads()
    pump(stack.window, lambda: _settled(stack), timeout=5.0)
    pump(stack.window, lambda: len(stack.controller.state.get_failed_downloads()) == 1)
    queue_panel = stack.window._detail_panel.queue
    queue_panel.toggle()  # opening the panel refreshes its rows
    pump(stack.window, lambda: bool(queue_panel._problems_label.cget("text")))
    assert "other error" in queue_panel._problems_label.cget("text").lower()

    queue_panel._retry_failed_btn.invoke()
    # The service is still running, so the re-queued entry is dispatched again.
    pump(stack.window, lambda: len(stack.download_adapter.attempts) >= 2, timeout=5.0)
