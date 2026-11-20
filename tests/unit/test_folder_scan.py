"""Tests for scanning the output folder."""

from pathlib import Path

from youmudow.services.folder_scan import ScannedFile, find_orphans, media_files


def _touch(path: Path, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_finds_media_files_and_ignores_the_rest(tmp_path):
    _touch(tmp_path / "song.mp3")
    _touch(tmp_path / "clip.MP4")
    _touch(tmp_path / "notes.txt")
    found = media_files(tmp_path)
    assert {item.path.name for item in found} == {"song.mp3", "clip.MP4"}


def test_scans_subfolders(tmp_path):
    _touch(tmp_path / "Channel" / "song.flac")
    assert [item.path.name for item in media_files(tmp_path)] == ["song.flac"]


def test_missing_folder_is_empty(tmp_path):
    assert media_files(tmp_path / "nope") == []


def test_orphans_exclude_known_paths(tmp_path):
    known = _touch(tmp_path / "known.mp3")
    orphan = _touch(tmp_path / "orphan.mp3")
    files = media_files(tmp_path)
    assert [item.path.name for item in find_orphans(files, [str(known)])] == [orphan.name]


def test_size_is_recorded(tmp_path):
    _touch(tmp_path / "song.mp3", b"12345")
    assert media_files(tmp_path)[0] == ScannedFile(path=tmp_path / "song.mp3", size=5)
