"""Tests for the composition root."""

import json

import pytest

from youmudow.app.config import AppConfig
from youmudow.bootstrap import build_services, open_library_store
from youmudow.services.library_store import LibraryStore


@pytest.fixture
def legacy(tmp_path):
    directory = tmp_path / "cfg"
    directory.mkdir()
    queue = directory / "queue.json"
    queue.write_text("[]", encoding="utf-8")
    return directory, queue


def test_open_library_store_imports_the_legacy_history(tmp_path, legacy):
    directory, queue = legacy
    (directory / "history.json").write_text(
        json.dumps(
            [
                {
                    "title": "Old",
                    "url": "https://x.test/old",
                    "uploader": "U",
                    "file_format": "mp3",
                    "output_path": str(tmp_path / "old.mp3"),
                    "downloaded_at": "2026-01-01T00:00:00+00:00",
                    "file_size_bytes": 10,
                }
            ]
        ),
        encoding="utf-8",
    )

    store = open_library_store(tmp_path / "youmudow.db", legacy_dir=directory, legacy_queue=queue)

    assert store is not None
    assert [entry.title for entry in store.history()] == ["Old"]


def test_open_library_store_returns_none_for_a_corrupt_file(tmp_path, legacy):
    directory, queue = legacy
    broken = tmp_path / "youmudow.db"
    broken.write_bytes(b"not a database at all")

    assert open_library_store(broken, legacy_dir=directory, legacy_queue=queue) is None


def test_open_library_store_returns_none_when_the_folder_is_missing(tmp_path):
    missing = tmp_path / "nope" / "deep"
    result = open_library_store(
        missing / "youmudow.db", legacy_dir=missing, legacy_queue=missing / "queue.json", quiet=True
    )
    assert result is None or isinstance(result, LibraryStore)


def test_build_services_shares_one_store_between_history_and_queue(tmp_path):
    store = LibraryStore(tmp_path / "youmudow.db")

    services = build_services(AppConfig(), library_store=store, open_store=False)

    assert services.library_store is store
    assert services.controller._library_store is store


def test_build_services_can_skip_the_database():
    services = build_services(AppConfig(), open_store=False)
    assert services.library_store is None
