"""Find media files in the output folder that the library does not know about."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

MEDIA_EXTENSIONS = frozenset(
    {
        ".aac",
        ".flac",
        ".m4a",
        ".mkv",
        ".mp3",
        ".mp4",
        ".ogg",
        ".opus",
        ".wav",
        ".webm",
    }
)


@dataclass(frozen=True)
class ScannedFile:
    """One media file found on disk."""

    path: Path
    size: int


def media_files(folder: Path, extensions: Iterable[str] = MEDIA_EXTENSIONS) -> list[ScannedFile]:
    """Media files under ``folder``, newest first. Missing folders yield ``[]``."""
    wanted = {ext.lower() for ext in extensions}
    if not folder.is_dir():
        return []
    found: list[ScannedFile] = []
    for path in folder.rglob("*"):
        if path.suffix.lower() not in wanted or not path.is_file():
            continue
        try:
            found.append(ScannedFile(path=path, size=path.stat().st_size))
        except OSError:
            continue
    found.sort(key=lambda item: item.path.stat().st_mtime, reverse=True)
    return found


def find_orphans(files: Iterable[ScannedFile], known_paths: Iterable[str]) -> list[ScannedFile]:
    """Files whose resolved path is not recorded in the library."""
    known = {str(Path(path).resolve()) for path in known_paths}
    return [item for item in files if str(item.path.resolve()) not in known]
