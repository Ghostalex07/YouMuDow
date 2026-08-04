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

    def test_macos_uses_osascript_with_escaped_message(self):
        from youmudow.services.notification_service import notify

        with (
            patch("platform.system", return_value="Darwin"),
            patch("subprocess.Popen") as mock_popen,
        ):
            notify('Say "hi"', "Line1\nLine2")
            args = mock_popen.call_args[0][0]
            assert args[0] == "osascript"
            assert args[1] == "-e"
            assert 'display notification "Line1\\nLine2" with title "Say \\"hi\\""' in args[2]

    def test_windows_with_plyer_calls_notify(self):
        from youmudow.services.notification_service import notify

        class FakeNotification:
            def notify(self, **kwargs): ...

        fake_notification = FakeNotification()

        class FakePlyer:
            notification = fake_notification

        with (
            patch("platform.system", return_value="Windows"),
            patch.dict(
                "sys.modules", {"plyer": FakePlyer(), "plyer.notification": fake_notification}
            ),
            patch.object(fake_notification, "notify") as mock_notify,
        ):
            notify("Title", "Message")
            mock_notify.assert_called_once_with(title="Title", message="Message", timeout=5)
