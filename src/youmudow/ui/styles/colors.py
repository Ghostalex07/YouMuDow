"""Color definitions for YouMuDow themes.

Modern dark theme with accent colors for a polished look.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    """Modern color palette for YouMuDow."""

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
    ACCENT="#F472B6",
    BACKGROUND="#0F0F0F",
    SURFACE="#1A1A2E",
    TEXT="#E4E4E7",
    TEXT_SECONDARY="#71717A",
    BORDER="#27272A",
    SUCCESS="#22C55E",
    WARNING="#EAB308",
    ERROR="#EF4444",
    DOWNLOADING="#3B82F6",
    QUEUED="#F59E0B",
    DONE="#22C55E",
    SELECTION="#3730A3",
    HOVER="#27272A",
    DISABLED="#3F3F46",
)


LIGHT_COLORS = Colors(
    PRIMARY="#6366F1",
    SECONDARY="#818CF8",
    ACCENT="#EC4899",
    BACKGROUND="#FAFAFA",
    SURFACE="#FFFFFF",
    TEXT="#18181B",
    TEXT_SECONDARY="#71717A",
    BORDER="#E4E4E7",
    SUCCESS="#22C55E",
    WARNING="#EAB308",
    ERROR="#EF4444",
    DOWNLOADING="#3B82F6",
    QUEUED="#F59E0B",
    DONE="#22C55E",
    SELECTION="#EEF2FF",
    HOVER="#F4F4F5",
    DISABLED="#D4D4D8",
)
