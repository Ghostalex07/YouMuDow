"""Filesystem paths shared across application layers."""

import platform
from pathlib import Path


def config_dir() -> Path:
    """Return the platform-specific user configuration directory."""
    if platform.system() == "Windows":
        return Path.home() / "AppData" / "Local" / "YouMuDow"
    return Path.home() / ".config" / "youmudow"
