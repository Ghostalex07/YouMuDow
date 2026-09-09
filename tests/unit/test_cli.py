"""Tests for the youmudow-cli entry point."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from youmudow.cli import _build_parser, _cmd_download, _cmd_search, main
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video


@pytest.fixture
def config():
    cfg = Mock()
    cfg.output_path = Path("/tmp/youmudow-cli-test")
    cfg.to_download_options.return_value = DownloadOptions()
    return cfg


@pytest.fixture
def video():
    return Video(title="Sample", url="https://example.com/video")


class TestParser:
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        assert "youmudow-cli" in capsys.readouterr().out

    def test_missing_command_is_error(self):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2

    def test_parser_has_download_and_search(self):
        parser = _build_parser()
        choices = parser._subparsers._group_actions[0].choices
        assert {"download", "search"} <= set(choices)


class TestCmdDownload:
    def test_success_downloads_via_service(self, config, video):
        done = Video(
            title="Sample",
            url=video.url,
            status=DownloadStatus.DONE,
            path=Path("/tmp/youmudow-cli-test/sample.mp3"),
        )
        with (
            patch("youmudow.cli.SearchService") as mock_search_cls,
            patch("youmudow.cli.DownloadService") as mock_service_cls,
        ):
            mock_search_cls.return_value.get_metadata.return_value = video
            mock_service_cls.return_value.download_now.return_value = done
            args = _build_parser().parse_args(["download", video.url, "--format", "flac"])

            code = _cmd_download(args, config)

        assert code == 0
        service = mock_service_cls.return_value
        service.set_log_callback.assert_called_once()
        assert service.download_now.call_args.args[0] is video
        assert service.download_now.call_args.args[1] == config.output_path
        assert video.options.file_format == "flac"

    def test_failure_returns_nonzero(self, config, video):
        failed = Video(
            title="Sample", url=video.url, status=DownloadStatus.ERROR, error_message="boom"
        )
        with (
            patch("youmudow.cli.SearchService") as mock_search_cls,
            patch("youmudow.cli.DownloadService") as mock_service_cls,
        ):
            mock_search_cls.return_value.get_metadata.return_value = video
            mock_service_cls.return_value.download_now.return_value = failed
            args = _build_parser().parse_args(["download", video.url])

            code = _cmd_download(args, config)

        assert code == 1

    def test_skip_metadata_uses_url_as_title(self, config):
        url = "https://example.com/video"
        done = Video(title=url, url=url, status=DownloadStatus.DONE)
        with (
            patch("youmudow.cli.SearchService") as mock_search_cls,
            patch("youmudow.cli.DownloadService") as mock_service_cls,
        ):
            mock_service_cls.return_value.download_now.return_value = done
            args = _build_parser().parse_args(["download", url, "--skip-metadata"])

            code = _cmd_download(args, config)

        assert code == 0
        mock_search_cls.return_value.get_metadata.assert_not_called()

    def test_invalid_url_rejected_before_service(self, config, capsys):
        with (
            patch("youmudow.cli.SearchService") as mock_search_cls,
            patch("youmudow.cli.DownloadService") as mock_service_cls,
        ):
            args = _build_parser().parse_args(["download", "not a url", "--skip-metadata"])

            code = _cmd_download(args, config)

        assert code == 1
        mock_service_cls.return_value.download_now.assert_not_called()
        mock_search_cls.return_value.get_metadata.assert_not_called()
        assert "Invalid URL" in capsys.readouterr().err

    def test_unvalidated_video_url_accepted(self, config):
        # Unknown-but-plausible URLs are passed through to yt-dlp untouched.
        url = "https://bandcamp.com/track/random-id"
        done = Video(title=url, url=url, status=DownloadStatus.DONE)
        with (
            patch("youmudow.cli.SearchService") as mock_search_cls,
            patch("youmudow.cli.DownloadService") as mock_service_cls,
        ):
            mock_search_cls.return_value.get_metadata.return_value = done
            mock_service_cls.return_value.download_now.return_value = done
            args = _build_parser().parse_args(["download", url])

            code = _cmd_download(args, config)

        assert code == 0

    def test_keyboard_interrupt_returns_130(self, config, video):
        with (
            patch("youmudow.cli.SearchService") as mock_search_cls,
            patch("youmudow.cli.DownloadService") as mock_service_cls,
        ):
            mock_search_cls.return_value.get_metadata.return_value = video
            mock_service_cls.return_value.download_now.side_effect = KeyboardInterrupt
            args = _build_parser().parse_args(["download", video.url])

            code = _cmd_download(args, config)

        assert code == 130

    @pytest.mark.parametrize(
        "argv",
        [
            ["download", "https://example.com/v", "--format", "vob"],
            ["download", "https://example.com/v", "--format", "mp3", "--quality", "foo"],
            ["download", "https://example.com/v", "--format", "webm"],
        ],
    )
    def test_rejects_invalid_format_or_quality(self, argv):
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(argv)
        assert exc.value.code == 2

    def test_accepts_valid_format_and_quality(self):
        args = _build_parser().parse_args(
            ["download", "https://example.com/v", "--format", "mp3", "--quality", "320kbps"]
        )
        assert args.file_format == "mp3"
        assert args.quality == "320kbps"

    def test_search_limit_must_be_positive(self):
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["search", "song", "--limit", "0"])


class TestCmdSearch:
    def test_search_prints_results(self, config, capsys):
        results = [
            Video(title="First Song", url="https://example.com/1"),
            Video(title="Second Song", url="https://example.com/2"),
        ]
        with patch("youmudow.cli.SearchService") as mock_search_cls:
            mock_search_cls.return_value.search.return_value = results
            args = _build_parser().parse_args(["search", "song", "--limit", "2"])

            code = _cmd_search(args, config)

        assert code == 0
        mock_search_cls.return_value.search.assert_called_once_with("song", 2)
        out = capsys.readouterr().out
        assert "First Song" in out
        assert "Second Song" in out
        assert "2 result(s)" in out
