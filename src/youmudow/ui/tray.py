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

    def start(self, timeout: float = 2.0) -> bool:
        """Show the icon, waiting until the backend reports it is live.

        Reporting success before the icon exists strands the app: closing the
        window withdraws it with no tray entry to bring it back. The backend
        runs in a thread and only calls ``setup`` once the icon is up, so we
        wait for that signal (or for the thread to fail) before answering.
        """
        if self._icon is not None:
            return True
        try:
            import pystray
        except ImportError:
            logger.info("pystray is not installed; the tray icon is unavailable")
            return False

        ready = threading.Event()
        failure: list[BaseException] = []
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Show", lambda: self._on_show(), default=True),
                pystray.MenuItem("Start downloads", lambda: self._on_start_queue()),
                pystray.MenuItem("Quit", lambda: self._on_quit()),
            )
            icon = pystray.Icon("youmudow", self._image_factory(), "YouMuDow", menu)
        except Exception as exc:  # noqa: BLE001 - a broken tray must never break the app
            logger.warning("Could not create the tray icon: %s", exc)
            return False

        def run_icon() -> None:
            try:
                icon.run(setup=lambda _icon: ready.set())
            except BaseException as exc:  # noqa: BLE001 - log it, never crash the app
                failure.append(exc)
                logger.warning("The tray backend stopped: %s", exc)
            finally:
                ready.set()

        threading.Thread(target=run_icon, daemon=True).start()
        ready.wait(timeout)
        if failure or not getattr(icon, "visible", True):
            logger.warning("The tray icon did not start; continuing without it")
            self._stop_icon(icon)
            return False
        self._icon = icon
        return True

    def _stop_icon(self, icon: Any) -> None:
        try:
            icon.stop()
        except Exception as exc:  # noqa: BLE001 - stopping a dead icon is not fatal
            logger.debug("Could not stop the tray icon: %s", exc)

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        if icon is None:
            return
        try:
            icon.stop()
        except Exception as exc:  # noqa: BLE001 - stopping a dead icon is not fatal
            logger.debug("Could not stop the tray icon: %s", exc)
