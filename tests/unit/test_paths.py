"""Tests for filesystem path helpers."""

from pathlib import Path

from youmudow.paths import cache_dir


def test_cache_dir_honors_xdg(monkeypatch, tmp_path):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert cache_dir() == tmp_path / "youmudow"


def test_cache_dir_defaults_to_dot_cache(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    assert cache_dir() == Path.home() / ".cache" / "youmudow"


def test_cache_dir_windows(monkeypatch, tmp_path):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cache_dir() == tmp_path / "YouMuDow" / "cache"


def test_portable_mode_moves_every_path_next_to_the_executable(monkeypatch, tmp_path):
    import sys

    from youmudow import paths

    monkeypatch.setattr(sys, "executable", str(tmp_path / "YouMuDow"))
    monkeypatch.setenv(paths.PORTABLE_ENV, "1")

    root = tmp_path / "data"
    assert paths.config_dir() == root / "config"
    assert paths.database_file() == root / "config" / "youmudow.db"
    assert paths.queue_file() == root / "config" / "queue.json"
    assert paths.cache_dir() == root / "cache"


def test_the_marker_file_enables_portable_mode(monkeypatch, tmp_path):
    import sys

    from youmudow import paths

    monkeypatch.delenv(paths.PORTABLE_ENV, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "YouMuDow"))
    (tmp_path / paths.PORTABLE_MARKER).write_text("", encoding="utf-8")

    assert paths.config_dir() == tmp_path / "data" / "config"
