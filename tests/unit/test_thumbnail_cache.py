"""Tests for the thumbnail cache."""

from youmudow.services.thumbnail_cache import ThumbnailCache


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
