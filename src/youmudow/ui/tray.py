"""Optional system tray icon.

Everything pystray-related stays behind a lazy import so the app (and its
tests) run unchanged on machines where the tray is unavailable.
"""

import base64
import io
import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def default_image() -> Any:
    """PIL image for the tray icon, built from the embedded PNG."""
    from PIL import Image

    from youmudow.ui.icon import ICON_BASE64

    return Image.open(io.BytesIO(base64.b64decode(ICON_BASE64)))


class TrayIcon:
    """A tray icon with Show / Start downloads / Quit entries."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        on_start_queue: Callable[[], None],
        image_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._on_start_queue = on_start_queue
        self._image_factory = image_factory or default_image
        self._icon: Any = None

    @property
    def available(self) -> bool:
        return self._icon is not None

    def start(self) -> bool:
        """Show the icon. Returns False when the tray is unavailable."""
        if self._icon is not None:
            return True
        try:
            import pystray
        except ImportError:
            logger.info("pystray is not installed; the tray icon is unavailable")
            return False
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Show", lambda: self._on_show(), default=True),
                pystray.MenuItem("Start downloads", lambda: self._on_start_queue()),
                pystray.MenuItem("Quit", lambda: self._on_quit()),
            )
            icon = pystray.Icon("youmudow", self._image_factory(), "YouMuDow", menu)
            threading.Thread(target=icon.run, daemon=True).start()
        except Exception as exc:  # noqa: BLE001 - a broken tray must never break the app
            logger.warning("Could not start the tray icon: %s", exc)
            return False
        self._icon = icon
        return True

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        if icon is None:
            return
        try:
            icon.stop()
        except Exception as exc:  # noqa: BLE001 - stopping a dead icon is not fatal
            logger.debug("Could not stop the tray icon: %s", exc)
