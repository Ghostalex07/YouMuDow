"""Timing guards for the two operations that used to freeze the window.

Thresholds are deliberately loose (3-10x the measured value) so a busy CI
runner does not fail them; they exist to catch a regression that reinstates the
old per-row or per-card work, which was an order of magnitude slower.
"""

import time
from unittest.mock import Mock

import pytest

from youmudow.app.state import AppState
from youmudow.domain.models import Video

pytestmark = pytest.mark.perf


def _videos(count: int) -> list[Video]:
    return [
        Video(title=f"Video {i}", url=f"https://x.test/{i}", queue_id=str(i)) for i in range(count)
    ]


def test_repainting_a_500_row_queue_stays_cheap(stack):
    panel = stack.window._detail_panel.queue
    snapshot = Mock()
    snapshot.queue = _videos(500)
    snapshot.active_downloads = []
    snapshot.completed_downloads = []
    snapshot.failed_downloads = []
    snapshot.state = AppState.IDLE

    panel.update_display(snapshot)  # warm up: this one inserts the rows

    start = time.perf_counter()
    for _ in range(20):
        panel.update_display(snapshot)
    per_repaint_ms = (time.perf_counter() - start) / 20 * 1000

    assert per_repaint_ms < 3.0, f"queue repaint took {per_repaint_ms:.2f} ms"


def test_first_result_batch_stays_under_400_ms(stack):
    cards = stack.window._results_cards
    videos = _videos(50)

    start = time.perf_counter()
    cards.update_results(videos)
    first_batch_ms = (time.perf_counter() - start) * 1000

    assert first_batch_ms < 400, f"first batch took {first_batch_ms:.0f} ms"
