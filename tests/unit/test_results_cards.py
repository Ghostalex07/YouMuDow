"""Tests for the ResultsCards widget."""

import tkinter as tk
from unittest.mock import Mock

import pytest

from youmudow.domain.models import Video
from youmudow.ui.widgets.results_cards import ResultsCards


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def state():
    return Mock()


@pytest.fixture
def loader():
    return Mock()


def _videos(n):
    return [Video(title=f"Video {i}", url=f"https://example.com/{i}") for i in range(n)]


def test_cards_count(root, state, loader):
    w = ResultsCards(root, state, loader)
    w.update_results(_videos(3))
    assert w.card_count() == 3
    w.destroy()


def test_selection_bounds_and_enter_noop(root, state, loader):
    w = ResultsCards(root, state, loader)
    w.update_results(_videos(1))
    w.select(-1)
    w.select(5)  # clamp, no error
    assert w.get_selected() == [0]
    w.destroy()


def test_get_selected_returns_indices(root, state, loader):
    w = ResultsCards(root, state, loader)
    w.update_results(_videos(2))
    w.select(1)
    assert w.get_selected() == [1]
    w.destroy()


def test_select_notify_false_sets_selection_without_callback(root, state, loader):
    on_select = Mock()
    w = ResultsCards(root, state, loader, on_select=on_select)
    w.update_results(_videos(3))
    w.select(0, notify=False)
    assert w.get_selected() == [0]
    on_select.assert_not_called()
    w.destroy()


def test_enter_with_no_selection_is_noop(root, state, loader):
    on_double = Mock()
    w = ResultsCards(root, state, loader, on_double_click=on_double)
    w.update_results(_videos(2))
    w._on_enter()
    assert not on_double.called
    w.destroy()


def test_enter_with_selection_fires_double_click(root, state, loader):
    on_double = Mock()
    w = ResultsCards(root, state, loader, on_double_click=on_double)
    w.update_results(_videos(2))
    w.select(0)
    w._on_enter()
    on_double.assert_called_once()
    w.destroy()


def test_keyboard_navigation_moves_selection(root, state, loader):
    w = ResultsCards(root, state, loader)
    w.update_results(_videos(3))
    w.select(0)
    w._on_down()
    assert w.get_selected() == [1]
    w._on_up()
    assert w.get_selected() == [0]
    w.destroy()


def test_double_click_fires_callback(root, state, loader):
    on_double = Mock()
    w = ResultsCards(root, state, loader, on_double_click=on_double)
    w.update_results(_videos(2))
    w._on_card_double_click(1)
    on_double.assert_called_once()
    assert w.get_selected() == [1]
    w.destroy()


def test_right_click_opens_in_browser(root, state, loader):
    on_open = Mock()
    w = ResultsCards(root, state, loader, on_open_in_browser=on_open)
    w.update_results(_videos(2))
    w._on_card_right_click(1)
    on_open.assert_called_once_with("https://example.com/1")
    w.destroy()


def test_update_requests_thumbnails(root, state, loader):
    videos = _videos(2)
    videos[0].thumbnail = "https://img.youtube.com/vi/abc12345678/hqdefault.jpg"
    w = ResultsCards(root, state, loader)
    w.update_results(videos)
    assert loader.request.called
    w.destroy()


def test_get_selected_videos_maps_indices(root, state, loader):
    w = ResultsCards(root, state, loader)
    w.update_results(_videos(2))
    w.select(1)
    videos = w.get_selected_videos()
    assert len(videos) == 1
    assert videos[0].url == "https://example.com/1"
    w.destroy()


def test_clear_results_empties_cards(root, state, loader):
    w = ResultsCards(root, state, loader)
    w.update_results(_videos(3))
    w.clear_results()
    assert w.card_count() == 0
    assert w.get_selected() == []
    w.destroy()


class TestThumbnailRetry:
    def test_failed_thumbnail_is_retried_once(self, root, state, loader):
        w = ResultsCards(root, state, loader)
        w._thumb_urls[0] = "https://example.com/t.jpg"
        scheduled = []
        w.after = lambda ms, cb: scheduled.append((ms, cb))

        w._on_thumb_ready(0, "https://example.com/t.jpg", None)
        w._on_thumb_ready(0, "https://example.com/t.jpg", None)

        assert len(scheduled) == 1  # one retry, not a loop
        scheduled[0][1]()
        loader.request.assert_called_once()
        w.destroy()

    def test_retry_is_dropped_when_the_card_moved_on(self, root, state, loader):
        w = ResultsCards(root, state, loader)
        scheduled = []
        w.after = lambda ms, cb: scheduled.append((ms, cb))
        w._thumb_urls[0] = "https://example.com/old.jpg"

        w._on_thumb_ready(0, "https://example.com/old.jpg", None)
        w._thumb_urls[0] = "https://example.com/new.jpg"
        scheduled[0][1]()

        loader.request.assert_not_called()
        w.destroy()


class TestCardPlaceholders:
    def test_missing_title_gets_a_readable_fallback(self, root, state, loader):
        w = ResultsCards(root, state, loader)
        assert w._title_text(Video(title="", url="https://example.com/x")) == "Untitled video"
        w.destroy()

    def test_missing_metadata_says_so_instead_of_showing_nothing(self, root, state, loader):
        w = ResultsCards(root, state, loader)
        assert w._meta_text(Video(title="T", url="https://example.com/x")) == "Metadata unavailable"
        w.destroy()
