"""Tests for the youmudow-cli entry point."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from youmudow.app.config import AppConfig
from youmudow.cli import _build_parser, _cmd_download, _cmd_search, main
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video
from youmudow.services.download_service import DownloadService
from youmudow.services.search_service import SearchService


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


def _done(video: Video) -> Video:
    video.status = DownloadStatus.DONE
    return video


class TestPlaylistDownload:
    def test_download_expands_playlists(self, monkeypatch, tmp_path, capsys):
        videos = [Video(title=f"V{i}", url=f"https://example.com/{i}") for i in range(2)]
        search = Mock()
        search.get_playlist.return_value = videos
        service = Mock()
        service.download_now.side_effect = lambda video, path, progress_callback=None: _done(video)
        monkeypatch.setattr("youmudow.cli.SearchService", lambda: search)
        monkeypatch.setattr("youmudow.cli.DownloadService", lambda: service)

        code = main(
            [
                "download",
                "https://www.youtube.com/@chan",
                "--limit",
                "2",
                "--output",
                str(tmp_path),
            ]
        )

        assert code == 0
        search.get_playlist.assert_called_once_with("https://www.youtube.com/@chan", 2)
        assert service.download_now.call_count == 2
        assert "Found 2 video(s)" in capsys.readouterr().out

    def test_playlist_with_one_failure_returns_one(self, monkeypatch, tmp_path, capsys):
        videos = [Video(title=f"V{i}", url=f"https://example.com/{i}") for i in range(2)]
        search = Mock()
        search.get_playlist.return_value = videos

        def download(video, path, progress_callback=None):
            video.status = DownloadStatus.ERROR if video.title == "V1" else DownloadStatus.DONE
            return video

        service = Mock()
        service.download_now.side_effect = download
        monkeypatch.setattr("youmudow.cli.SearchService", lambda: search)
        monkeypatch.setattr("youmudow.cli.DownloadService", lambda: service)

        code = main(["download", "https://www.youtube.com/@chan", "--output", str(tmp_path)])

        assert code == 1
        assert "[1/2] V0" in capsys.readouterr().out


def test_download_limit_is_capped_at_500(monkeypatch, tmp_path):
    search = Mock()
    search.get_playlist.return_value = []
    monkeypatch.setattr("youmudow.cli.SearchService", lambda: search)

    code = main(
        ["download", "https://www.youtube.com/@chan", "--limit", "9999", "--output", str(tmp_path)]
    )

    assert code == 1
    search.get_playlist.assert_called_once_with("https://www.youtube.com/@chan", 500)


def _playlist_args(tmp_path, limit):
    return _build_parser().parse_args(
        [
            "download",
            "https://youtube.com/playlist?list=abc",
            "--skip-metadata",
            "--output",
            str(tmp_path),
            "--limit",
            str(limit),
        ]
    )


def test_playlist_notice_says_when_the_limit_was_hit(monkeypatch, tmp_path, capsys):
    videos = [Video(title=f"V{i}", url=f"https://x.test/{i}") for i in range(3)]
    monkeypatch.setattr(SearchService, "get_playlist", lambda self, url, limit, start=1: videos)

    def done(self, video, out=None, **kw):
        return Video(title=video.title, url=video.url, status=DownloadStatus.DONE)

    monkeypatch.setattr(DownloadService, "download_now", done)

    _cmd_download(_playlist_args(tmp_path, 3), AppConfig())

    assert "limited to 3" in capsys.readouterr().out


def test_playlist_progress_line_is_closed_on_interrupt(monkeypatch, tmp_path, capsys):
    videos = [Video(title=f"V{i}", url=f"https://x.test/{i}") for i in range(2)]

    def boom(self, video, out=None, **kw):
        kw["progress_callback"](42.0, "")
        raise KeyboardInterrupt

    monkeypatch.setattr(SearchService, "get_playlist", lambda self, url, limit, start=1: videos)
    monkeypatch.setattr(DownloadService, "download_now", boom)

    assert _cmd_download(_playlist_args(tmp_path, 50), AppConfig()) == 130
    out = capsys.readouterr().out
    assert "42.0%" in out
    assert out.endswith("\n")


def test_serve_command_forwards_its_options(monkeypatch):
    from youmudow import cli, server

    seen = {}

    def fake_serve(**kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(server, "serve", fake_serve)
    args = cli._build_parser().parse_args(
        ["serve", "--port", "9100", "--token", "tok", "--output", "/tmp/out"]
    )
    assert cli.main(["serve", "--port", "9100", "--token", "tok", "--output", "/tmp/out"]) == 0
    assert seen["port"] == 9100
    assert seen["token"] == "tok"
    assert str(seen["output"]) == "/tmp/out"
    assert args.func is cli._cmd_serve


class _FakeDownloadService:
    def __init__(self, *args, **kwargs):
        self.downloaded = []

    def set_log_callback(self, callback):
        pass

    def download_now(self, video, output_dir, progress_callback=None):
        self.downloaded.append(video.url)
        return video


def test_download_from_file_skips_known_urls(tmp_path, monkeypatch, capsys):
    from youmudow import cli

    listing = tmp_path / "urls.txt"
    listing.write_text(
        "# comment\nhttps://x.test/a\nhttps://x.test/b\nhttps://x.test/b\nhttps://x.test/c\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "DownloadService", _FakeDownloadService)
    monkeypatch.setattr(cli, "_open_cli_store", lambda: _KnownStore({"https://x.test/b"}))

    code = cli.main(["download", "--from-file", str(listing), "--json", "--output", str(tmp_path)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["requested"] == 3
    assert payload["downloaded"] == 2
    assert payload["skipped"] == 1
    assert payload["failed"] == 0


class _KnownStore:
    def __init__(self, known):
        self._known = known

    def has_url(self, url):
        return url in self._known


def test_download_from_file_without_json_prints_a_summary(tmp_path, monkeypatch, capsys):
    from youmudow import cli

    listing = tmp_path / "urls.txt"
    listing.write_text("https://x.test/a\n", encoding="utf-8")
    monkeypatch.setattr(cli, "DownloadService", _FakeDownloadService)
    monkeypatch.setattr(cli, "_open_cli_store", lambda: None)

    code = cli.main(["download", "--from-file", str(listing), "--output", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "Downloaded 1" in out


def test_doctor_prints_the_report_and_exits_zero(monkeypatch, capsys):
    from youmudow import cli
    from youmudow.services import doctor

    monkeypatch.setattr(
        doctor, "run_checks", lambda output=None: [doctor.CheckResult("A", True, "fine")]
    )
    assert cli.main(["doctor"]) == 0
    assert "ok   A: fine" in capsys.readouterr().out


def test_doctor_exits_one_when_a_check_fails(monkeypatch, capsys):
    from youmudow import cli
    from youmudow.services import doctor

    monkeypatch.setattr(
        doctor, "run_checks", lambda output=None: [doctor.CheckResult("A", False, "broken")]
    )
    assert cli.main(["doctor"]) == 1
    assert "FAIL A: broken" in capsys.readouterr().out


def _seeded_store(tmp_path, monkeypatch):
    from youmudow import paths
    from youmudow.domain.models import HistoryEntry
    from youmudow.services.library_store import LibraryStore

    db = tmp_path / "lib.db"
    monkeypatch.setattr(paths, "database_file", lambda: db)
    store = LibraryStore(db)
    store.add_history(
        HistoryEntry(
            title="Song One",
            url="https://x.test/1",
            uploader="Chan",
            file_format="mp3",
            output_path=str(tmp_path / "one.mp3"),
            downloaded_at="2026-11-23T10:00:00+00:00",
            file_size_bytes=2048,
        )
    )
    return store


def test_history_prints_the_recent_downloads(tmp_path, monkeypatch, capsys):
    from youmudow import cli

    _seeded_store(tmp_path, monkeypatch).close()
    assert cli.main(["history"]) == 0
    out = capsys.readouterr().out
    assert "Song One" in out
    assert "2026-11-23" in out


def test_history_can_print_json(tmp_path, monkeypatch, capsys):
    from youmudow import cli

    _seeded_store(tmp_path, monkeypatch).close()
    assert cli.main(["history", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entries"][0]["title"] == "Song One"
    assert payload["entries"][0]["format"] == "mp3"


def test_search_can_print_json(monkeypatch, capsys):
    from youmudow import cli
    from youmudow.domain.models import Video

    monkeypatch.setattr(
        cli.SearchService,
        "search",
        lambda self, query, limit=10: [
            Video(title="Hit", url="https://x.test/hit", uploader="Chan", duration=42)
        ],
    )
    assert cli.main(["search", "hit", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["title"] == "Hit"
    assert payload["query"] == "hit"


def test_queue_lists_and_clears_the_saved_queue(tmp_path, monkeypatch, capsys):
    from youmudow import cli
    from youmudow.domain.models import Video
    from youmudow.services.queue_store import video_to_dict

    store = _seeded_store(tmp_path, monkeypatch)
    store.replace_queue([json.dumps(video_to_dict(Video(title="Later", url="https://x.test/l")))])
    store.close()

    assert cli.main(["queue"]) == 0
    assert "Later" in capsys.readouterr().out

    assert cli.main(["queue", "--clear"]) == 0
    assert "cleared" in capsys.readouterr().out.lower()

    assert cli.main(["queue", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"queue": []}
