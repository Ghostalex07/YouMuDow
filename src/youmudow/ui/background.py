"""Run work off the UI thread and deliver the result back on it.

Tkinter may only be touched from the main thread, so every background job in
the UI follows the same shape: do the slow thing in a worker, then hand the
result to ``MainWindow._schedule``. This module keeps that shape in one place
so a new job cannot forget the marshal step and call Tk from a worker.
"""

import logging
import threading
from collections.abc import Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class Scheduler(Protocol):
    def _schedule(self, callback: Callable[..., Any], *args: Any) -> None: ...


def run_in_background(
    owner: Scheduler,
    work: Callable[[], Any],
    on_result: Callable[[Any], None],
    *,
    on_error: Callable[[BaseException], None] | None = None,
    name: str | None = None,
) -> threading.Thread:
    """Run ``work`` in a daemon thread and call ``on_result`` on the Tk loop.

    Exceptions are logged and passed to ``on_error`` (also on the Tk loop), or
    swallowed with a log line when no handler is given: a background failure
    must never take the window down.
    """

    def runner() -> None:
        try:
            result = work()
        except BaseException as exc:
            logger.exception("Background job %s failed", name or "unnamed")
            if on_error is not None:
                owner._schedule(on_error, exc)
            return
        owner._schedule(on_result, result)

    thread = threading.Thread(target=runner, name=name, daemon=True)
    thread.start()
    return thread
