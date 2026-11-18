import tkinter as tk

from conftest import pump

from youmudow.domain.models import Video


def _child_texts(stack):
    inner = stack.window._results_cards._inner
    texts = []
    for child in inner.winfo_children():
        if isinstance(child, tk.Label):
            texts.append(child.cget("text"))
    return texts


def test_query_renders_one_card_per_result(stack):
    stack.adapter.results = [
        Video(title="Lofi One", url="https://example.com/1", uploader="A", duration=61),
        Video(title="Lofi Two", url="https://example.com/2", uploader="B", duration=122),
    ]
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 2)
    assert stack.window._results_cards.card_count() == 2
    assert stack.window._is_searching is False


def test_selecting_a_card_fills_the_detail_panel(stack):
    video = Video(title="Lofi One", url="https://example.com/1", uploader="A")
    stack.adapter.results = [video]
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 1)
    stack.window._results_cards.select(0)
    stack.window._root.update()
    assert stack.window._selected_video is video
    assert stack.window._detail_panel._detail_title.cget("text") == "Lofi One"


def test_empty_query_never_reaches_the_service(stack):
    stack.window._search_bar.search_var.set("   ")
    stack.window._on_search()
    assert stack.adapter.queries == []


def test_failing_search_leaves_the_busy_state(stack, monkeypatch):
    def explode(query, limit=10):
        raise RuntimeError("network down")

    monkeypatch.setattr(stack.adapter, "search", explode)
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._is_searching is False)
    assert "Searching..." not in _child_texts(stack)
    assert "Error" in stack.window._status_bar._status_var.get()


def test_empty_results_show_the_empty_state(stack, monkeypatch):
    messages = []
    monkeypatch.setattr(stack.window, "_set_status", lambda *a, **k: messages.append(a[0]))
    stack.adapter.results = []
    stack.window._search_bar.search_var.set("nothing matches")
    stack.window._on_search()
    # Wait for the callback's own message, not for _is_searching: the IDLE
    # snapshot clears that flag before the callback has drawn the empty state.
    pump(stack.window, lambda: any("No results found" in m for m in messages))
    assert stack.window._results_cards._empty_state is not None


def test_selecting_a_card_previews_the_estimated_size(stack):
    from youmudow.domain.formats import FormatInfo

    stack.adapter.results = [Video(title="Lofi One", url="https://example.com/1", duration=60)]
    stack.adapter.formats = [FormatInfo("251", "m4a", 0, 256.0, 0.0, 0)]
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 1)

    stack.window._results_cards.select(0)
    pump(stack.window, lambda: "~" in stack.window._detail_panel._detail_meta.cget("text"))

    assert stack.window._detail_panel._detail_meta.cget("text") == "1:00 · ~1.8 MB"


def test_first_result_is_previewed_without_clicking(stack):
    from youmudow.domain.formats import FormatInfo

    stack.adapter.results = [Video(title="Lofi One", url="https://example.com/1", duration=60)]
    stack.adapter.formats = [FormatInfo("251", "m4a", 0, 256.0, 0.0, 0)]
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()

    pump(stack.window, lambda: "~" in stack.window._detail_panel._detail_meta.cget("text"))


def test_rapid_selection_debounces_the_format_lookup(stack):
    from youmudow.domain.formats import FormatInfo

    stack.adapter.results = [
        Video(title=f"V{i}", url=f"https://example.com/{i}", duration=60) for i in range(3)
    ]
    stack.adapter.formats = [FormatInfo("251", "m4a", 0, 256.0, 0.0, 0)]
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count() == 3)
    pump(stack.window, lambda: stack.adapter.format_calls >= 1)

    stack.adapter.format_calls = 0
    for index in range(3):
        stack.window._results_cards.select(index)
    pump(stack.window, lambda: stack.adapter.format_calls >= 1)

    assert stack.adapter.format_calls == 1
