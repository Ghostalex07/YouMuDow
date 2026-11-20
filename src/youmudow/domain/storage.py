"""Free-space checks before starting a download."""

import shutil
from pathlib import Path

# Beyond the estimated file size, yt-dlp writes a temporary container first, so
# a download that exactly fits would still fail.
SPACE_MARGIN_BYTES = 64 * 1024 * 1024


def free_bytes(path: Path) -> int | None:
    """Free space on the volume holding ``path``, or None when unknowable."""
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None


def has_room_for(path: Path, needed_bytes: int) -> bool:
    """True when ``path`` can take ``needed_bytes`` plus the safety margin."""
    free = free_bytes(path)
    if free is None:
        return True  # cannot measure: never block the user on a guess
    return free >= needed_bytes + SPACE_MARGIN_BYTES
