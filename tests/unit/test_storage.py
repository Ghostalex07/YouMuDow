"""Tests for the free-space helpers."""

from pathlib import Path
from unittest.mock import patch

from youmudow.domain.storage import SPACE_MARGIN_BYTES, free_bytes, has_room_for


def test_free_bytes_reports_a_number(tmp_path):
    assert isinstance(free_bytes(tmp_path), int)


def test_missing_folder_walks_up_to_an_existing_parent(tmp_path):
    assert free_bytes(tmp_path / "not" / "created" / "yet") is not None


def test_unknown_usage_never_blocks_a_download(tmp_path):
    with patch("youmudow.domain.storage.shutil.disk_usage", side_effect=OSError):
        assert free_bytes(tmp_path) is None
        assert has_room_for(tmp_path, 10**12) is True


def test_has_room_compares_against_the_margin(tmp_path):
    with patch("youmudow.domain.storage.free_bytes", return_value=1000):
        assert has_room_for(tmp_path, 10) is False
        assert has_room_for(Path("/tmp"), 1000 - SPACE_MARGIN_BYTES) is True
