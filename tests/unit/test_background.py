"""Tests for the UI background helper."""

import time
from unittest.mock import Mock

from youmudow.ui.background import run_in_background


class FakeOwner:
    def __init__(self):
        self.scheduled = []

    def _schedule(self, callback, *args):
        self.scheduled.append((callback, args))

    def drain(self):
        while self.scheduled:
            callback, args = self.scheduled.pop(0)
            callback(*args)


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def test_result_is_delivered_through_the_schedule_hook():
    owner = FakeOwner()
    seen = []
    run_in_background(owner, lambda: 21 * 2, seen.append, name="double")
    assert _wait_for(lambda: owner.scheduled)
    assert seen == []  # nothing delivered from the worker thread
    owner.drain()
    assert seen == [42]


def test_failures_go_to_the_error_handler_on_the_loop():
    owner = FakeOwner()
    errors = []

    def boom():
        raise RuntimeError("nope")

    run_in_background(owner, boom, lambda _result: None, on_error=errors.append)
    assert _wait_for(lambda: owner.scheduled)
    owner.drain()
    assert isinstance(errors[0], RuntimeError)


def test_missing_error_handler_does_not_raise():
    owner = FakeOwner()

    def boom():
        raise RuntimeError("nope")

    run_in_background(owner, boom, Mock())
    assert _wait_for(lambda: owner.scheduled) is False
