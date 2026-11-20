"""What a first-time user sees when the window opens."""

from conftest import pump

from youmudow.domain.models import Video


def test_results_pane_explains_what_to_do(stack):
    inner_texts = [
        child.cget("text")
        for child in stack.window._results_cards._inner.winfo_children()
        for child in child.winfo_children()
        if child.winfo_class() == "Label"
    ]
    assert any("Paste a link" in text for text in inner_texts)
    assert any("drag" in text.lower() for text in inner_texts)


def test_paste_button_searches_the_clipboard(stack, monkeypatch):
    stack.window._root.clipboard_clear()
    stack.window._root.clipboard_append("https://youtube.com/watch?v=abc")
    stack.adapter.metadata = Video(title="Pasted", url="https://youtube.com/watch?v=abc")

    stack.window._paste_from_clipboard()
    pump(stack.window, lambda: stack.window._detail_panel._detail_title.cget("text") == "Pasted")
    assert stack.window._search_bar.search_var.get() == "https://youtube.com/watch?v=abc"


def test_detail_panel_says_nothing_is_selected(stack):
    title = stack.window._detail_panel._detail_title.cget("text")
    assert "No video" in title


def test_queue_panel_starts_hidden_and_appears_with_work(stack):
    queue = stack.window._detail_panel.queue
    assert queue.visible is False

    stack.controller.enqueue(Video(title="A", url="https://x.test/a"))
    stack.window._refresh_queue()
    assert queue.visible is True


def test_pause_is_disabled_until_there_is_work(stack):
    queue = stack.window._detail_panel.queue
    stack.window._refresh_queue()
    assert str(queue._pause_btn.cget("state")) == "disabled"

    stack.controller.enqueue(Video(title="A", url="https://x.test/a"))
    stack.window._refresh_queue()
    assert str(queue._pause_btn.cget("state")) == "normal"


def test_actions_are_disabled_until_something_is_selected(stack):
    detail = stack.window._detail_panel
    for button in (
        detail._download_btn,
        detail._add_all_btn,
        detail._export_btn,
        detail._load_more_btn,
    ):
        assert str(button.cget("state")) == "disabled"
