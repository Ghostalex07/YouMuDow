"""Pure parsers for yt-dlp output.

Every function takes text yt-dlp wrote (or a URL the user entered) and returns
data: nothing here spawns processes, touches the filesystem or keeps state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from youmudow.domain.models import Video

ERROR_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("private video", "video is private"), "Video is private"),
    (("not available", "unavailable"), "Video not available"),
    (("removed", "deleted"), "Video has been removed"),
    (("connection", "network", "http error"), "Connection error"),
    (("permission denied", "permission"), "Permission denied"),
    (("auth", "login", "sign in"), "Authentication required"),
    (("captcha", "verification"), "CAPTCHA required"),
]

COOKIE_BROWSER_NAMES: tuple[str, ...] = ("chrome", "firefox", "edge", "brave", "opera", "vivaldi")

COOKIE_ERROR_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("locked", "lock"), "Cookies locked - browser may be running"),
    (("profile",), "Browser profile not accessible"),
    (("database",), "Cookies database corrupted or inaccessible"),
    (("no such file", "directory"), "Browser profile directory not found"),
]

# Keywords whose presence marks a failure as a cookie/authentication problem
# worth retrying without credentials.
COOKIE_ERROR_KEYWORDS: tuple[str, ...] = (
    "could not find",
    "cookies",
    "database",
    "chrome",
    "firefox",
    "edge",
    "brave",
    "opera",
    "vivaldi",
    "profile",
    "not found",
    "locked",
)

_PROGRESS_SPEED_RE = re.compile(r"\[download\]\s+(\d+\.?\d*)%.*?at\s+(\S+).*?ETA\s+(\S+)")
_PROGRESS_SIZE_RE = re.compile(r"\[download\]\s+(\d+\.?\d*)%.*?of\s+~?([~\d.]+\w+)")
_PROGRESS_BARE_RE = re.compile(r"\[download\]\s+(\d+\.?\d*)%")


@dataclass
class ProgressInfo:
    """Parsed progress information from yt-dlp output."""

    progress: float
    speed: str
    eta: str
    size: str
    line: str = ""


def parse_progress(line: str) -> ProgressInfo | None:
    """Parse a ``[download]`` progress line, or return ``None`` if it is not one.

    Handles the full form (percentage, size, speed and ETA), the size-only form
    and a bare percentage.
    """
    speed_match = _PROGRESS_SPEED_RE.search(line)
    if speed_match:
        return ProgressInfo(
            progress=float(speed_match.group(1)),
            speed=speed_match.group(2),
            eta=speed_match.group(3),
            size="",
            line=line,
        )

    size_match = _PROGRESS_SIZE_RE.search(line)
    if size_match:
        return ProgressInfo(
            progress=float(size_match.group(1)),
            speed="",
            eta="",
            size=size_match.group(2),
            line=line,
        )

    # Fallback: bare percentage (no speed/ETA), e.g. "[download]  45.2%"
    bare_match = _PROGRESS_BARE_RE.search(line)
    if bare_match:
        return ProgressInfo(
            progress=float(bare_match.group(1)),
            speed="",
            eta="",
            size="",
            line=line,
        )

    return None


def parse_json_output(stdout: str) -> dict | None:
    """Parse yt-dlp JSON output, tolerating surrounding log lines."""
    decoder = json.JSONDecoder()

    def try_parse(text: str) -> dict | None:
        text = text.lstrip()
        if not text:
            return None
        try:
            data, _ = decoder.raw_decode(text)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None

    data = try_parse(stdout)
    if data:
        return data

    first_brace = stdout.find("{")
    if first_brace >= 0:
        data = try_parse(stdout[first_brace:])
        if data:
            return data

    for line in stdout.strip().splitlines():
        data = try_parse(line)
        if data:
            return data
    return None


def parse_flat_results(stdout: str) -> list[Video]:
    """Parse yt-dlp ``--flat-playlist --print`` output into Video objects.

    Each accepted line has the shape ``url | title | uploader | duration``;
    anything else is ignored.
    """
    videos: list[Video] = []
    if not stdout:
        return videos
    for line in stdout.strip().split("\n"):
        if line and " | " in line:
            parts = line.split(" | ", 3)
            if len(parts) >= 4:
                videos.append(
                    Video(
                        title=parts[1].strip(),
                        url=parts[0].strip(),
                        uploader=parts[2].strip(),
                        duration=parse_duration(parts[3]),
                    )
                )
    return videos


def parse_duration(value: str | None) -> int:
    """Parse ``mm:ss``, ``hh:mm:ss`` or a number of seconds into seconds.

    Unparseable or missing values yield ``0``.
    """
    try:
        if value and ":" in value:
            parts = value.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return int(float(value or 0))
    except (ValueError, TypeError):
        return 0


def parse_cookie_error(error_output: str) -> str:
    """Parse cookie-related errors and return a user-friendly message."""
    error_lower = error_output.lower()

    if "could not find" in error_lower or "not found" in error_lower:
        for browser in COOKIE_BROWSER_NAMES:
            if browser in error_lower:
                return f"{browser.capitalize()} cookies not found - is {browser.capitalize()} installed?"
        return "Browser cookies not found"

    for keywords, message in COOKIE_ERROR_PATTERNS:
        if any(kw in error_lower for kw in keywords):
            return message

    return "Cookie authentication failed"


def parse_yt_dlp_error(error_output: str) -> str:
    """Parse yt-dlp error output and return a user-friendly message."""
    if not error_output:
        return "Download failed"
    error_lower = error_output.lower()
    if "地域" in error_output or "region" in error_lower:
        return "Video not available in your region"
    if "cookies" in error_lower or "cookie" in error_lower:
        return parse_cookie_error(error_output)
    for keywords, message in ERROR_PATTERNS:
        if any(kw in error_lower for kw in keywords):
            return message
    return "Download failed"


def is_cookie_error(error_output: str) -> bool:
    """Check if error output indicates a cookie/auth problem."""
    lower = error_output.lower()
    return any(kw in lower for kw in COOKIE_ERROR_KEYWORDS)


def normalize_playlist_url(url: str) -> str:
    """Normalize YouTube watch URLs carrying a list param to playlist URLs.

    Non-YouTube URLs are returned unchanged.
    """
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        query = parse_qs(parsed.query)
        if "list" in query and not (
            parsed.path.startswith("/playlist") or parsed.path.startswith("/music/playlist")
        ):
            return f"https://www.youtube.com/playlist?list={query['list'][0]}"
    return url
