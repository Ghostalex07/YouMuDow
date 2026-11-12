"""Tests for the startup checks and yt-dlp maintenance actions.

Every function in ``youmudow.ui.startup_checks`` takes a ``schedule`` and a
``set_status`` callable, so these tests drive them with mocks instead of a Tk
main loop. Work spawned on background threads is awaited with an ``Event`` that
the mock sets, never with a sleep.
"""

import threading
import tkinter as tk
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("tkinter")

from youmudow import __version__
from youmudow.ui import startup_checks

TIMEOUT = 5


def _immediate_schedule() -> Mock:
    """A schedule mock that runs the callback right away, like ``after(0, ...)``."""
    return Mock(side_effect=lambda callback, *args: callback(*args))


def _recording_schedule() -> tuple[Mock, threading.Event]:
    """A schedule mock that signals an event on its first call."""
    called = threading.Event()
    schedule = Mock(side_effect=lambda *args, **kwargs: called.set())
    return schedule, called


class _FakeMessagebox:
    """Thread-safe stand-in for ``tkinter.messagebox``.

    ``show_ytdlp_version`` reads ``messagebox.showinfo`` on a daemon thread so it
    can hand it to the scheduler. ``unittest.mock.Mock`` is not safe there: its
    lazy ``__getattr__`` builds a child mock and binds ``inspect.signature``
    while a background thread can race garbage collection and abort the whole
    interpreter. A plain object with a real attribute has none of that.
    """

    @staticmethod
    def showinfo(*args: object, **kwargs: object) -> None:
        return None


class TestCheckClipboard:
    def _root(self, clipboard=None, error=None):
        root = Mock()
        if error is not None:
            root.clipboard_get.side_effect = error
        else:
            root.clipboard_get.return_value = clipboard
        return root

    def test_offers_supported_url_to_callback(self):
        root = self._root("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        on_supported = Mock()

        startup_checks.check_clipboard(root, on_supported)

        on_supported.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_strips_whitespace_before_offering_url(self):
        root = self._root("  https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")
        on_supported = Mock()

        startup_checks.check_clipboard(root, on_supported)

        on_supported.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_ignores_unsupported_clipboard_text(self):
        root = self._root("just some copied text")
        on_supported = Mock()

        startup_checks.check_clipboard(root, on_supported)

        on_supported.assert_not_called()

    def test_ignores_empty_clipboard(self):
        root = self._root("")
        on_supported = Mock()

        startup_checks.check_clipboard(root, on_supported)

        on_supported.assert_not_called()

    def test_swallows_clipboard_errors(self):
        root = self._root(error=tk.TclError("CLIPBOARD selection doesn't exist"))
        on_supported = Mock()

        startup_checks.check_clipboard(root, on_supported)

        on_supported.assert_not_called()


class TestCheckYtdlp:
    def test_missing_version_schedules_not_found_status(self):
        schedule, called = _recording_schedule()
        set_status = Mock()

        with patch.object(startup_checks, "get_ytdlp_version", return_value=""):
            startup_checks.check_ytdlp(schedule, set_status)
            assert called.wait(TIMEOUT)

        scheduled = schedule.call_args
        assert scheduled.args[0] is set_status
        assert "not found" in scheduled.args[1]

    def test_present_version_starts_environment_check(self):
        schedule, _ = _recording_schedule()
        set_status = Mock()
        started = threading.Event()
        run_check = Mock(side_effect=lambda *args: started.set())

        with (
            patch.object(startup_checks, "get_ytdlp_version", return_value="2026.01.01"),
            patch.object(startup_checks, "run_environment_check", run_check),
        ):
            startup_checks.check_ytdlp(schedule, set_status)
            assert started.wait(TIMEOUT)

        assert run_check.call_args.args == (schedule, set_status)


class TestRunEnvironmentCheck:
    def test_reports_ready_when_runtime_and_ejs_are_present(self):
        schedule = _immediate_schedule()
        set_status = Mock()
        repair = Mock()

        with (
            patch.object(startup_checks, "detect_js_runtime", return_value="deno"),
            patch.object(startup_checks, "is_ejs_installed", return_value=True),
            patch.object(startup_checks, "repair_youtube_environment", repair),
        ):
            startup_checks.run_environment_check(schedule, set_status)

        messages = [call.args[0] for call in set_status.call_args_list]
        assert any("YouTube ready" in message and "deno" in message for message in messages)
        assert not repair.called

    def test_installs_ejs_when_runtime_is_present_without_ejs(self):
        schedule = _immediate_schedule()
        set_status = Mock()
        repair = Mock()

        with (
            patch.object(startup_checks, "detect_js_runtime", return_value="node"),
            patch.object(startup_checks, "is_ejs_installed", return_value=False),
            patch.object(startup_checks, "repair_youtube_environment", repair),
        ):
            startup_checks.run_environment_check(schedule, set_status)

        messages = [call.args[0] for call in set_status.call_args_list]
        assert any("installing JS challenge scripts" in message for message in messages)
        repair.assert_called_once()

    def test_ejs_repair_callbacks_report_success_and_failure(self):
        schedule = _immediate_schedule()
        set_status = Mock()
        repair = Mock()

        with (
            patch.object(startup_checks, "detect_js_runtime", return_value="deno"),
            patch.object(startup_checks, "is_ejs_installed", return_value=False),
            patch.object(startup_checks, "repair_youtube_environment", repair),
        ):
            startup_checks.run_environment_check(schedule, set_status)

        repair.call_args.kwargs["on_success"]("yt-dlp[default] updated")
        repair.call_args.kwargs["on_error"]("pip exploded")

        messages = [call.args[0] for call in set_status.call_args_list]
        assert "Fix applied: yt-dlp[default] updated" in messages
        assert "Fix failed: pip exploded" in messages

    def test_warns_about_403_when_no_runtime_is_found(self):
        schedule = _immediate_schedule()
        set_status = Mock()
        repair = Mock()

        with (
            patch.object(startup_checks, "detect_js_runtime", return_value=None),
            patch.object(startup_checks, "is_ejs_installed", return_value=False),
            patch.object(startup_checks, "repair_youtube_environment", repair),
        ):
            startup_checks.run_environment_check(schedule, set_status)

        messages = [call.args[0] for call in set_status.call_args_list]
        assert any("403" in message and "deno" in message for message in messages)
        assert not repair.called


class TestRepairEnvironment:
    def test_reports_progress_then_result(self):
        schedule = _immediate_schedule()
        set_status = Mock()
        repair = Mock()

        with patch.object(startup_checks, "repair_youtube_environment", repair):
            startup_checks.repair_environment(schedule, set_status)

        assert "Repairing" in set_status.call_args_list[0].args[0]
        repair.assert_called_once()

        repair.call_args.kwargs["on_success"]("cache cleared")
        repair.call_args.kwargs["on_error"]("no network")

        messages = [call.args[0] for call in set_status.call_args_list]
        assert "Repair OK: cache cleared" in messages
        assert "Repair failed: no network" in messages


class TestInstallYtdlpUpdate:
    def test_reports_success(self):
        schedule = _immediate_schedule()
        set_status = Mock()
        update = Mock()

        with patch.object(startup_checks, "update_ytdlp", update):
            startup_checks.install_ytdlp_update(schedule, set_status)

        assert set_status.call_args_list[0].args[0] == "Updating yt-dlp..."
        update.assert_called_once()

        update.call_args.args[0]("2026.01.01")
        assert set_status.call_args.args[0] == "yt-dlp updated to 2026.01.01"

    def test_reports_failure(self):
        schedule = _immediate_schedule()
        set_status = Mock()
        update = Mock()

        with patch.object(startup_checks, "update_ytdlp", update):
            startup_checks.install_ytdlp_update(schedule, set_status)

        update.call_args.args[1]("pip is offline")

        assert set_status.call_args.args[0] == "Update failed: pip is offline"


class TestShowYtdlpVersion:
    def test_shows_installed_version(self):
        schedule, called = _recording_schedule()
        messagebox = _FakeMessagebox()

        with (
            patch.object(startup_checks, "messagebox", messagebox),
            patch.object(startup_checks, "get_ytdlp_version", return_value="2026.01.01"),
        ):
            startup_checks.show_ytdlp_version(schedule, Mock())
            assert called.wait(TIMEOUT)

        scheduled = schedule.call_args.args
        assert scheduled[0] is messagebox.showinfo
        assert scheduled[1] == "yt-dlp version"
        assert "2026.01.01" in scheduled[2]

    def test_shows_not_found_when_version_is_empty(self):
        schedule, called = _recording_schedule()

        with (
            patch.object(startup_checks, "messagebox", _FakeMessagebox()),
            patch.object(startup_checks, "get_ytdlp_version", return_value=""),
        ):
            startup_checks.show_ytdlp_version(schedule, Mock())
            assert called.wait(TIMEOUT)

        assert "not found" in schedule.call_args.args[2]


class TestShowAbout:
    def test_shows_version_and_repository(self):
        schedule, called = _recording_schedule()
        messagebox = Mock()

        with (
            patch.object(startup_checks, "messagebox", messagebox),
            patch.object(startup_checks, "get_ytdlp_version", return_value="2026.01.01"),
        ):
            startup_checks.show_about(schedule, Mock())
            assert called.wait(TIMEOUT)

        title, body = messagebox.showinfo.call_args.args
        assert title == "About YouMuDow"
        assert __version__ in body
        assert "github.com/Ghostalex07/YouMuDow" in body

    def test_refreshes_ytdlp_status_after_dialog(self):
        schedule, called = _recording_schedule()
        set_status = Mock()

        with (
            patch.object(startup_checks, "messagebox", Mock()),
            patch.object(startup_checks, "get_ytdlp_version", return_value="2026.01.01"),
        ):
            startup_checks.show_about(schedule, set_status)
            assert called.wait(TIMEOUT)

        assert schedule.call_args.args == (set_status, "yt-dlp: 2026.01.01")
