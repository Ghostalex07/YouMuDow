"""Tests for the async thumbnail loader and photoimage helper."""

import threading
import time
import tkinter as tk

import pytest

from youmudow.services.thumbnail_cache import ThumbnailCache
from youmudow.services.thumbnail_loader import ThumbnailLoader
from youmudow.services.thumbnail_service import ThumbnailService
from youmudow.ui.widgets.components.thumbnail import photoimage_from_bytes


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


def _wait_for(root, predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        root.update()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_loader_uses_cache_when_present(root, tmp_path):
    cache = ThumbnailCache(tmp_path)
    cache.put("vid12345678", b"jpgdata")
    results = {}
    loader = ThumbnailLoader(root, cache, ThumbnailService())
    try:
        loader.request(
            "https://youtu.be/vid12345678",
            lambda url, data: results.setdefault(url, data),
        )
        assert _wait_for(root, lambda: "https://youtu.be/vid12345678" in results)
    finally:
        loader.shutdown()
    assert results["https://youtu.be/vid12345678"] == b"jpgdata"


def test_stale_request_does_not_overwrite(root, tmp_path, monkeypatch):
    import youmudow.services.thumbnail_loader as loader_mod

    cache = ThumbnailCache(tmp_path)
    results = {}
    started = threading.Event()
    release = threading.Event()

    def fake_urlopen(url, timeout=None):
        if "aaaaaaaaaaa" in url:
            started.set()
            release.wait(timeout=3.0)
            return _FakeResponse(b"slow")
        return _FakeResponse(b"fast")

    monkeypatch.setattr(loader_mod, "urlopen", fake_urlopen)
    loader = ThumbnailLoader(root, cache, ThumbnailService())
    try:
        loader.request(
            "https://youtu.be/aaaaaaaaaaa",
            lambda url, data: results.setdefault(url, data),
        )
        assert started.wait(timeout=3.0)
        loader.request(
            "https://youtu.be/bbbbbbbbbbb",
            lambda url, data: results.setdefault(url, data),
        )
        release.set()
        assert _wait_for(root, lambda: "https://youtu.be/bbbbbbbbbbb" in results)
    finally:
        loader.shutdown()
    assert results["https://youtu.be/bbbbbbbbbbb"] == b"fast"
    assert "https://youtu.be/aaaaaaaaaaa" not in results


def test_photoimage_from_bytes_valid(root):
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (20, 20), "red").save(buf, format="PNG")
    photo = photoimage_from_bytes(buf.getvalue(), 10, 10)
    assert photo is not None
    assert photo.width() <= 10
    assert photo.height() <= 10


def test_photoimage_from_bytes_invalid(root):
    assert photoimage_from_bytes(b"not an image", 10, 10) is None
