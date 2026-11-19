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


def test_write_atomic_survives_a_directory_that_cannot_be_fsynced(tmp_path, monkeypatch):
    import os as os_module

    real_open = os_module.open

    def fake_open(path, flags, *a, **kw):
        if str(path) == str(tmp_path):
            raise OSError("no directory fsync here")
        return real_open(path, flags, *a, **kw)

    monkeypatch.setattr(os_module, "open", fake_open)
    target = tmp_path / "config.json"
    write_atomic(target, "{}")
    assert target.read_text(encoding="utf-8") == "{}"


def test_backup_corrupt_returns_none_when_the_file_cannot_be_moved(tmp_path, monkeypatch):
    import os as os_module

    target = tmp_path / "config.json"
    target.write_text("{bad", encoding="utf-8")
    monkeypatch.setattr(
        os_module, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("locked"))
    )
    assert backup_corrupt(target) is None
