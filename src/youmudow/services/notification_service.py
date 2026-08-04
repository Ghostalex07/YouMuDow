"""System desktop notifications for YouMuDow."""

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def notify(title: str, message: str) -> None:
    try:
        system = platform.system()
        if system == "Linux":
            subprocess.Popen(
                ["notify-send", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Darwin":
            safe_msg = message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            safe_title = title.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            script = f'display notification "{safe_msg}" with title "{safe_title}"'
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Windows":
            try:
                import plyer.notification  # type: ignore[import-not-found]

                plyer.notification.notify(title=title, message=message, timeout=5)
            except ImportError:
                logger.debug("plyer not installed; skipping desktop notification")
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("Could not show desktop notification: %s", e)
