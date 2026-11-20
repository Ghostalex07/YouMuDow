"""Tests for the failure summary in the queue panel."""

import tkinter as tk
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.domain.models import Video
from youmudow.ui.widgets.queue_panel import QueuePanel


@pytest.fixture
def root():
    try:
        root = tk.Tk()
    except tk.TclError:  # pragma: no cover - headless without X
        pytest.skip("no display")
    root.withdraw()
    yield root
    root.destroy()


def _panel(root, failed):
    snapshot = Mock(queue=[], active_downloads=[], completed_downloads=[], failed_downloads=failed)
    controller = Mock()
    controller.state.get_snapshot.return_value = snapshot
    mw = Mock()
    mw._controller = controller
    mw._root = root
    panel = QueuePanel(root, mw)
    panel.update_display(snapshot)
    return panel, mw


def test_summary_groups_failures_by_cause(root):
    failed = [
        Video(title="a", url="u1", error_message="Private video"),
        Video(title="b", url="u2", error_message="Private video"),
        Video(title="c", url="u3", error_message="Sign in to confirm you're not a bot"),
    ]
    panel, _ = _panel(root, failed)
    text = panel._problems_label.cget("text")
    assert "2" in text and "private" in text.lower()
    assert "1" in text and "cookie" in text.lower()
    assert panel._problems.winfo_manager()


def test_summary_is_hidden_without_failures(root):
    panel, _ = _panel(root, [])
    assert not panel._problems.winfo_manager()


def test_retry_button_delegates_to_the_window(root):
    panel, mw = _panel(root, [Video(title="a", url="u1", error_message="boom")])
    panel._retry_failed_btn.invoke()
    mw._on_retry_failed.assert_called_once_with()
