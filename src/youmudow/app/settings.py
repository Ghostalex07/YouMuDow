"""Typed schema for the JSON settings file.

Every value read from disk is coerced to the type its default declares, so a
hand-edited config with ``"max_retries": "3"`` behaves like ``3`` instead of
breaking an ``int()`` call deep inside the app.
"""

import copy
import platform
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypedDict


class Settings(TypedDict):
    window_geometry: str
    output_path: str
    format: str
    quality: str
    subtitles: bool
    subtitle_lang: str
    embed_subtitles: bool
    use_cookies: bool
    cookies_source: str
    cookies_file: str
    browser: str
    profile: str
    rate_limit: str
    split_chapters: bool
    debug_mode: bool
    options_panel_open: bool
    theme: str
    minimize_to_tray: bool
    concurrent_downloads: int
    max_retries: int
    language: str
    check_for_updates: bool
    playlist_limit: int
    search_history: list[str]


DEFAULT_SETTINGS: Settings = {
    "window_geometry": "",
    "output_path": str(
        Path.home() / "Music" / "YouMuDow"
        if platform.system() != "Windows"
        else Path.home() / "Desktop" / "YouMuDow"
    ),
    "format": "mp3",
    "quality": "best",
    "subtitles": False,
    "subtitle_lang": "en",
    "embed_subtitles": False,
    "use_cookies": False,
    "cookies_source": "browser",
    "cookies_file": "",
    "browser": "chrome",
    "profile": "Default",
    "rate_limit": "",
    "split_chapters": False,
    "debug_mode": False,
    "options_panel_open": False,
    "theme": "dark",
    "minimize_to_tray": False,
    "concurrent_downloads": 1,
    "max_retries": 2,
    "language": "auto",
    "check_for_updates": True,
    "playlist_limit": 50,
    "search_history": [],
}

_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off", ""})
_MISSING = object()


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
    return default


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str) -> str:
    return default if value is None else str(value)


def _coerce_history(value: Any, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    entries: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            entries.append(text)
    return entries


_COERCERS: dict[type, Callable[[Any, Any], Any]] = {
    bool: _coerce_bool,
    int: _coerce_int,
    str: _coerce_str,
    list: _coerce_history,
}


def coerce_setting(key: str, value: Any) -> Any:
    """Return ``value`` as the type ``key`` declares, or the default on junk."""
    default = DEFAULT_SETTINGS.get(key, _MISSING)
    if default is _MISSING:
        return value
    coercer = _COERCERS[type(default)]
    return coercer(value, default)


def normalize_settings(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Defaults plus the stored values, each coerced to its declared type.

    Unknown keys are preserved: a newer version of the app may have written
    them, and dropping them would silently lose the user's choices.
    """
    data: dict[str, Any] = {key: copy.deepcopy(value) for key, value in raw.items()}
    for key, default in DEFAULT_SETTINGS.items():
        data[key] = coerce_setting(key, raw.get(key, copy.deepcopy(default)))
    return data
