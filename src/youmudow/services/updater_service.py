import subprocess
import sys
import threading
from typing import Callable


def get_ytdlp_version() -> str:
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def update_ytdlp(
    on_success: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    def _do_update() -> None:
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
            on_error(str(e))

    threading.Thread(target=_do_update, daemon=True).start()
