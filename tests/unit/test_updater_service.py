"""Tests for the yt-dlp updater service."""

from unittest.mock import Mock, patch


class TestGetYtdlpVersion:
    def test_returns_stdout_when_success(self):
        from youmudow.services.updater_service import get_ytdlp_version

        result = Mock()
        result.returncode = 0
        result.stdout = "2026.3.17\n"
        with patch("subprocess.run", return_value=result):
            assert get_ytdlp_version() == "2026.3.17"

    def test_returns_empty_when_nonzero(self):
        from youmudow.services.updater_service import get_ytdlp_version

        result = Mock()
        result.returncode = 1
        result.stdout = ""
        with patch("subprocess.run", return_value=result):
            assert get_ytdlp_version() == ""

    def test_returns_empty_on_error(self):
        from youmudow.services.updater_service import get_ytdlp_version

        with patch("subprocess.run", side_effect=OSError("missing")):
            assert get_ytdlp_version() == ""


class TestUpdateYtdlp:
    def test_success_calls_on_success(self):
        from youmudow.services.updater_service import update_ytdlp

        result = Mock()
        result.returncode = 0
        on_success = Mock()
        on_error = Mock()
        with (
            patch("subprocess.run", return_value=result),
            patch("youmudow.services.updater_service.get_ytdlp_version", return_value="2026.4.1"),
        ):
            update_ytdlp(on_success, on_error)
            import time

            deadline = time.time() + 3
            while on_success.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_called_once_with("2026.4.1")
        on_error.assert_not_called()

    def test_missing_binary_calls_on_error(self):
        from youmudow.services.updater_service import update_ytdlp

        on_success = Mock()
        on_error = Mock()
        with patch("subprocess.run", side_effect=FileNotFoundError("yt-dlp")):
            update_ytdlp(on_success, on_error)
            import time

            deadline = time.time() + 3
            while on_error.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_not_called()
        on_error.assert_called_once()

    def test_update_failure_falls_back_to_pip(self):
        from youmudow.services.updater_service import update_ytdlp

        fail_result = Mock()
        fail_result.returncode = 1
        fail_result.stderr = "boom"
        pip_result = Mock()
        pip_result.returncode = 0
        on_success = Mock()
        on_error = Mock()
        with (
            patch("subprocess.run", side_effect=[fail_result, pip_result]),
            patch("youmudow.services.updater_service.get_ytdlp_version", return_value="2026.4.1"),
        ):
            update_ytdlp(on_success, on_error)
            import time

            deadline = time.time() + 3
            while on_success.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_called_once_with("2026.4.1")
        on_error.assert_not_called()
