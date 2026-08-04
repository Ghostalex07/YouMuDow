"""Browser profile detection for YouMuDow.

Discovers installed browsers and their profile directories on the current
platform. Used to hand cookie profiles over to yt-dlp.
"""

import logging
import os
import platform
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SUPPORTED_BROWSERS = ["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi"]


@dataclass
class BrowserProfile:
    """Represents a browser profile."""

    name: str
    path: str
    browser: str


def _get_browser_profile_paths() -> dict[str, list[str]]:
    """Return browser profile paths for the current platform."""
    system = platform.system()

    if system == "Windows":
        local = os.path.expandvars("%LOCALAPPDATA%")
        roaming = os.path.expandvars("%APPDATA%")
        return {
            "chrome": [os.path.join(local, "Google", "Chrome", "User Data")],
            "chromium": [os.path.join(local, "Chromium", "User Data")],
            "firefox": [os.path.join(roaming, "Mozilla", "Firefox", "Profiles")],
            "edge": [os.path.join(local, "Microsoft", "Edge", "User Data")],
            "brave": [os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data")],
            "opera": [os.path.join(roaming, "Opera Software", "Opera Stable")],
            "vivaldi": [os.path.join(local, "Vivaldi", "User Data")],
        }
    if system == "Darwin":
        home = os.path.expanduser("~")
        app_support = os.path.join(home, "Library", "Application Support")
        return {
            "chrome": [os.path.join(app_support, "Google", "Chrome")],
            "chromium": [os.path.join(app_support, "Chromium")],
            "firefox": [
                os.path.join(home, "Library", "Application Support", "Firefox", "Profiles")
            ],
            "edge": [os.path.join(app_support, "Microsoft Edge")],
            "brave": [os.path.join(app_support, "BraveSoftware", "Brave-Browser")],
            "opera": [os.path.join(app_support, "com.operasoftware.Opera")],
            "vivaldi": [os.path.join(app_support, "Vivaldi")],
        }
    return {
        "chrome": ["~/.config/google-chrome", "~/.config/google-chrome-stable"],
        "chromium": ["~/.config/chromium"],
        "firefox": ["~/.mozilla/firefox", "~/.librewolf"],
        "edge": ["~/.config/microsoft-edge"],
        "brave": [
            "~/.config/Brave-Browser",
            "~/.config/Brave-Browser-Beta",
            "~/.config/Brave-Browser-Dev",
        ],
        "opera": ["~/.config/opera", "~/.config/opera-developer"],
        "vivaldi": ["~/.config/vivaldi", "~/.config/vivaldi-snapshot"],
    }


def _expand(path: str) -> str:
    """Expand user shortcuts only on POSIX systems."""
    if platform.system() == "Linux":
        return os.path.expanduser(path)
    return path


def get_all_browser_profiles() -> dict[str, list[BrowserProfile]]:
    """Get all available browser profiles.

    Returns:
        Dict mapping browser name to list of BrowserProfile objects
    """
    browser_paths = _get_browser_profile_paths()
    result: dict[str, list[BrowserProfile]] = {}

    for browser, paths in browser_paths.items():
        profiles: list[BrowserProfile] = []
        for raw_path in paths:
            expanded = _expand(raw_path)
            if not os.path.isdir(expanded):
                continue

            if browser == "firefox":
                try:
                    for item in os.listdir(expanded):
                        profile_dir = os.path.join(expanded, item)
                        if os.path.isdir(profile_dir) and not item.startswith("."):
                            profiles.append(
                                BrowserProfile(name=item, path=profile_dir, browser=browser)
                            )
                except OSError as e:
                    logger.debug("Could not list Firefox profiles in %s: %s", expanded, e)
            else:
                base_name = os.path.basename(expanded)
                if base_name.lower() in ["default", "default release"]:
                    profiles.append(BrowserProfile(name="Default", path=expanded, browser=browser))

                try:
                    for item in os.listdir(expanded):
                        item_path = os.path.join(expanded, item)
                        if os.path.isdir(item_path) and item.lower().startswith("profile"):
                            profiles.append(
                                BrowserProfile(name=item, path=item_path, browser=browser)
                            )
                except OSError as e:
                    logger.debug("Could not list profiles in %s: %s", expanded, e)

        if profiles:
            result[browser] = profiles[:5]

    return result


def check_browser_profile(browser: str) -> tuple[bool, str]:
    """Check if a browser profile exists and is accessible.

    Returns:
        (exists, message)
    """
    browser = browser.lower()
    browser_paths = _get_browser_profile_paths()
    paths = browser_paths.get(browser, [])

    for raw_path in paths:
        expanded = _expand(raw_path)
        if os.path.isdir(expanded):
            return True, expanded

    available: list[str] = []
    for br, paths_list in browser_paths.items():
        for p in paths_list:
            if os.path.isdir(_expand(p)):
                available.append(br)
                break

    available_text = ", ".join(available) if available else "none"
    return False, f"Browser not installed or not logged in. Available: {available_text}"


def get_fallback_browser() -> str | None:
    """Return the first installed browser, or None if none is found."""
    for browser in SUPPORTED_BROWSERS:
        exists, _ = check_browser_profile(browser)
        if exists:
            return browser
    return None


_browsers_cache: list[str] | None = None
_browsers_cache_time: float = 0.0
_BROWSERS_CACHE_TTL: float = 30.0


def get_available_browsers() -> list[str]:
    """Return the list of installed browsers, cached briefly."""
    global _browsers_cache, _browsers_cache_time
    now = time.monotonic()
    if _browsers_cache is not None and (now - _browsers_cache_time) < _BROWSERS_CACHE_TTL:
        return list(_browsers_cache)
    browsers = [browser for browser in SUPPORTED_BROWSERS if check_browser_profile(browser)[0]]
    _browsers_cache = browsers
    _browsers_cache_time = now
    return list(browsers)


def invalidate_browsers_cache() -> None:
    """Drop the cached browser list (used when profiles may have changed)."""
    global _browsers_cache
    _browsers_cache = None
