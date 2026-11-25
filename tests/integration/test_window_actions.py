"""Window actions that a user triggers directly, end to end."""

from conftest import pump

from youmudow.domain.models import Video


def test_pasting_a_video_url_previews_its_metadata(stack):
    stack.adapter.metadata = Video(
        title="Single", url="https://youtube.com/watch?v=abc", uploader="Chan"
    )
    stack.window._search_bar.search_var.set("https://youtube.com/watch?v=abc")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._detail_panel._detail_title.cget("text") == "Single")
    assert stack.adapter.queries == []
    assert stack.adapter.metadata_calls == ["https://youtube.com/watch?v=abc"]


def test_opening_a_result_in_the_browser_uses_the_default_browser(stack, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    stack.window._on_open_in_browser("https://x.test/watch")
    assert opened == ["https://x.test/watch"]


def test_staying_on_the_search_tab_does_not_refresh_history(stack, monkeypatch):
    refreshed = []
    panel = stack.window._ensure_history_panel()
    monkeypatch.setattr(panel, "refresh", lambda: refreshed.append(True))
    stack.window._notebook.select(0)
    stack.window._on_tab_changed()
    assert refreshed == []


def test_switching_to_the_history_tab_refreshes_it(stack, monkeypatch):
    refreshed = []
    panel = stack.window._ensure_history_panel()
    monkeypatch.setattr(panel, "refresh", lambda: refreshed.append(True))
    stack.window._notebook.select(1)
    stack.window._on_tab_changed()
    assert refreshed


def test_dropping_a_link_searches_it(stack):
    stack.adapter.metadata = Video(
        title="Dropped", url="https://youtube.com/watch?v=abc", uploader="Chan"
    )
    stack.window._accept_dropped_urls(["https://youtube.com/watch?v=abc"])
    pump(stack.window, lambda: stack.window._detail_panel._detail_title.cget("text") == "Dropped")
    assert stack.window._search_bar.search_var.get() == "https://youtube.com/watch?v=abc"


def test_dropping_nothing_explains_what_is_accepted(stack):
    stack.window._accept_dropped_urls([])
    assert "supported link" in stack.window._status_bar._status_var.get()


def test_queue_shortcuts_are_bound(stack):
    assert stack.window._root.bind("<Control-Shift-s>")


def test_download_now_stops_when_the_disk_is_full(stack, monkeypatch):
    from youmudow.domain.models import Video

    stack.adapter.results = [Video(title="Big", url="https://example.com/big")]
    stack.window._search_bar.search_var.set("big")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 1)
    stack.window._detail_panel.set_estimate(10**12)
    monkeypatch.setattr("youmudow.ui.window.has_room_for", lambda path, needed: False)
    monkeypatch.setattr("youmudow.ui.window.free_bytes", lambda path: 1024)

    stack.window._on_download_now()

    assert "space" in stack.window._status_bar._status_var.get().lower()
    assert stack.controller.state.get_queue() == []


def test_tabs_are_built_only_when_first_opened(stack):
    window = stack.window
    assert window._history_panel is None
    assert window._library_panel is None

    window._notebook.select(1)
    window._on_tab_changed()
    assert window._history_panel is not None
    assert window._library_panel is None

    window._notebook.select(2)
    window._on_tab_changed()
    assert window._library_panel is not None

    first = window._library_panel
    window._notebook.select(0)
    window._on_tab_changed()
    window._notebook.select(2)
    window._on_tab_changed()
    assert window._library_panel is first


def test_state_snapshots_are_coalesced_before_rendering(stack, monkeypatch):
    applied: list[int] = []
    monkeypatch.setattr(stack.window, "_update_from_snapshot", lambda snapshot: applied.append(1))
    for _ in range(6):
        stack.controller.state.set_state(stack.controller.state.state)
    pump(stack.window, lambda: bool(applied), timeout=2.0)
    assert len(applied) < 6
