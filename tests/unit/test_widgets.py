"""Tests for UI widgets."""

import os
import pytest
from unittest.mock import Mock

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
        from youmudow.ui.widgets.results_table import ResultsTable
        from youmudow.domain.models import Video
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
        from youmudow.ui.widgets.history_panel import HistoryPanel
        from youmudow.domain.models import HistoryEntry
        hp = HistoryPanel(tk_root, mock_window)
        hp._all_entries = [
            HistoryEntry(title="Song A", url="url1", uploader="artist1",
                         file_format="mp3", output_path="/tmp", downloaded_at="2024-01-01T00:00:00"),
            HistoryEntry(title="Song B", url="url2", uploader="artist2",
                         file_format="flac", output_path="/tmp", downloaded_at="2024-01-02T00:00:00"),
        ]
        hp._apply_filter("Song A")
        assert len(hp._filtered) == 1
        assert hp._filtered[0].title == "Song A"
