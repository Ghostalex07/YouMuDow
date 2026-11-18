"""Named download presets for the options panel.

Data only: the panel decides how to apply them, and cookies, output path and
rate limit are deliberately left untouched so a preset never changes auth.
"""

from dataclasses import dataclass

from youmudow.domain.models import DownloadOptions


@dataclass(frozen=True)
class Preset:
    """A named bundle of download options."""

    name: str
    options: DownloadOptions


PRESETS: tuple[Preset, ...] = (
    Preset("Music 320", DownloadOptions(file_format="mp3", quality="320kbps")),
    Preset("Video 1080", DownloadOptions(file_format="mp4", quality="1080p")),
    Preset("Archive FLAC", DownloadOptions(file_format="flac", quality="best")),
)


def find_preset(name: str) -> Preset | None:
    """Return the preset with this name, or None when it is not one of ours."""
    for preset in PRESETS:
        if preset.name == name:
            return preset
    return None
