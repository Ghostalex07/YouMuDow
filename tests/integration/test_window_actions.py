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
    monkeypatch.setattr(stack.window._history_panel, "refresh", lambda: refreshed.append(True))
    stack.window._notebook.select(0)
    stack.window._on_tab_changed()
    assert refreshed == []


def test_switching_to_the_history_tab_refreshes_it(stack, monkeypatch):
    refreshed = []
    monkeypatch.setattr(stack.window._history_panel, "refresh", lambda: refreshed.append(True))
    stack.window._notebook.select(1)
    stack.window._on_tab_changed()
    assert refreshed
