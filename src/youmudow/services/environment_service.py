"""yt-dlp environment diagnostics and repair for YouMuDow.

YouTube now requires an external JavaScript runtime (EJS) to solve the
JavaScript challenges that produce working download URLs. Since October 2025,
YouTube extraction without a JS runtime is deprecated and, in practice,
downloads fail with ``HTTP Error 403: Forbidden`` (an unsigned or stale URL is
rejected by YouTube's servers).

yt-dlp enables Deno by default and auto-detects it; Node, QuickJS, etc. must be
enabled explicitly with ``--js-runtimes``. Pip-installed yt-dlp additionally
needs the ``yt-dlp-ejs`` companion package (ships with ``yt-dlp[default]``) so
the actual challenge-solver scripts are available locally.
"""

import importlib.util
import logging
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Ordered by preference, as ``(binary on PATH, yt-dlp runtime name)`` pairs.
# ``deno`` is enabled by yt-dlp by default, so only node/quickjs need an explicit
# ``--js-runtimes`` flag. QuickJS ships a binary named ``qjs`` but yt-dlp only
# accepts the runtime key ``quickjs``, so the two names must not be conflated.
JS_RUNTIMES: tuple[tuple[str, str], ...] = (
    ("deno", "deno"),
    ("node", "node"),
    ("quickjs", "quickjs"),
    ("qjs", "quickjs"),
    ("bun", "bun"),
)

_EJS_MODULE = "yt_dlp_ejs"
_PIP_TARGET = "yt-dlp[default]"


def detect_js_runtime() -> str | None:
    """Return the yt-dlp runtime name of the first supported JS runtime on PATH."""
    for binary, runtime in JS_RUNTIMES:
        if shutil.which(binary):
            return runtime
    return None


def js_runtimes_flag() -> list[str]:
    """Return the ``--js-runtimes`` args for the detected runtime.

    Empty when no runtime is found or when the runtime is deno (already enabled
    by yt-dlp by default).
    """
    runtime = detect_js_runtime()
    if runtime and runtime != "deno":
        return ["--js-runtimes", runtime]
    return []


def is_ejs_installed() -> bool:
    """Return True when the ``yt-dlp-ejs`` challenge solver scripts are present."""
    return importlib.util.find_spec(_EJS_MODULE) is not None


def clear_ytdlp_cache() -> bool:
    """Clear yt-dlp's cached player/challenge data.

    A stale cached player produces signatures YouTube rejects with 403; clearing
    the cache forces yt-dlp to fetch the current player on the next run.
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--rm-cache-dir"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        logger.debug("Could not clear yt-dlp cache", exc_info=True)
        return False


def install_ejs_scripts(
    on_success: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    """Install/upgrade ``yt-dlp[default]`` (includes the EJS scripts).

    Runs in a background thread; callbacks are invoked from that thread.
    """

    def _do() -> None:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", _PIP_TARGET],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0:
                on_success(f"{_PIP_TARGET} updated (EJS scripts included)")
            else:
                on_error(result.stderr.strip() or f"Failed to install {_PIP_TARGET}")
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("pip install %s failed: %s", _PIP_TARGET, e)
            on_error(str(e))

    threading.Thread(target=_do, daemon=True).start()


def repair_youtube_environment(
    on_success: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    """Clear the yt-dlp cache and refresh ``yt-dlp[default]`` in background.

    This is the "make YouTube work again" action: it clears the stale player
    cache and installs the latest yt-dlp together with the EJS scripts. The JS
    runtime itself (deno/node) is detected and passed by the downloader.
    """

    def _do() -> None:
        cleared = clear_ytdlp_cache()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", _PIP_TARGET],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("yt-dlp repair failed: %s", e)
            on_error(str(e))
            return
        if result.returncode != 0:
            on_error(result.stderr.strip() or f"Failed to install {_PIP_TARGET}")
            return
        cache_note = "cache cleared" if cleared else "cache was not cleared"
        on_success(f"{_PIP_TARGET} updated ({cache_note})")

    threading.Thread(target=_do, daemon=True).start()


def youtube_environment_status() -> dict[str, object]:
    """Return a snapshot of the YouTube environment for diagnostics."""
    return {
        "yt_dlp_installed": shutil.which("yt-dlp") is not None,
        "js_runtime": detect_js_runtime(),
        "ejs_installed": is_ejs_installed(),
    }
