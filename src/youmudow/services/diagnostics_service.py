"""Build and export a single diagnostics file for support requests."""

import json
import logging
import platform
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from youmudow import __version__
from youmudow.app.config import CONFIG_DIR, DEFAULT_CONFIG, AppConfig
from youmudow.logging_config import LOG_FILE_NAME
from youmudow.services.environment_service import youtube_environment_status
from youmudow.services.updater_service import get_ytdlp_version

logger = logging.getLogger(__name__)

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "cookies_file",
        "cookies_profile",
        "cookies_from_browser",
        "search_history",
        "output_path",
    }
)
REDACTED = "<redacted>"
LOG_TAIL_LINES = 100


def redact_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Copy ``config``, replacing anything private or identifying."""
    return {key: REDACTED if key in SENSITIVE_KEYS else value for key, value in config.items()}


def _ffmpeg_version() -> str:
    """First line of ``ffmpeg -version``, or "not found"."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "not found"
    lines = (result.stdout or "").splitlines()
    return lines[0] if lines else "not found"


def _log_tail(limit: int = LOG_TAIL_LINES) -> str:
    """Last lines of the current log file, or "" when there is none."""
    try:
        text = (CONFIG_DIR / LOG_FILE_NAME).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-limit:])


def _current_config() -> dict[str, Any]:
    config = AppConfig()
    return {key: config.get(key) for key in DEFAULT_CONFIG}


def build_report(
    log_tail: str = "",
    config: Mapping[str, Any] | None = None,
) -> str:
    """Render the full report. Missing pieces degrade to "not found"."""
    config = _current_config() if config is None else dict(config)
    environment = youtube_environment_status()
    sections = [
        "YouMuDow diagnostics",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"App version: {__version__}",
        f"Platform: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"yt-dlp: {get_ytdlp_version() or 'not found'}",
        f"ffmpeg: {_ffmpeg_version()}",
        "",
        "YouTube environment",
        json.dumps(environment, indent=2, sort_keys=True, default=str),
        "",
        "Config",
        json.dumps(redact_config(config), indent=2, sort_keys=True, default=str),
        "",
        "Log tail",
        log_tail or "(no log entries)",
    ]
    return "\n".join(sections) + "\n"


def export_diagnostics(destination: Path) -> Path:
    """Write the report to ``destination``, creating its parent directory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_report(log_tail=_log_tail()), encoding="utf-8")
    return destination
