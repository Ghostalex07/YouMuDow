"""The optional system tray icon."""

import sys
import types

from youmudow.ui.tray import TrayIcon


def _install_fake_pystray(monkeypatch):
    module = types.ModuleType("pystray")

    class MenuItem:
        def __init__(self, text, action=None, default=False):
            self.text = text
            self.action = action
            self.default = default

    class Menu(list):
        def __init__(self, *items):
            super().__init__(items)

    class Icon:
        def __init__(self, name, image, title, menu):
            self.name = name
            self.image = image
            self.title = title
            self.menu = menu
            self.stopped = False
            self.visible = False

        def run(self, setup=None):
            self.visible = True
            if setup is not None:
                setup(self)

        def stop(self):
            self.stopped = True

    module.MenuItem = MenuItem
    module.Menu = Menu
    module.Icon = Icon
    monkeypatch.setitem(sys.modules, "pystray", module)
    return module


def test_tray_degrades_without_pystray(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", None)
    tray = TrayIcon(lambda: None, lambda: None, lambda: None, lambda: None)
    assert tray.start() is False
    assert tray.available is False


def test_tray_menu_labels_stop_and_callbacks(monkeypatch):
    _install_fake_pystray(monkeypatch)
    calls = []
    tray = TrayIcon(
        lambda: calls.append("show"),
        lambda: calls.append("quit"),
        lambda: calls.append("start"),
        lambda: None,
    )
    assert tray.start() is True
    assert tray.available is True
    icon = tray._icon
    assert [item.text for item in icon.menu] == ["Show", "Start downloads", "Quit"]
    for item in icon.menu:
        item.action()
    assert calls == ["show", "start", "quit"]
    tray.stop()
    assert icon.stopped is True
    assert tray._icon is None
