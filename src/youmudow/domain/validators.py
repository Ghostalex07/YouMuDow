"""Input validation utilities."""

import re

YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.|m\.|music\.)?youtube\.com/watch\?v=[\w-]+",
    r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
    r"(?:https?://)?(?:www\.|m\.)?youtube\.com/shorts/[\w-]+",
    r"(?:https?://)?(?:www\.|music\.)?youtube\.com/playlist\?list=[\w-]+",
]

YOUTUBE_REGEX = re.compile("|".join(YOUTUBE_PATTERNS), re.IGNORECASE)

PLAYLIST_PATTERN = r"(?:https?://)?(?:www\.|music\.)?youtube\.com/playlist\?list=[\w-]+"
PLAYLIST_REGEX = re.compile(PLAYLIST_PATTERN, re.IGNORECASE)

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

MAX_FILENAME_LENGTH = 200

AUDIO_FORMATS: frozenset[str] = frozenset({"mp3", "m4a", "opus", "ogg", "flac", "wav", "aac"})
VIDEO_FORMATS: frozenset[str] = frozenset({"mp4"})
SUPPORTED_FORMATS: frozenset[str] = AUDIO_FORMATS | VIDEO_FORMATS

AUDIO_QUALITIES: frozenset[str] = frozenset(
    {"64kbps", "96kbps", "128kbps", "192kbps", "256kbps", "320kbps"}
)
VIDEO_QUALITIES: frozenset[str] = frozenset({"360p", "480p", "720p", "1080p"})
SUPPORTED_QUALITIES: frozenset[str] = AUDIO_QUALITIES | VIDEO_QUALITIES | {"best"}


def is_valid_format(file_format: str | None) -> bool:
    """True when the format is one this application can hand to yt-dlp."""
    return file_format in SUPPORTED_FORMATS


def is_valid_quality(quality: str | None) -> bool:
    """True when the quality is one of the supported audio/video qualities."""
    return quality in SUPPORTED_QUALITIES


def is_valid_youtube_url(url: str) -> bool:
    """Validate if a string is a valid YouTube URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(YOUTUBE_REGEX.match(url.strip()))


def is_valid_url(url: str) -> bool:
    """Accept any valid http/https URL."""
    url = url.strip()
    return url.startswith(("http://", "https://")) and "." in url


def is_supported_url(url: str) -> bool:
    """True if the URL looks downloadable (not just YouTube)."""
    return is_valid_url(url) and len(url) > 10


def is_playlist_url(url: str) -> bool:
    """Check if URL is a playlist (YouTube, SoundCloud, Bandcamp, etc.)."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if PLAYLIST_REGEX.match(url):
        return True
    # SoundCloud sets
    if re.search(r"(?:https?://)?(?:www\.)?soundcloud\.com/.+/sets/.+", url, re.IGNORECASE):
        return True
    # Bandcamp album
    if re.search(r"(?:https?://)?(?:[\w-]+\.)?bandcamp\.com/album/.+", url, re.IGNORECASE):
        return True
    # Generic /playlist in path
    if re.search(r"/playlist(?:/|\?|$)", url, re.IGNORECASE):
        return True
    # YouTube channel / user
    return bool(
        re.search(
            r"(?:https?://)?(?:www\.)?youtube\.com/(?:@[\w-]+|channel/[\w-]+|c/[\w-]+|user/[\w-]+)/videos",
            url,
            re.IGNORECASE,
        )
    )


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Remove invalid characters from a filename, limit length."""
    if not name:
        return "untitled"
    sanitized = INVALID_FILENAME_CHARS.sub(replacement, name)
    sanitized = sanitized.strip(". ")
    sanitized = sanitized[:MAX_FILENAME_LENGTH]
    return sanitized or "untitled"


def is_valid_rate_limit(rate: str) -> bool:
    """Check if rate limit is valid (e.g., '1M', '500K', '1G').

    Valid formats: number followed by K (kilobytes), M (megabytes), G (gigabytes)
    """
    if not isinstance(rate, str):
        return False
    rate = rate.strip()
    if not rate:
        return True  # Empty is valid (no limit)
    pattern = r"^\d+[KMG]?$"
    return bool(re.match(pattern, rate, re.IGNORECASE))
