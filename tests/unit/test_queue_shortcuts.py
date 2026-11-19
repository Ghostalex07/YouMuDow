"""Keyboard shortcuts for the queue panel."""

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


def _panel(root, queued):
    controller = Mock()
    controller.state.get_snapshot.return_value = Mock(
        queue=queued, active_downloads=[], completed_downloads=[], failed_downloads=[]
    )
    mw = Mock()
    mw._controller = controller
    mw._root = root
    panel = QueuePanel(root, mw)
    panel.update_display(controller.state.get_snapshot())
    return panel, controller


def test_delete_removes_the_selected_queue_entry(root):
    first = Video(title="One", url="https://x.test/1", queue_id="1")
    second = Video(title="Two", url="https://x.test/2", queue_id="2")
    panel, controller = _panel(root, [first, second])

    panel._queue_tree.selection_set(panel._queue_tree.get_children()[1])
    panel._on_remove_selected()

    controller.remove_from_queue.assert_called_once_with(second)


def test_delete_without_a_selection_does_nothing(root):
    panel, controller = _panel(root, [Video(title="One", url="https://x.test/1", queue_id="1")])
    panel._on_remove_selected()
    controller.remove_from_queue.assert_not_called()


def test_delete_is_bound_to_the_tree(root):
    panel, _ = _panel(root, [])
    assert panel._queue_tree.bind("<Delete>")
