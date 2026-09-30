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
    mw._results_table.is_playlist = False
    mw._results_table.playlist_videos = []
    return mw


@pytest.fixture
def detail_panel(state_window, tk_root):
    from youmudow.ui.widgets.detail_panel import DetailPanel

    panel = DetailPanel(state_window._main_content_frame, state_window)
    panel._queue_frame.grid()
    panel._queue_panel_visible = True
    tk_root.update()
    return panel


class TestSearchBar:
    def test_init(self, tk_root, mock_window):
        from youmudow.ui.widgets.search_bar import SearchBar

        sb = SearchBar(tk_root, mock_window)
        assert sb.search_var.get() == ""

    def test_get_query_returns_text(self, tk_root, mock_window):
        from youmudow.ui.widgets.search_bar import SearchBar

        sb = SearchBar(tk_root, mock_window)
        sb.search_var.set("test query")
        assert sb.get_query() == "test query"

    def test_get_query_ignores_placeholder(self, tk_root, mock_window):
        from youmudow.ui.widgets.search_bar import SearchBar

        sb = SearchBar(tk_root, mock_window)
        sb._search_combo.set(sb._placeholder)
        assert sb.get_query() == ""

    def test_update_history(self, tk_root, mock_window):
        from youmudow.ui.widgets.search_bar import SearchBar

        sb = SearchBar(tk_root, mock_window)
        history = ["url1", "url2"]
        sb.update_history(history)
        assert list(sb._search_combo["values"]) == history

    def test_search_entry_property(self, tk_root, mock_window):
        from youmudow.ui.widgets.search_bar import SearchBar

        sb = SearchBar(tk_root, mock_window)
        assert sb.search_entry is sb._search_combo

    def test_update_button_states(self, tk_root, mock_window):
        from youmudow.ui.widgets.search_bar import SearchBar

        sb = SearchBar(tk_root, mock_window)
        sb.update_button_states(True, False)
        assert sb._search_btn.cget("state") == "disabled"
        sb.update_button_states(False, False)
        assert sb._search_btn.cget("state") == "normal"


class TestResultsTable:
    def test_init(self, tk_root, mock_window):
        from youmudow.ui.widgets.results_table import ResultsTable

        rt = ResultsTable(tk_root, mock_window)
        assert rt.results_tree is not None

    def test_clear_results(self, tk_root, mock_window):
        from youmudow.ui.widgets.results_table import ResultsTable

        rt = ResultsTable(tk_root, mock_window)
        rt.clear_results()

    def test_update_results(self, tk_root, mock_window):
        from youmudow.domain.models import Video
        from youmudow.ui.widgets.results_table import ResultsTable

        rt = ResultsTable(tk_root, mock_window)
        videos = [
            Video(title="Test 1", url="https://example.com/1"),
            Video(title="Test 2", url="https://example.com/2"),
        ]
        rt.update_results(videos)


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
        tree = panel._queue_tree
        return [tree.item(iid, "values") for iid in tree.get_children("")]

    def test_requeued_url_does_not_break_panel(self, detail_panel, state_window):
        """Re-downloading a finished video must not raise inside the treeview."""
        from youmudow.domain.enums import DownloadStatus
        from youmudow.domain.models import Video

        sm = state_window._controller.state
        url = "https://www.youtube.com/watch?v=abc"
        self._download(sm, "Song", url, DownloadStatus.DONE)
        detail_panel._update_queue_display(sm.get_snapshot())

        sm.add_to_queue(Video(title="Song", url=url))
        for iid in detail_panel._queue_tree.get_children(""):
            detail_panel._queue_tree.delete(iid)

        detail_panel._update_queue_display(sm.get_snapshot())

        rows = self._rows(detail_panel)
        assert len(rows) == 2
        assert [row[0] for row in rows] == ["Queued", "Completed"]

    def test_failed_download_not_rendered_as_completed(self, detail_panel, state_window):
        from youmudow.domain.enums import DownloadStatus

        sm = state_window._controller.state
        self._download(sm, "Secret", "https://youtu.be/x", DownloadStatus.ERROR)
        detail_panel._update_queue_display(sm.get_snapshot())

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
        detail_panel._update_queue_display(sm.get_snapshot())

        assert self._rows(detail_panel)[0][0] == "Cancelled"

    def test_right_click_remove_on_completed_row(self, detail_panel, state_window, monkeypatch):
        from types import SimpleNamespace

        from youmudow.domain.enums import DownloadStatus
        from youmudow.ui.widgets import detail_panel as detail_panel_module

        sm = state_window._controller.state
        finished = self._download(sm, "Done", "https://youtu.be/z", DownloadStatus.DONE)
        detail_panel._update_queue_display(sm.get_snapshot())
        state_window._root.update()

        created = []
        monkeypatch.setattr(
            detail_panel_module.tk,
            "Menu",
            lambda *a, **k: created.append(_RecordingMenu()) or created[-1],
        )

        iid = detail_panel._queue_tree.get_children("")[0]
        row_y = next(
            y
            for y in range(detail_panel._queue_tree.winfo_height())
            if detail_panel._queue_tree.identify_row(y) == iid
        )
        detail_panel._on_queue_right_click(
            SimpleNamespace(y=row_y, x_root=0, y_root=0)
        )

        assert created, "no context menu shown for a completed row"
        remove = created[0].commands["Remove from queue"]
        remove()
        state_window._controller.remove_from_queue.assert_called_once()
        assert state_window._controller.remove_from_queue.call_args.args[0].queue_id == (
            finished.queue_id
        )
