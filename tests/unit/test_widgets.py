"""Tests for UI widgets."""

import os
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)


@pytest.fixture
def tk_root():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def mock_window(tk_root):
    mw = Mock()
    mw._root = tk_root
    mw._config = Mock()
    mw._config.get_search_history.return_value = ["test query"]
    mw._controller = Mock()
    mw._controller._download_service._max_concurrent = 1
    return mw


@pytest.fixture
def state_window(tk_root):
    import tkinter as tk

    from youmudow.app.state import StateManager

    mw = Mock()
    mw._root = tk_root
    mw._config = Mock()
    mw._config.get_search_history.return_value = []
    mw._controller = Mock()
    mw._controller._download_service._max_concurrent = 1
    mw._controller.state = StateManager()
    mw._main_content_frame = tk.Frame(tk_root)
    mw._main_content_frame.grid(row=0, column=0)
    mw._selected_video = None
    mw._results_cards.is_playlist = False
    mw._results_cards.playlist_videos = []
    return mw


@pytest.fixture
def detail_panel(state_window, tk_root):
    from youmudow.ui.widgets.detail_panel import DetailPanel

    panel = DetailPanel(state_window._main_content_frame, state_window)
    panel.queue.grid()
    panel.queue.visible = True
    tk_root.update()
    return panel


class TestSearchBar:
    def test_init(self, tk_root, mock_window):
        from youmudow.ui.widgets.search_bar import _PLACEHOLDER, SearchBar

        sb = SearchBar(tk_root, mock_window)
        # The placeholder is written into the shared variable, so the query
        # itself stays empty even though the variable is not.
        assert sb.get_query() == ""
        assert sb.search_var.get() == _PLACEHOLDER


class TestStatusBar:
    def test_init(self, tk_root, mock_window):
        from youmudow.ui.widgets.status_bar import StatusBar

        sb = StatusBar(tk_root, mock_window)
        assert sb is not None

    def test_set_status(self, tk_root, mock_window):
        from youmudow.ui.widgets.status_bar import StatusBar

        sb = StatusBar(tk_root, mock_window)
        sb.set_status("test status")


class TestHistoryPanel:
    def test_init(self, tk_root, mock_window):
        from youmudow.ui.widgets.history_panel import HistoryPanel

        hp = HistoryPanel(tk_root, mock_window)
        assert hp is not None

    def test_refresh(self, tk_root, mock_window):
        from youmudow.ui.widgets.history_panel import HistoryPanel

        mock_window._controller.history.get_all.return_value = []
        hp = HistoryPanel(tk_root, mock_window)
        hp.refresh()

    def test_apply_filter(self, tk_root, mock_window):
        from youmudow.domain.models import HistoryEntry
        from youmudow.ui.widgets.history_panel import HistoryPanel

        hp = HistoryPanel(tk_root, mock_window)
        hp._all_entries = [
            HistoryEntry(
                title="Song A",
                url="url1",
                uploader="artist1",
                file_format="mp3",
                output_path="/tmp",
                downloaded_at="2024-01-01T00:00:00",
            ),
            HistoryEntry(
                title="Song B",
                url="url2",
                uploader="artist2",
                file_format="flac",
                output_path="/tmp",
                downloaded_at="2024-01-02T00:00:00",
            ),
        ]
        hp._apply_filter("Song A")
        assert len(hp._filtered) == 1
        assert hp._filtered[0].title == "Song A"


class _RecordingMenu:
    def __init__(self, *args, **kwargs):
        self.commands = {}

    def add_command(self, label=None, command=None, **kwargs):
        self.commands[label] = command

    def add_separator(self, **kwargs):
        pass

    def tk_popup(self, *args, **kwargs):
        pass


class TestQueuePanel:
    def _download(self, sm, title, url, status):
        from youmudow.domain.enums import DownloadStatus
        from youmudow.domain.models import Video

        video = Video(title=title, url=url)
        sm.add_to_queue(video)
        sm.start_download(video)
        video.status = status
        if status is DownloadStatus.ERROR:
            video.error_message = "Authentication required"
        sm.finish_download(video)
        return video

    def _rows(self, panel):
        tree = panel.queue._queue_tree
        return [tree.item(iid, "values") for iid in tree.get_children("")]

    def test_requeued_url_does_not_break_panel(self, detail_panel, state_window):
        """Re-downloading a finished video must not raise inside the treeview."""
        from youmudow.domain.enums import DownloadStatus
        from youmudow.domain.models import Video

        sm = state_window._controller.state
        url = "https://www.youtube.com/watch?v=abc"
        self._download(sm, "Song", url, DownloadStatus.DONE)
        detail_panel.queue.update_display(sm.get_snapshot())

        sm.add_to_queue(Video(title="Song", url=url))
        for iid in detail_panel.queue._queue_tree.get_children(""):
            detail_panel.queue._queue_tree.delete(iid)

        detail_panel.queue.update_display(sm.get_snapshot())

        rows = self._rows(detail_panel)
        assert len(rows) == 2
        assert [row[0] for row in rows] == ["Queued", "Completed"]

    def test_failed_download_not_rendered_as_completed(self, detail_panel, state_window):
        from youmudow.domain.enums import DownloadStatus

        sm = state_window._controller.state
        self._download(sm, "Secret", "https://youtu.be/x", DownloadStatus.ERROR)
        detail_panel.queue.update_display(sm.get_snapshot())

        status, title, progress = self._rows(detail_panel)[0]
        assert status == "Failed"
        assert progress != "100%"
        assert title == "Secret"

    def test_cancelled_download_rendered(self, detail_panel, state_window):
        from youmudow.domain.models import Video

        sm = state_window._controller.state
        video = Video(title="Nope", url="https://youtu.be/y")
        sm.add_to_queue(video)
        sm.start_download(video)
        sm.cancel_download(video)
        detail_panel.queue.update_display(sm.get_snapshot())

        assert self._rows(detail_panel)[0][0] == "Cancelled"

    def test_right_click_remove_on_completed_row(self, detail_panel, state_window, monkeypatch):
        from types import SimpleNamespace

        from youmudow.domain.enums import DownloadStatus
        from youmudow.ui.widgets import detail_panel as detail_panel_module

        sm = state_window._controller.state
        finished = self._download(sm, "Done", "https://youtu.be/z", DownloadStatus.DONE)
        detail_panel.queue.update_display(sm.get_snapshot())
        state_window._root.update()

        created = []
        monkeypatch.setattr(
            detail_panel_module.tk,
            "Menu",
            lambda *a, **k: created.append(_RecordingMenu()) or created[-1],
        )

        iid = detail_panel.queue._queue_tree.get_children("")[0]
        row_y = next(
            y
            for y in range(detail_panel.queue._queue_tree.winfo_height())
            if detail_panel.queue._queue_tree.identify_row(y) == iid
        )
        detail_panel.queue._on_right_click(SimpleNamespace(y=row_y, x_root=0, y_root=0))

        assert created, "no context menu shown for a completed row"
        remove = created[0].commands["Remove from queue"]
        remove()
        state_window._controller.remove_from_queue.assert_called_once()
        assert state_window._controller.remove_from_queue.call_args.args[0].queue_id == (
            finished.queue_id
        )


class TestDetailPanelActions:
    def _video(self, title="Song", url="https://youtu.be/a"):
        from youmudow.domain.models import Video

        return Video(title=title, url=url)

    def test_enqueue_selected_queues_every_selected_video(self, detail_panel, state_window):
        videos = [
            self._video("One", "https://youtu.be/1"),
            self._video("Two", "https://youtu.be/2"),
        ]
        state_window._results_cards.get_selected_videos.return_value = videos

        detail_panel.enqueue_selected()

        state_window._controller.enqueue_multiple.assert_called_once_with(videos)
        state_window._set_status.assert_called_once_with("Added 2 to queue")
        assert all(video.options is not None for video in videos)

    def test_enqueue_selected_falls_back_to_selected_video(self, detail_panel, state_window):
        video = self._video()
        state_window._results_cards.get_selected_videos.return_value = []
        state_window._selected_video = video

        detail_panel.enqueue_selected()

        state_window._controller.enqueue.assert_called_once_with(video)
        assert video.options is not None
        state_window._set_status.assert_called_once_with(f"Added to queue: {video.title}")

    def test_enqueue_selected_ignores_expanded_playlist_without_selection(
        self, detail_panel, state_window
    ):
        state_window._results_cards.get_selected_videos.return_value = []
        state_window._results_cards.is_playlist = True
        state_window._results_cards.playlist_videos = [self._video()]

        detail_panel.enqueue_selected()

        state_window._controller.enqueue.assert_not_called()
        state_window._controller.enqueue_multiple.assert_not_called()

    def test_add_all_queues_the_whole_playlist(self, detail_panel, state_window):
        videos = [
            self._video("One", "https://youtu.be/1"),
            self._video("Two", "https://youtu.be/2"),
        ]
        state_window._results_cards.playlist_videos = videos

        detail_panel._add_all_to_queue()

        state_window._controller.enqueue_multiple.assert_called_once_with(videos)
        state_window._set_status.assert_called_once_with("Added 2 videos to queue")
        assert all(video.options is not None for video in videos)

    def test_toggle_queue_panel_flips_visibility(self, detail_panel):
        assert detail_panel.queue_panel_visible is True

        detail_panel._toggle_queue_panel()

        assert detail_panel.queue_panel_visible is False
        detail_panel._toggle_queue_panel()
        assert detail_panel.queue_panel_visible is True

    def test_empty_thumbnail_resets_last_thumb_url(self, detail_panel):
        detail_panel._last_thumb_url = "http://old/thumb.jpg"

        detail_panel._load_thumbnail(self._video())

        assert detail_panel._last_thumb_url == ""
