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


def test_scanning_the_folder_finds_and_imports_stray_files(stack):
    output = stack.downloads.get_output_path()
    output.mkdir(parents=True, exist_ok=True)
    (output / "Stray Song.mp3").write_bytes(b"12345")
    panel = stack.window._library_panel

    panel._scan()
    assert [item.path.name for item in panel._scanned] == ["Stray Song.mp3"]

    panel._import_files()
    assert stack.controller.library_stats()["count"] == 1
    assert panel._scanned == []


def test_add_new_only_skips_what_is_already_downloaded(stack):
    from conftest import pump

    from youmudow.domain.models import Video

    stack.library_store.add_history(
        HistoryEntry(
            title="Old",
            url="https://example.com/old",
            uploader="",
            file_format="mp3",
            output_path="",
            downloaded_at=datetime.now().astimezone().isoformat(),
        )
    )
    stack.adapter.playlist = [
        Video(title="Old", url="https://example.com/old"),
        Video(title="New", url="https://example.com/new"),
    ]
    stack.window._search_bar.search_var.set("https://www.youtube.com/playlist?list=PL1")
    stack.window._on_search()
    pump(stack.window, lambda: len(stack.window._results_cards.playlist_videos) == 2)

    stack.window._detail_panel._add_new_to_queue()

    assert [v.url for v in stack.controller.state.get_queue()] == ["https://example.com/new"]
