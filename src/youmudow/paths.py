"""Filesystem paths shared across application layers."""

import os
import platform
from pathlib import Path


def config_dir() -> Path:
    """Return the platform-specific user configuration directory."""
    if platform.system() == "Windows":
        return Path.home() / "AppData" / "Local" / "YouMuDow"
    return Path.home() / ".config" / "youmudow"


def cache_dir() -> Path:
    """Return the platform-specific cache directory.

    Honors ``XDG_CACHE_HOME`` on Linux/macOS and ``LOCALAPPDATA`` on Windows,
    falling back to their conventional defaults.
    """
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "YouMuDow" / "cache"
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "youmudow"
