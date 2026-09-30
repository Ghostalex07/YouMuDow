"""yt-dlp update service for YouMuDow."""

import logging
import subprocess
import sys
import threading
from collections.abc import Callable

from youmudow.domain.exceptions import YtDlpNotFoundError

logger = logging.getLogger(__name__)


def get_ytdlp_version() -> str:
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("Could not determine yt-dlp version: %s", e)
        return ""


def update_ytdlp(
    on_success: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    def _do_update() -> None:
        binary_missing = False
        try:
            result = subprocess.run(
                ["yt-dlp", "-U"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode == 0:
                new_version = get_ytdlp_version()
                on_success(new_version)
                return
            binary_error = result.stderr or "yt-dlp self-update failed"
        except FileNotFoundError as e:
            logger.warning("yt-dlp binary not found, falling back to pip: %s", e)
            binary_error = str(e) or "yt-dlp binary not found"
            binary_missing = True
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("yt-dlp self-update failed: %s", e)
            binary_error = str(e)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode == 0:
                logger.info("yt-dlp updated via pip after self-update failed: %s", binary_error)
                new_version = get_ytdlp_version()
                on_success(new_version)
                return
            pip_error = result.stderr or "Update failed"
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("pip install yt-dlp failed: %s", e)
            pip_error = str(e)

        message = (
            f"yt-dlp self-update failed ({binary_error}); pip update also failed ({pip_error})"
        )
        if binary_missing:
            on_error(str(YtDlpNotFoundError(message)))
        else:
            on_error(message)

    threading.Thread(target=_do_update, daemon=True).start()
