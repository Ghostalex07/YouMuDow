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

    messages = []
    monkeypatch.setattr(stack.adapter, "get_playlist_videos", explode)
    monkeypatch.setattr(stack.window, "_set_status", lambda *a, **k: messages.append(a[0]))
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(
        stack.window,
        lambda: any("playlist" in str(message).lower() for message in messages),
        timeout=2.0,
    )
    assert stack.window._results_cards.card_count() == 0
    assert any("playlist" in str(message).lower() for message in messages)


def test_playlist_previews_the_first_entry(stack):
    from youmudow.domain.formats import FormatInfo

    stack.adapter.playlist = [
        Video(title="PONE", url="https://example.com/p1", duration=60),
    ]
    stack.adapter.formats = [FormatInfo("251", "m4a", 0, 256.0, 0.0, 0)]
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()

    pump(stack.window, lambda: "~" in stack.window._detail_panel._detail_meta.cget("text"))


def test_exporting_a_playlist_writes_an_m3u(stack, tmp_path, monkeypatch):
    stack.adapter.playlist = [
        Video(title="P1", url="https://example.com/p1", duration=90),
        Video(title="P2", url="https://example.com/p2"),
    ]
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: len(stack.window._results_cards.playlist_videos) == 2)

    target = tmp_path / "list.m3u"
    monkeypatch.setattr(
        "youmudow.ui.window_actions.filedialog.asksaveasfilename", lambda **_kw: str(target)
    )
    stack.window._export_playlist()

    text = target.read_text(encoding="utf-8")
    assert text.startswith("#EXTM3U")
    assert "#EXTINF:90,P1" in text
    assert "https://example.com/p2" in text
