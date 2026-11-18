import logging
from typing import ClassVar

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


class FakeTray:
    instances: ClassVar[list] = []

    def __init__(self, *args, **kwargs):
        self.started = False
        self.stopped = False
        FakeTray.instances.append(self)

    def start(self):
        self.started = True
        return True

    def stop(self):
        self.stopped = True


def test_close_with_tray_enabled_hides_the_window_and_keeps_downloading(stack, monkeypatch):
    from youmudow.ui import window as window_module

    FakeTray.instances.clear()
    monkeypatch.setattr(window_module, "TrayIcon", FakeTray)
    stack.config.set("minimize_to_tray", True)
    stack.controller.enqueue(Video(title="Song", url="https://example.com/song"))
    stack.controller.start_downloads()
    stack.window._on_close()
    assert stack.window._root.state() == "withdrawn"
    assert stack.downloads.is_running is True
    assert FakeTray.instances and FakeTray.instances[-1].started is True


def test_quit_from_tray_uses_the_real_shutdown_path(stack, monkeypatch):
    from youmudow.ui import window as window_module

    FakeTray.instances.clear()
    monkeypatch.setattr(window_module, "TrayIcon", FakeTray)
    # Tray callbacks arrive on a worker thread; here we are already on the UI
    # thread, so run the marshalled call inline instead of waiting for a loop.
    monkeypatch.setattr(stack.window, "_schedule", lambda callback, *args: callback(*args))
    stack.config.set("minimize_to_tray", True)
    stack.window._on_close()
    stack.window._quit_from_tray()
    assert stack.downloads.is_running is False
    assert FakeTray.instances[-1].stopped is True


def test_exit_menu_quits_even_when_the_tray_is_enabled(stack, monkeypatch):
    stack.config.set("minimize_to_tray", True)
    monkeypatch.setattr(stack.window, "_should_use_tray", lambda: True)
    stack.window._on_quit()
    assert stack.downloads.is_running is False


def test_shutdown_saves_the_settings_before_destroying(stack, monkeypatch):
    order = []
    real_destroy = type(stack.window).destroy

    def destroy(self):
        order.append("destroy")
        real_destroy(self)

    monkeypatch.setattr(type(stack.window), "_save_settings", lambda self: order.append("save"))
    monkeypatch.setattr(type(stack.window), "destroy", destroy)
    stack.window._shutdown()
    assert order == ["save", "destroy"]
