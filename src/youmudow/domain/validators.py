"""Input validation utilities."""

import os
import platform as _platform
import re
from dataclasses import dataclass
from pathlib import Path


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

SUPPORTED_BROWSERS = ["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi"]


def is_valid_youtube_url(url: str) -> bool:
    """Validate if a string is a valid YouTube URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(YOUTUBE_REGEX.match(url.strip()))


def is_playlist_url(url: str) -> bool:
    """Check if URL is a YouTube playlist."""
    if not url or not isinstance(url, str):
        return False
    return bool(PLAYLIST_REGEX.match(url.strip()))


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Remove invalid characters from a filename, limit length."""
    if not name:
        return "untitled"
    sanitized = INVALID_FILENAME_CHARS.sub(replacement, name)
    sanitized = sanitized.strip(". ")
    sanitized = sanitized[:MAX_FILENAME_LENGTH]
    return sanitized or "untitled"


def get_unique_filename(directory: Path, filename: str, max_attempts: int = 999) -> Path:
    """Get a unique filename by adding (1), (2), etc. if file exists.

    Raises FileExistsError if max_attempts is exceeded.
    """
    directory = Path(directory)
    path = directory / filename

    if not path.exists():
        return path

    name, ext = os.path.splitext(filename)
    for counter in range(1, max_attempts + 1):
        new_path = directory / f"{name} ({counter}){ext}"
        if not new_path.exists():
            return new_path

    raise FileExistsError(
        f"Could not find a unique filename for '{filename}' after {max_attempts} attempts in {directory}"
    )


def validate_format_quality(file_format: str, quality: str) -> tuple[bool, str]:
    """Validate format and quality combination.
    
    Returns:
        (is_valid, warning_message)
    """
    file_format = file_format.lower()
    quality = quality.lower()
    
    audio_formats = {"mp3", "m4a", "opus", "ogg", "flac", "wav"}
    video_qualities = {"1080p", "720p", "480p", "360p"}
    audio_qualities = {"320kbps", "256kbps", "192kbps", "128kbps", "96kbps"}
    
    if file_format in audio_formats and quality in video_qualities:
        return True, f"[WARNING] Video quality '{quality}' not applicable to audio format '{file_format}', using audio quality instead"
    
    if file_format == "mp4" and quality in audio_qualities:
        return True, f"[WARNING] Audio quality '{quality}' not applicable to video format 'mp4', using best video"
    
    return True, ""


def parse_yt_dlp_error(error_output: str) -> str:
    """Parse yt-dlp error output to return user-friendly message."""
    error_lower = error_output.lower()
    
    if "private video" in error_lower or "video is private" in error_lower:
        return "Video is private"
    if "not available" in error_lower or "unavailable" in error_lower:
        return "Video not available"
    if "removed" in error_lower or "deleted" in error_lower:
        return "Video has been removed"
    if "connection" in error_lower or "network" in error_lower or "http error" in error_lower:
        return "Connection error"
    if "permission denied" in error_lower or "permission" in error_lower:
        return "Permission denied"
    if "auth" in error_lower or "login" in error_lower or "sign in" in error_lower:
        return "Authentication required"
    if "captcha" in error_lower or "verification" in error_lower:
        return "CAPTCHA required"
    if "地域" in error_output or "region" in error_lower:
        return "Video not available in your region"
    if "cookies" in error_lower or "cookie" in error_lower:
        return parse_cookie_error(error_output)
    
    return "Download failed"


def parse_cookie_error(error_output: str) -> str:
    """Parse cookie-related errors and return user-friendly message."""
    error_lower = error_output.lower()
    
    if "locked" in error_lower or "lock" in error_lower:
        return "Cookies locked - browser may be running"
    if "could not find" in error_lower or "not found" in error_lower:
        if "chrome" in error_lower:
            return "Chrome cookies not found - is Chrome installed?"
        if "firefox" in error_lower:
            return "Firefox cookies not found - is Firefox installed?"
        if "edge" in error_lower:
            return "Edge cookies not found - is Edge installed?"
        if "brave" in error_lower:
            return "Brave cookies not found - is Brave installed?"
        return "Browser cookies not found"
    if "profile" in error_lower:
        return "Browser profile not accessible"
    if "database" in error_lower:
        return "Cookies database corrupted or inaccessible"
    if "no such file" in error_lower or "directory" in error_lower:
        return "Browser profile directory not found"
    
    return "Cookie authentication failed"


def _get_browser_profile_paths() -> dict[str, list[str]]:
    """Return browser profile paths for the current platform."""
    system = _platform.system()

    if system == "Windows":
        local = os.path.expandvars("%LOCALAPPDATA%")
        roaming = os.path.expandvars("%APPDATA%")
        return {
            "chrome": [
                os.path.join(local, "Google", "Chrome", "User Data"),
            ],
            "chromium": [
                os.path.join(local, "Chromium", "User Data"),
            ],
            "firefox": [
                os.path.join(roaming, "Mozilla", "Firefox", "Profiles"),
            ],
            "edge": [
                os.path.join(local, "Microsoft", "Edge", "User Data"),
            ],
            "brave": [
                os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
            ],
            "opera": [
                os.path.join(roaming, "Opera Software", "Opera Stable"),
            ],
            "vivaldi": [
                os.path.join(local, "Vivaldi", "User Data"),
            ],
        }
    elif system == "Darwin":
        home = os.path.expanduser("~")
        app_support = os.path.join(home, "Library", "Application Support")
        return {
            "chrome": [
                os.path.join(app_support, "Google", "Chrome"),
            ],
            "chromium": [
                os.path.join(app_support, "Chromium"),
            ],
            "firefox": [
                os.path.join(home, "Library", "Application Support", "Firefox", "Profiles"),
            ],
            "edge": [
                os.path.join(app_support, "Microsoft Edge"),
            ],
            "brave": [
                os.path.join(app_support, "BraveSoftware", "Brave-Browser"),
            ],
            "opera": [
                os.path.join(app_support, "com.operasoftware.Opera"),
            ],
            "vivaldi": [
                os.path.join(app_support, "Vivaldi"),
            ],
        }
    else:
        return {
            "chrome": [
                "~/.config/google-chrome",
                "~/.config/google-chrome-stable",
            ],
            "chromium": [
                "~/.config/chromium",
            ],
            "firefox": [
                "~/.mozilla/firefox",
                "~/.librewolf",
            ],
            "edge": [
                "~/.config/microsoft-edge",
            ],
            "brave": [
                "~/.config/Brave-Browser",
                "~/.config/Brave-Browser-Beta",
                "~/.config/Brave-Browser-Dev",
            ],
            "opera": [
                "~/.config/opera",
                "~/.config/opera-developer",
            ],
            "vivaldi": [
                "~/.config/vivaldi",
                "~/.config/vivaldi-snapshot",
            ],
        }


@dataclass
class BrowserProfile:
    """Represents a browser profile."""
    name: str
    path: str
    browser: str


def get_all_browser_profiles() -> dict[str, list[BrowserProfile]]:
    """Get all available browser profiles.
    
    Returns:
        Dict mapping browser name to list of BrowserProfile objects
    """
    browser_paths = _get_browser_profile_paths()
    result: dict[str, list[BrowserProfile]] = {}
    
    for browser, paths in browser_paths.items():
        profiles = []
        for raw_path in paths:
            expanded = os.path.expanduser(raw_path)
            if not os.path.isdir(expanded):
                continue
            
            if browser == "firefox":
                profile_dirs = []
                try:
                    for item in os.listdir(expanded):
                        profile_dir = os.path.join(expanded, item)
                        if os.path.isdir(profile_dir) and not item.startswith('.'):
                            profile_dirs.append(item)
                except OSError:
                    pass
                
                for pdir in profile_dirs[:5]:
                    profiles.append(BrowserProfile(
                        name=pdir,
                        path=os.path.join(expanded, pdir),
                        browser=browser
                    ))
            else:
                base_name = os.path.basename(expanded)
                if base_name.lower() in ["default", "default release"]:
                    profiles.append(BrowserProfile(
                        name="Default",
                        path=expanded,
                        browser=browser
                    ))
                
                try:
                    for item in os.listdir(expanded):
                        item_path = os.path.join(expanded, item)
                        if os.path.isdir(item_path) and item.lower().startswith("profile"):
                            profiles.append(BrowserProfile(
                                name=item,
                                path=item_path,
                                browser=browser
                            ))
                except OSError:
                    pass
        
        if profiles:
            result[browser] = profiles[:5]
    
    return result


def check_browser_profile(browser: str) -> tuple[bool, str]:
    """Check if browser profile exists and is accessible.
    
    Returns:
        (exists, message)
    """
    browser = browser.lower()
    browser_paths = _get_browser_profile_paths()
    paths = browser_paths.get(browser, [])
    
    for raw_path in paths:
        expanded = os.path.expanduser(raw_path)
        if os.path.isdir(expanded):
            return True, expanded
    
    available = []
    for br, paths_list in browser_paths.items():
        for p in paths_list:
            ep = os.path.expanduser(p)
            if os.path.isdir(ep):
                available.append(br)
                break
    
    return False, f"Browser not installed or not logged in. Available: {', '.join(available) if available else 'none'}"


def get_fallback_browser() -> str | None:
    """On Linux, try to find an available browser if Chrome fails.
    
    Returns:
        Browser name to use, or None if no browser found
    """
    
    for browser in SUPPORTED_BROWSERS:
        exists, _ = check_browser_profile(browser)
        if exists:
            return browser
    
    return None


def get_available_browsers() -> list[str]:
    """Get list of browsers with at least one profile.
    
    Returns:
        List of browser names
    """
    browsers = []
    for browser in SUPPORTED_BROWSERS:
        exists, _ = check_browser_profile(browser)
        if exists:
            browsers.append(browser)
    return browsers


def is_valid_format(fmt: str) -> bool:
    """Check if the format is supported."""
    if not fmt or not isinstance(fmt, str):
        return False
    valid_formats = {"mp3", "mp4", "wav", "flac", "aac", "m4a", "ogg"}
    return fmt.lower() in valid_formats


def is_valid_rate_limit(rate: str) -> bool:
    """Check if rate limit is valid (e.g., '1M', '500K', '1G').
    
    Valid formats: number followed by K (kilobytes), M (megabytes), G (gigabytes)
    """
    if not isinstance(rate, str):
        return False
    rate = rate.strip()
    if not rate:
        return True  # Empty is valid (no limit)
    pattern = r'^\d+[KMG]?$'
    return bool(re.match(pattern, rate, re.IGNORECASE))
