"""Color definitions for YouMuDow themes."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Colors:
    """Color palette for YouMuDow."""

    PRIMARY: str
    SECONDARY: str
    ACCENT: str
    BACKGROUND: str
    FOREGROUND: str
    TEXT: str
    TEXT_SECONDARY: str
    BORDER: str
    SUCCESS: str
    WARNING: str
    ERROR: str
    SELECTION: str
    HOVER: str
    DISABLED: str


LIGHT_COLORS = Colors(
    PRIMARY="#2196F3",
    SECONDARY="#64B5F6",
    ACCENT="#FF5722",
    BACKGROUND="#FFFFFF",
    FOREGROUND="#F5F5F5",
    TEXT="#212121",
    TEXT_SECONDARY="#757575",
    BORDER="#E0E0E0",
    SUCCESS="#4CAF50",
    WARNING="#FFC107",
    ERROR="#F44336",
    SELECTION="#BBDEFB",
    HOVER="#E3F2FD",
    DISABLED="#BDBDBD",
)


DARK_COLORS = Colors(
    PRIMARY="#1976D2",
    SECONDARY="#42A5F5",
    ACCENT="#FF7043",
    BACKGROUND="#212121",
    FOREGROUND="#303030",
    TEXT="#FFFFFF",
    TEXT_SECONDARY="#B0B0B0",
    BORDER="#424242",
    SUCCESS="#66BB6A",
    WARNING="#FFD54F",
    ERROR="#EF5350",
    SELECTION="#1565C0",
    HOVER="#303030",
    DISABLED="#616161",
)
