from conftest import pump

from youmudow.domain.models import Video

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLPAGES"


def _make_page(count, offset=0):
    return [
        Video(title=f"P{i}", url=f"https://example.com/p{i}") for i in range(offset, offset + count)
    ]


def test_load_more_appends_the_next_page(stack):
    stack.adapter.playlist = _make_page(5)
    stack.config.set("playlist_limit", 2)

    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 2)
    assert stack.window._playlist_has_more is True

    stack.window._load_more_playlist()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 4)

    titles = [v.title for v in stack.window._results_cards.playlist_videos]
    assert titles == ["P0", "P1", "P2", "P3"]
    assert stack.window._is_searching is False


def test_load_more_stops_when_the_playlist_is_exhausted(stack):
    stack.adapter.playlist = _make_page(3)
    stack.config.set("playlist_limit", 2)

    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 2)

    stack.window._load_more_playlist()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 3)

    assert stack.window._playlist_has_more is False
    stack.window._load_more_playlist()  # a no-op once exhausted
    assert stack.window._results_cards.card_count() == 3


def test_a_new_search_resets_the_pagination(stack):
    stack.adapter.playlist = _make_page(4)
    stack.config.set("playlist_limit", 2)

    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 2)
    stack.window._load_more_playlist()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 4)

    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 2)
    assert [v.title for v in stack.window._results_cards.playlist_videos] == ["P0", "P1"]
