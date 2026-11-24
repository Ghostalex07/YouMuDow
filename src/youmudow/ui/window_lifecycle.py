"""Window lifecycle: closing, quitting, settings and the tray icon.

Split out of ``MainWindow`` so the shutdown path (save settings, stop
downloads, tear down the root) is one readable unit instead of a dozen
methods scattered between the menu and the search flow.
"""

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Any

from youmudow.app.config import AppConfig
from youmudow.ui.tray import TrayIcon
from youmudow.ui.window_settings import save_settings

if TYPE_CHECKING:
    from youmudow.ui.window import MainWindow

logger = logging.getLogger(__name__)


class WindowLifecycle:
    """Everything that ends, hides or restores the main window."""

    def __init__(self, window: "MainWindow") -> None:
        self._window = window

    def close(self) -> None:
        """The WM close button: hide into the tray when that is enabled."""
        self.save_settings()
        if self.should_use_tray():
            self._window._tk_root.withdraw()
            return
        self.shutdown()

    def save_settings(self) -> None:
        window = self._window
        detail_panel = window._detail_panel_widget
        if window._config and detail_panel is not None:
            try:
                output_path = window._controller.get_output_path()
            except (tk.TclError, KeyError, TypeError, ValueError) as e:
                logger.debug("Could not read output path: %s", e)
                output_path = None
            save_settings(window._config, detail_panel.options, window._tk_root, output_path)

    def should_use_tray(self) -> bool:
        """True when closing must only hide the window and keep the queue alive."""
        window = self._window
        if not window._config or not window._config.get("minimize_to_tray", False):
            return False
        if window._tray is None:
            window._tray = TrayIcon(
                on_show=self.show_from_tray,
                on_quit=self.quit_from_tray,
                on_start_queue=lambda: window._schedule(window._on_start_queue),
            )
        return window._tray.start()

    def shutdown(self) -> None:
        self.save_settings()
        self._window._controller.stop_downloads()
        self._window.destroy()

    def quit(self) -> None:
        """File > Exit: always leaves the application, tray or not."""
        self.shutdown()

    def quit_from_tray(self) -> None:
        self._window._schedule(self.shutdown)

    def show_from_tray(self) -> None:
        self._window._schedule(self._window._tk_root.deiconify)

    def toggle_tray(self) -> None:
        window = self._window
        if window._config is None:
            return
        enabled = bool(window._tray_var.get())
        window._config.set("minimize_to_tray", enabled)
        window._config.save()
        if enabled:
            # Show the icon now: waiting until the first close leaves the user
            # with no clue the option did anything.
            self.should_use_tray()

    def current_config(self) -> dict[str, Any]:
        config = self._window._config
        if not isinstance(config, AppConfig):
            return {}
        return dict(config.snapshot())
