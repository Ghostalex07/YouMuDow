from datetime import datetime

from youmudow.domain.models import HistoryEntry


def test_library_tab_summarises_the_database(stack):
    stack.library_store.add_history(
        HistoryEntry(
            title="One",
            url="https://youtube.com/watch?v=one",
            uploader="Chan",
            file_format="mp3",
            output_path="",
            downloaded_at=datetime.now().astimezone().isoformat(),
            file_size_bytes=2048,
        )
    )
    stack.window._library_panel.refresh()
    assert "1" in stack.window._library_panel._summary.cget("text")
    assert "Chan" in stack.window._library_panel._body.get("1.0", "end")


def test_check_library_reports_missing_files(stack):
    stack.library_store.add_history(
        HistoryEntry(
            title="Gone",
            url="https://youtube.com/watch?v=gone",
            uploader="Chan",
            file_format="mp3",
            output_path="",
            downloaded_at=datetime.now().astimezone().isoformat(),
        )
    )
    stack.window._library_panel._check()
    assert stack.window._library_panel._missing == ["Gone"]
    assert "1" in stack.window._library_panel._summary.cget("text")


def test_requeue_missing_queues_the_lost_entries(stack):
    stack.library_store.add_history(
        HistoryEntry(
            title="Gone",
            url="https://youtube.com/watch?v=gone",
            uploader="Chan",
            file_format="mp3",
            output_path="",
            downloaded_at=datetime.now().astimezone().isoformat(),
        )
    )
    assert stack.window._on_requeue_missing() == 1
    assert [video.title for video in stack.controller.state.get_queue()] == ["Gone"]


def test_import_urls_text_queues_supported_links(stack):
    text = "https://youtube.com/watch?v=a\n# comment\nnot a link\nhttps://youtube.com/watch?v=b"
    assert stack.window._import_urls_text(text) == 2
    assert len(stack.controller.state.get_queue()) == 2


def test_queue_pause_button_toggles_the_service(stack):
    queue_panel = stack.window._detail_panel.queue
    queue_panel._toggle_pause()
    assert stack.controller.downloads_paused is True
    assert queue_panel._pause_btn.cget("text") == "Resume"
    queue_panel._toggle_pause()
    assert stack.controller.downloads_paused is False


def test_dragging_a_queue_row_reorders_it(stack):
    stack.controller.enqueue_urls(
        [
            "https://youtube.com/watch?v=a",
            "https://youtube.com/watch?v=b",
        ]
    )
    queue_panel = stack.window._detail_panel.queue
    queue_panel.update_display()
    rows = queue_panel._queue_tree.get_children()
    first = stack.controller.state.get_queue()[0]
    assert stack.controller.move_in_queue(first, 1) is True
    assert [video.url for video in stack.controller.state.get_queue()][1].endswith("a")
    assert len(rows) == 2
