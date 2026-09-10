"""Color definitions for YouMuDow themes.

Neutral dark/light palette with indigo accent.
All colors pass WCAG AA contrast against their intended backgrounds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    """Color palette for YouMuDow."""

    PRIMARY: str
    SECONDARY: str
    ACCENT: str
    BACKGROUND: str
    SURFACE: str
    TEXT: str
    TEXT_SECONDARY: str
    BORDER: str
    SUCCESS: str
    WARNING: str
    ERROR: str
    DOWNLOADING: str
    QUEUED: str
    DONE: str
    SELECTION: str
    HOVER: str
    DISABLED: str


DARK_COLORS = Colors(
    PRIMARY="#6366F1",
    SECONDARY="#818CF8",
    ACCENT="#A78BFA",
    BACKGROUND="#111113",
    SURFACE="#1C1C1E",
    TEXT="#EDEDEF",
    TEXT_SECONDARY="#8E8E93",
    BORDER="#2C2C2E",
    SUCCESS="#30D158",
    WARNING="#FFD60A",
    ERROR="#FF453A",
    DOWNLOADING="#0A84FF",
    QUEUED="#FF9F0A",
    DONE="#30D158",
    SELECTION="#3730A3",
    HOVER="#2C2C2E",
    DISABLED="#48484A",
)


LIGHT_COLORS = Colors(
    PRIMARY="#6366F1",
    SECONDARY="#5856D6",
    ACCENT="#5856D6",
    BACKGROUND="#F2F2F7",
    SURFACE="#FFFFFF",
    TEXT="#1C1C1E",
    TEXT_SECONDARY="#8E8E93",
    BORDER="#D1D1D6",
    SUCCESS="#34C759",
    WARNING="#FF9500",
    ERROR="#FF3B30",
    DOWNLOADING="#007AFF",
    QUEUED="#FF9500",
    DONE="#34C759",
    SELECTION="#E8E8FF",
    HOVER="#E5E5EA",
    DISABLED="#C7C7CC",
)
