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


def test_write_atomic_fsyncs_the_parent_directory(tmp_path, monkeypatch):
    import os

    p = tmp_path / "f.json"
    fsynced: list[int] = []
    real_open = os.open

    def fake_open(path, flags, *args, **kwargs):
        if str(path) == str(tmp_path):
            return 999
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr("os.open", fake_open)
    monkeypatch.setattr("os.fsync", lambda fd: fsynced.append(fd))
    monkeypatch.setattr("os.close", lambda fd: None)

    write_atomic(p, "{}")

    assert 999 in fsynced


def test_backup_corrupt_renames(tmp_path):
    p = tmp_path / "f.json"
    p.write_text("bad")
    b = backup_corrupt(p)
    assert b is not None and b.suffix == ".corrupt"
