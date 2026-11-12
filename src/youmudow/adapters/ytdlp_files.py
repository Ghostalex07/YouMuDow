"""Destination and output-file resolution for yt-dlp downloads.

yt-dlp's output template keeps whatever already exists in the output
directory, so a run's own result is identified by comparing the directory
against a snapshot taken before the run started. These helpers do that
comparison; nothing here spawns processes.
"""

from __future__ import annotations

from pathlib import Path


def existing_files(output_path: Path) -> set[Path]:
    """Return the set of regular files currently present in a directory."""
    try:
        return {path for path in output_path.glob("*") if path.is_file()}
    except OSError:
        return set()


def resolve_output_file(
    output_path: Path,
    safe_title: str,
    preexisting: set[Path],
) -> Path | None:
    """Resolve the file created by this download run.

    Only files that did not exist before the download started are
    considered, so a pre-existing file is never mistaken for the newly
    downloaded one (regardless of mtime). Files whose stem matches the
    sanitized title win; otherwise the newest new file is returned.
    """
    try:
        new_files = [
            path for path in output_path.glob("*") if path.is_file() and path not in preexisting
        ]
    except OSError:
        return None

    candidates = new_files
    title_matches = [p for p in new_files if p.stem == safe_title]
    if title_matches:
        candidates = title_matches
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def resolve_destination(
    destinations: list[str],
    output_path: Path,
    safe_title: str,
    preexisting: set[Path],
    already_downloaded: list[str] | None = None,
    captured: Path | None = None,
) -> Path | None:
    """Resolve the file created by this run, never a pre-existing one.

    Per-call ``destinations`` (parsed from yt-dlp output) are authoritative;
    only a destination that did not exist before the run counts. A file
    reported via the "has already been downloaded" line is accepted even if
    pre-existing, because yt-dlp explicitly attributes it to this run. Then
    ``captured`` (the last destination reported to the caller) is tried, and
    finally a glob for newly created files.
    """
    for raw in destinations:
        candidate = Path(raw)
        if candidate.is_file() and candidate not in preexisting:
            return candidate
    for raw in already_downloaded or []:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    if captured is not None and captured.is_file() and captured not in preexisting:
        return captured
    return resolve_output_file(output_path, safe_title, preexisting)
