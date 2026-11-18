import logging

from youmudow.domain.models import Video


def test_close_stops_downloads_and_destroys_the_root(stack):
    stack.controller.enqueue(Video(title="Song", url="https://example.com/song"))
    stack.controller.start_downloads()
    stack.window._on_close()
    assert stack.downloads.is_running is False


def test_terminal_callback_after_destroy_is_harmless(stack, caplog):
    callback = stack.controller._download_complete_callback
    video = Video(title="Late", url="https://example.com/late")
    stack.window.destroy()
    with caplog.at_level(logging.DEBUG):
        callback(video)  # a worker finishing after the window is gone
    assert "Late" not in caplog.text  # nothing rendered, nothing raised
