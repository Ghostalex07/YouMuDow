from conftest import pump

from youmudow.domain.models import Video

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL123"


def test_playlist_url_marks_the_results_as_a_playlist(stack):
    stack.adapter.playlist = [
        Video(title="P1", url="https://example.com/p1"),
        Video(title="P2", url="https://example.com/p2"),
    ]
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 2)
    assert stack.window._results_cards.is_playlist is True


def test_add_all_enqueues_every_playlist_entry(stack):
    videos = [Video(title=f"P{i}", url=f"https://example.com/p{i}") for i in range(3)]
    stack.adapter.playlist = videos
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: len(stack.window._results_cards.playlist_videos) == 3)
    stack.window._detail_panel._add_all_to_queue()
    assert len(stack.controller.state.get_queue()) == 3


def test_playlist_fetch_failure_recovers_the_ui(stack, monkeypatch):
    def explode(url, limit=50):
        raise RuntimeError("private playlist")

    monkeypatch.setattr(stack.adapter, "get_playlist_videos", explode)
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._is_searching is False, timeout=2.0)
    assert stack.window._results_cards.card_count() == 0
    assert "playlist" in stack.window._status_bar._status_var.get().lower()
