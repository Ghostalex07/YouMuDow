"""Input validation utilities."""

import re
from pathlib import Path


YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+",
]

YOUTUBE_REGEX = re.compile("|".join(YOUTUBE_PATTERNS), re.IGNORECASE)

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def is_valid_youtube_url(url: str) -> bool:
    """Validate if a string is a valid YouTube URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(YOUTUBE_REGEX.match(url.strip()))


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Remove invalid characters from a filename."""
    if not name:
        return "untitled"
    sanitized = INVALID_FILENAME_CHARS.sub(replacement, name)
    sanitized = sanitized.strip(". ")
    return sanitized or "untitled"


def is_valid_format(fmt: str) -> bool:
    """Check if the format is supported."""
    if not fmt or not isinstance(fmt, str):
        return False
    valid_formats = {"mp3", "mp4", "wav", "flac", "aac", "m4a", "ogg"}
    return fmt.lower() in valid_formats
