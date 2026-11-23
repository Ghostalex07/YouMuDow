"""Tests for the incremental repaint of the queue tree."""

import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.domain.enums import DownloadStatus
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


def _panel(root):
    snapshot = Mock(queue=[], active_downloads=[], completed_downloads=[], failed_downloads=[])
    controller = Mock()
    controller.state.get_snapshot.return_value = snapshot
    mw = Mock()
    mw._controller = controller
    mw._root = root
    return QueuePanel(root, mw)


def _snapshot(queue):
    return Mock(
        queue=queue,
        active_downloads=[],
        completed_downloads=[],
        failed_downloads=[],
    )


def test_identical_snapshots_do_not_touch_the_tree(root, monkeypatch):
    panel = _panel(root)
    queue = [Video(title=f"V{i}", url=f"https://x.test/{i}", queue_id=i) for i in range(20)]
    panel.update_display(_snapshot(queue))

    calls = []
    monkeypatch.setattr(ttk.Treeview, "move", lambda self, *args: calls.append(args))
    monkeypatch.setattr(ttk.Treeview, "item", lambda self, *args, **kwargs: calls.append(args))
    monkeypatch.setattr(ttk.Treeview, "insert", lambda self, *args, **kwargs: calls.append(args))

    for _ in range(5):
        panel.update_display(_snapshot(queue))

    assert calls == []


def test_reordering_updates_the_tree_order(root):
    panel = _panel(root)
    first = Video(title="A", url="https://x.test/a", queue_id=1)
    second = Video(title="B", url="https://x.test/b", queue_id=2)
    third = Video(title="C", url="https://x.test/c", queue_id=3)
    panel.update_display(_snapshot([first, second, third]))

    panel.update_display(_snapshot([third, first, second]))

    assert panel._queue_tree.get_children("") == ("q3", "q1", "q2")


def test_repaint_state_tracks_only_the_changed_row(root):
    panel = _panel(root)
    video = Video(title="A", url="https://x.test/a", queue_id=1, status=DownloadStatus.DOWNLOADING)
    other = Video(title="B", url="https://x.test/b", queue_id=2)
    panel.update_display(_snapshot([video, other]))
    before = list(panel._last_rows)

    video.progress = 42.0
    panel.update_display(_snapshot([video, other]))

    after = panel._last_rows
    assert after[0][1] == ("Downloading", "A", "42%")
    assert after[1] == before[1]
