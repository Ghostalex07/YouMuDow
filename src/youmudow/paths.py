"""Filesystem paths shared across application layers."""

import os
import platform
import sys
from pathlib import Path

PORTABLE_ENV = "YMD_PORTABLE"
PORTABLE_MARKER = "youmudow.portable"
_PORTABLE_VALUES = {"1", "true", "yes", "on"}


def portable_root() -> Path | None:
    """Return the data directory for a portable run, or None.

    Portable mode keeps config, database, cache and logs next to the executable
    so the whole app can live on a USB stick. It is enabled by ``YMD_PORTABLE``
    or by a ``youmudow.portable`` marker beside the executable.
    """
    flag = os.environ.get(PORTABLE_ENV, "").strip().lower()
    if flag in _PORTABLE_VALUES:
        return Path(sys.executable).resolve().parent / "data"
    marker = Path(sys.executable).resolve().parent / PORTABLE_MARKER
    if marker.is_file():
        return marker.parent / "data"
    return None


def config_dir() -> Path:
    """Return the platform-specific user configuration directory."""
    portable = portable_root()
    if portable is not None:
        return portable / "config"
    if platform.system() == "Windows":
        return Path.home() / "AppData" / "Local" / "YouMuDow"
    return Path.home() / ".config" / "youmudow"


def queue_file() -> Path:
    """Return the path of the persisted pending download queue."""
    return config_dir() / "queue.json"


def database_file() -> Path:
    """Return the path of the SQLite library (history and subscriptions)."""
    return config_dir() / "youmudow.db"


def cache_dir() -> Path:
    """Return the platform-specific cache directory.

    Honors ``XDG_CACHE_HOME`` on Linux/macOS and ``LOCALAPPDATA`` on Windows,
    falling back to their conventional defaults.
    """
    portable = portable_root()
    if portable is not None:
        return portable / "cache"
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "YouMuDow" / "cache"
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "youmudow"
