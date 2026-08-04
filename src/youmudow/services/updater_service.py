"""yt-dlp update service for YouMuDow."""

import logging
import subprocess
import sys
import threading
from typing import Callable

from youmudow.domain.exceptions import YtDlpNotFoundError

logger = logging.getLogger(__name__)


def get_ytdlp_version() -> str:
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
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
        try:
            result = subprocess.run(
                ["yt-dlp", "-U"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                new_version = get_ytdlp_version()
                on_success(new_version)
                return
        except FileNotFoundError as e:
            logger.warning("yt-dlp binary not found: %s", e)
            on_error(str(YtDlpNotFoundError("yt-dlp binary not found")))
            return
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("yt-dlp self-update failed: %s", e)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                new_version = get_ytdlp_version()
                on_success(new_version)
            else:
                on_error(result.stderr or "Update failed")
        except Exception as e:
            logger.warning("pip install yt-dlp failed: %s", e)
            on_error(str(e))

    threading.Thread(target=_do_update, daemon=True).start()
