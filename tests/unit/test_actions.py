"""Tests for file dialogs and OS integration in the main window."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from youmudow.ui import actions


class TestChooseOutputFolder:
    def test_returns_selected_folder(self):
        with patch.object(actions.filedialog, "askdirectory", return_value="/home/user/Music"):
            assert actions.choose_output_folder() == "/home/user/Music"

    def test_returns_none_when_dialog_is_cancelled(self):
        with patch.object(actions.filedialog, "askdirectory", return_value=""):
            assert actions.choose_output_folder() is None


class TestExportLogs:
    def test_cancel_writes_nothing(self):
        log_terminal = Mock()
        set_status = Mock()

        with patch.object(actions.filedialog, "asksaveasfilename", return_value=""):
            actions.export_logs(log_terminal, set_status)

        log_terminal.export_to_file.assert_not_called()
        set_status.assert_not_called()

    def test_writes_logs_and_reports_path(self):
        log_terminal = Mock()
        set_status = Mock()

        with patch.object(
            actions.filedialog, "asksaveasfilename", return_value="/tmp/youmudow_logs.txt"
        ):
            actions.export_logs(log_terminal, set_status)

        log_terminal.export_to_file.assert_called_once_with(Path("/tmp/youmudow_logs.txt"))
        assert "Logs exported to /tmp/youmudow_logs.txt" == set_status.call_args.args[0]

    @pytest.mark.parametrize(
        "error", [OSError("disk full"), ValueError("closed file")], ids=["oserror", "valueerror"]
    )
    def test_write_failure_is_reported(self, error):
        log_terminal = Mock()
        log_terminal.export_to_file.side_effect = error
        set_status = Mock()

        with patch.object(actions.filedialog, "asksaveasfilename", return_value="/tmp/logs.txt"):
            actions.export_logs(log_terminal, set_status)

        message = set_status.call_args.args[0]
        assert message.startswith("Export failed")
        assert str(error) in message


class TestOpenOutputFolder:
    @pytest.mark.parametrize(
        ("system", "command"),
        [("Windows", "explorer"), ("Darwin", "open"), ("Linux", "xdg-open")],
    )
    def test_uses_platform_file_manager(self, system, command):
        path = Path("/tmp/output")

        with (
            patch.object(actions.platform, "system", return_value=system),
            patch.object(actions.subprocess, "Popen") as popen,
        ):
            assert actions.open_output_folder(path) is True

        popen.assert_called_once_with([command, str(path)])

    def test_returns_false_when_launch_fails(self):
        with (
            patch.object(actions.platform, "system", return_value="Linux"),
            patch.object(actions.subprocess, "Popen", side_effect=OSError("no xdg-open")),
        ):
            assert actions.open_output_folder(Path("/tmp/output")) is False
