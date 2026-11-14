"""Tests for the thumbnail cache."""

import os

from youmudow.services.thumbnail_cache import ThumbnailCache


def _disk_bytes(path):
    return sum(p.stat().st_size for p in path.glob("*.jpg"))


def test_cache_roundtrip(tmp_path):
    c = ThumbnailCache(tmp_path)
    c.put("abc12345678", b"data")
    assert c.get("abc12345678") == b"data"


def test_cache_miss_returns_none(tmp_path):
    assert ThumbnailCache(tmp_path).get("missing") is None


def test_lru_eviction(tmp_path):
    c = ThumbnailCache(tmp_path, max_entries=3)
    for i in range(6):
        c.put(f"vid{i}", bytes([i]))
    assert len(list(tmp_path.glob("*.jpg"))) <= 3


def test_clear_removes_files_and_memory(tmp_path):
    c = ThumbnailCache(tmp_path)
    c.put("abc12345678", b"data")
    assert list(tmp_path.glob("*.jpg"))
    c.clear()
    assert list(tmp_path.glob("*.jpg")) == []
    assert c.get("abc12345678") is None


def test_fresh_instance_reads_from_disk(tmp_path):
    ThumbnailCache(tmp_path).put("abc12345678", b"data")
    assert ThumbnailCache(tmp_path).get("abc12345678") == b"data"


def test_byte_cap_evicts_oldest_entries(tmp_path):
    c = ThumbnailCache(tmp_path, max_bytes=10)
    for i in range(5):
        c.put(f"vid{i}", b"x" * 4)
    assert _disk_bytes(tmp_path) <= 10
    assert c.get("vid4") == b"x" * 4
    assert c.get("vid0") is None


def test_single_entry_larger_than_cap_is_kept(tmp_path):
    c = ThumbnailCache(tmp_path, max_bytes=4)
    c.put("big", b"x" * 100)
    assert c.get("big") == b"x" * 100
    assert _disk_bytes(tmp_path) == 100


def test_startup_trim_respects_byte_cap(tmp_path):
    for i in range(3):
        path = tmp_path / f"old{i}.jpg"
        path.write_bytes(b"x" * 6)
        os.utime(path, (1_600_000_000 + i, 1_600_000_000 + i))
    c = ThumbnailCache(tmp_path, max_bytes=12)
    assert c.get("old0") is None
    assert c.get("old2") == b"x" * 6
    assert _disk_bytes(tmp_path) <= 12


def test_zero_max_bytes_disables_byte_cap(tmp_path):
    c = ThumbnailCache(tmp_path, max_bytes=0)
    c.put("big", b"x" * 4096)
    assert c.get("big") == b"x" * 4096
