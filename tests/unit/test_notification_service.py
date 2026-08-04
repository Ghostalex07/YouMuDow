"""Tests for desktop notifications."""

from unittest.mock import patch


class TestNotify:
    def test_linux_uses_notify_send(self):
        from youmudow.services.notification_service import notify

        with (
            patch("platform.system", return_value="Linux"),
            patch("subprocess.Popen") as mock_popen,
        ):
            notify("Title", "Message")
            mock_popen.assert_called_once()
            assert mock_popen.call_args[0][0] == ["notify-send", "Title", "Message"]

    def test_windows_without_plyer_is_silent(self):
        from youmudow.services.notification_service import notify

        with (
            patch("platform.system", return_value="Windows"),
            patch.dict("sys.modules", {"plyer": None}),
            patch("builtins.__import__", side_effect=ImportError("no plyer")),
        ):
            notify("Title", "Message")  # should not raise

    def test_subprocess_error_is_swallowed(self):
        from youmudow.services.notification_service import notify

        with (
            patch("platform.system", return_value="Linux"),
            patch("subprocess.Popen", side_effect=OSError("no display")),
        ):
            notify("Title", "Message")  # should not raise
