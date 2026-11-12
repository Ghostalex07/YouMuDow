"""Performance-focused tests: redundant-work removal and lazy imports."""

import tkinter as tk
from unittest.mock import Mock

import pytest

from youmudow.app.state import StateManager


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def window(tk_root):
    mw = Mock()
    mw._root = tk_root
    mw._config = Mock()
    mw._config.get_search_history.return_value = []
    mw._controller = Mock()
    mw._controller._download_service._max_concurrent = 1
    mw._controller.state = StateManager()
    mw._selected_video = None
    mw._results_cards = Mock()
    mw._results_cards.is_playlist = False
    mw._results_cards.playlist_videos = []
    return mw


def test_browser_profiles_cached_per_instance(tk_root, window, monkeypatch):
    from youmudow.ui.widgets import options_panel
    from youmudow.ui.widgets.options_panel import OptionsPanel

    calls = 0

    def fake_browsers():
        nonlocal calls
        calls += 1
        return ["chrome", "firefox"]

    monkeypatch.setattr(options_panel, "get_available_browsers", fake_browsers)

    panel = OptionsPanel(tk_root, window)

    first = panel._browser_options()
    second = panel._browser_options()

    assert first == ["chrome", "firefox"]
    assert second == first
    assert calls == 1  # memoized: detection runs once, not on every call
