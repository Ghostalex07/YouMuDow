"""Tests for the shared atomic persistence helpers."""

import pytest

from youmudow.services.persistence import backup_corrupt, write_atomic


def test_write_atomic_no_tmp_left(tmp_path):
    p = tmp_path / "f.json"
    write_atomic(p, "{}")
    assert p.read_text() == "{}"
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_atomic_keeps_original_on_failure(tmp_path, monkeypatch):
    p = tmp_path / "f.json"
    p.write_text("orig")
    monkeypatch.setattr("os.replace", lambda a, b: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        write_atomic(p, "new")
    assert p.read_text() == "orig"


def test_backup_corrupt_renames(tmp_path):
    p = tmp_path / "f.json"
    p.write_text("bad")
    b = backup_corrupt(p)
    assert b is not None and b.suffix == ".corrupt"
