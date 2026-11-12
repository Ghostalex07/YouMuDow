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
