"""HistoryService backed by the SQLite library store."""

from youmudow.domain.models import Video
from youmudow.services.history_service import HistoryService
from youmudow.services.library_store import LibraryStore


def _service(tmp_path):
    store = LibraryStore(tmp_path / "lib.db")
    return HistoryService(store=store), store


def test_add_persists_to_the_store(tmp_path):
    service, store = _service(tmp_path)
    service.add(Video(title="Song", url="https://x.test/1", uploader="Chan"), "/m/a.mp3", "mp3", 99)
    assert len(store.history()) == 1
    assert service.get_all()[0].title == "Song"
    store.close()


def test_search_and_remove_work_through_the_store(tmp_path):
    service, store = _service(tmp_path)
    service.add(Video(title="Lofi", url="https://x.test/1", uploader="Chan"), "/m/a.mp3", "mp3")
    service.add(Video(title="Rock", url="https://x.test/2", uploader="Band"), "/m/b.mp3", "mp3")

    assert [e.title for e in service.search("lofi")] == ["Lofi"]
    first = service.get_all()[0]
    service.remove(first)
    assert [e.title for e in service.get_all()] == ["Lofi"]
    service.clear()
    assert service.get_all() == []
    store.close()


def test_service_does_not_touch_json_when_a_store_is_given(tmp_path, monkeypatch):
    legacy = tmp_path / "history.json"
    monkeypatch.setattr("youmudow.services.history_service.HISTORY_FILE", legacy)
    service, store = _service(tmp_path)
    service.add(Video(title="Song", url="https://x.test/1"), "/m/a.mp3", "mp3")
    assert not legacy.exists()
    store.close()
