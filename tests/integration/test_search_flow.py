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


def test_empty_results_show_the_empty_state(stack):
    stack.adapter.results = []
    stack.window._search_bar.search_var.set("nothing matches")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._is_searching is False)
    assert stack.window._results_cards._empty_state is not None
    assert "No results found" in stack.window._status_bar._status_var.get()


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
