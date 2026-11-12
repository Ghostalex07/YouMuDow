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
