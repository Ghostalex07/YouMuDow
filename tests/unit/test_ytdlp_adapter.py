"""Tests for ytdlp adapter."""

import io
import os
import subprocess
import tempfile
import threading
from unittest.mock import Mock, patch

import pytest

from youmudow.adapters.ytdlp_adapter import (
    YtdlpAdapter,
    YtdlpConfig,
)
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video


@pytest.fixture
def adapter():
    """Create adapter with default config."""
    return YtdlpAdapter(YtdlpConfig())


@pytest.fixture
def sample_video():
    """Create a sample video for testing."""
    return Video(
        title="Test Song",
        url="https://youtube.com/watch?v=test123",
        uploader="Test Artist",
        duration=180,
        options=DownloadOptions(file_format="mp3"),
    )


class TestYtdlpConfig:
    """Tests for YtdlpConfig."""

    def test_default_values(self):
        config = YtdlpConfig()
        assert config.output_template == "%(title)s.%(ext)s"
        assert config.audio_format == "mp3"
        assert config.download_timeout == 300
        assert config.max_retries == 2
        assert config.embed_metadata is True

    def test_custom_values(self):
        config = YtdlpConfig(
            output_template="%(title)s.%(ext)s",
            download_timeout=600,
            max_retries=3,
            embed_metadata=False,
        )
        assert config.download_timeout == 600
        assert config.max_retries == 3
        assert config.embed_metadata is False


class TestYtdlpAdapter:
    """Tests for YtdlpAdapter."""

    def test_set_log_callback(self, adapter):
        callback = Mock()
        adapter.set_log_callback(callback)
        assert adapter._log_callback is callback


class TestBuildArgs:
    """Tests for argument building."""

    def test_base_args_basic(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(file_format="mp3"),
        )
        args = adapter._build_base_args(video)
        assert "yt-dlp" in args
        assert "--no-check-certificate" in args
        assert "https://youtube.com/watch?v=test" not in args

    def test_cookies_from_browser(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(
                use_cookies=True,
                cookies_from_browser="firefox",
                cookies_profile="default",
            ),
        )
        args = adapter._build_base_args(video)
        assert "--cookies-from-browser" in args
        assert "firefox" in args

    def test_cookies_from_browser_with_profile(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(
                use_cookies=True,
                cookies_from_browser="firefox",
                cookies_profile="my-profile",
            ),
        )
        args = adapter._build_base_args(video)
        assert "firefox:my-profile" in args

    def test_cookies_from_file(self, adapter):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"# Netscape HTTP Cookie File")
            temp_file = f.name

        try:
            video = Video(
                title="Test",
                url="https://youtube.com/watch?v=test",
                uploader="Test",
                duration=60,
                options=DownloadOptions(
                    use_cookies=True,
                    cookies_file=temp_file,
                    cookies_from_browser=None,
                ),
            )
            args = adapter._build_base_args(video)
            assert "--cookies" in args
            assert temp_file in args
        finally:
            os.unlink(temp_file)

    def test_cookies_from_nonexistent_file(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(
                use_cookies=True,
                cookies_file="/nonexistent/cookies.txt",
                cookies_from_browser=None,
            ),
        )
        args = adapter._build_base_args(video)
        assert "--cookies" not in args

    def test_no_cookies_when_disabled(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(use_cookies=False),
        )
        args = adapter._build_base_args(video)
        assert "--cookies-from-browser" not in args
        assert "--cookies" not in args

    def test_skip_cookies_flag(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(
                use_cookies=True,
                cookies_from_browser="firefox",
            ),
        )
        args = adapter._build_base_args(video, skip_cookies=True)
        assert "--cookies-from-browser" not in args


class TestBuildDownloadArgs:
    """Tests for download argument building."""

    def test_format_mp3(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(file_format="mp3", quality="320kbps"),
        )
        args = adapter._build_download_args(video)
        assert "--extract-audio" in args
        assert "--audio-format" in args
        assert "mp3" in args

    def test_format_mp4(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(file_format="mp4", quality="1080p"),
        )
        args = adapter._build_download_args(video)
        assert "-f" in args

    def test_rate_limit_option(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(file_format="mp3", rate_limit="1M"),
        )
        args = adapter._build_download_args(video)
        assert "--limit-rate" in args
        assert "1M" in args

    def test_split_chapters_option(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(file_format="mp4", split_chapters=True),
        )
        args = adapter._build_download_args(video)
        assert "--split-chapters" in args

    def test_subtitles_option(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            uploader="Test",
            duration=60,
            options=DownloadOptions(
                file_format="mp3",
                subtitles=True,
                subtitle_lang="en,es",
                embed_subtitles=True,
            ),
        )
        args = adapter._build_download_args(video)
        assert "--write-subs" in args
        assert "--sub-langs" in args
        assert "en,es" in args
        assert "--embed-subs" in args


class TestFormatSelectors:
    """Tests for format selector generation."""

    def test_mp3_selector(self, adapter):
        selector = adapter._get_format_selector("mp3", "best")
        assert selector == "bestaudio/best"

    def test_mp4_1080p_selector(self, adapter):
        selector = adapter._get_format_selector("mp4", "1080p")
        assert "1080" in selector

    def test_audio_quality(self, adapter):
        assert adapter._get_audio_quality("320kbps") == "0"
        assert adapter._get_audio_quality("128kbps") == "3"
        assert adapter._get_audio_quality("96kbps") == "4"


class TestProgressParsing:
    """Tests for progress parsing."""

    def test_parse_progress_with_size(self):
        a = YtdlpAdapter()
        info = a._parse_progress("[download] 50.0% of ~10.0MiB at 1.0MiB/s ETA 00:30")
        assert info is not None
        assert info.progress == 50.0

    def test_parse_progress_without_size(self):
        a = YtdlpAdapter()
        info = a._parse_progress("[download] 75.0% at 2.0MiB/s ETA 00:15")
        assert info is not None
        assert info.progress == 75.0

    def test_parse_non_progress(self):
        a = YtdlpAdapter()
        info = a._parse_progress("[info] Downloading video")
        assert info is None


class TestDurationParsing:
    """Tests for duration parsing."""

    def test_parse_minutes(self):
        a = YtdlpAdapter()
        assert a._parse_duration("3:45") == 225

    def test_parse_hours(self):
        a = YtdlpAdapter()
        assert a._parse_duration("1:30:45") == 5445

    def test_parse_seconds(self):
        a = YtdlpAdapter()
        assert a._parse_duration("90") == 90

    def test_parse_invalid(self):
        a = YtdlpAdapter()
        assert a._parse_duration("invalid") == 0
        assert a._parse_duration("") == 0
        assert a._parse_duration(None) == 0


class TestBuildDownloadArgsSubtitles:
    """Tests for subtitle argument building in download args."""

    def test_embed_subs_from_config_includes_write_subs(self):
        """embed_subs from YtdlpConfig must include --write-subs or it's a no-op."""
        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter, YtdlpConfig
        from youmudow.domain.models import DownloadOptions, Video

        config = YtdlpConfig(embed_subs=True)
        adapter = YtdlpAdapter(config=config)

        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=x",
            options=DownloadOptions(subtitles=False),
        )
        args = adapter._build_download_args(video)

        if "--embed-subs" in args:
            assert "--write-subs" in args, (
                "--embed-subs added without --write-subs: yt-dlp will ignore it silently"
            )

    def test_subtitles_true_includes_write_subs(self):
        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
        from youmudow.domain.models import DownloadOptions, Video

        adapter = YtdlpAdapter()
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=x",
            options=DownloadOptions(subtitles=True, subtitle_lang="es"),
        )
        args = adapter._build_download_args(video)

        assert "--write-subs" in args
        assert "--sub-langs" in args
        idx = args.index("--sub-langs")
        assert args[idx + 1] == "es"

    def test_embed_subtitles_requires_subtitles_true(self):
        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
        from youmudow.domain.models import DownloadOptions, Video

        adapter = YtdlpAdapter()
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=x",
            options=DownloadOptions(subtitles=True, embed_subtitles=True),
        )
        args = adapter._build_download_args(video)

        assert "--write-subs" in args
        assert "--embed-subs" in args


class TestSearchErrorHandling:
    def test_search_logs_error_on_nonzero_returncode(self):
        from unittest.mock import Mock, patch

        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter

        adapter = YtdlpAdapter()
        logs = []
        adapter.set_log_callback(logs.append)

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ERROR: SSL certificate failed"

        with patch("subprocess.run", return_value=mock_result):
            results = adapter.search("test query")

        assert results == []
        assert any("error" in log.lower() or "SSL" in log for log in logs), (
            f"Error not logged. Logs: {logs}"
        )

    def test_get_metadata_logs_error_on_nonzero_returncode(self):
        from unittest.mock import Mock, patch

        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter

        adapter = YtdlpAdapter()
        logs = []
        adapter.set_log_callback(logs.append)

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ERROR: Video unavailable"

        with patch("subprocess.run", return_value=mock_result):
            result = adapter.get_metadata("https://youtube.com/watch?v=test")

        assert result is None
        assert any("error" in log.lower() or "unavailable" in log.lower() for log in logs), (
            f"Error not logged. Logs: {logs}"
        )


class TestParseYtDlpError:
    """Tests for yt-dlp error parsing."""

    def test_empty_output(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("") == "Download failed"

    def test_private_video(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("ERROR: This video is private") == "Video is private"

    def test_region_block(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert (
            parse_yt_dlp_error("The uploader has not made this video available in your region")
            == "Video not available in your region"
        )

    def test_cookie_not_found(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert (
            parse_yt_dlp_error("ERROR: could not find chrome cookies")
            == "Chrome cookies not found - is Chrome installed?"
        )

    def test_cookie_locked(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        result = parse_yt_dlp_error("ERROR: cookies database is locked")
        assert "locked" in result.lower()

    def test_generic_failure(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("ERROR: Something totally unexpected") == "Download failed"

    def test_cookie_error_parsing(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert parse_cookie_error("profile not accessible") == "Browser profile not accessible"


class TestResolveOutputFile:
    """Tests for resolving the actual downloaded file."""

    def test_returns_most_recent_match(self, tmp_path):
        import os

        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter

        (tmp_path / "Song.mp3").write_text("x")
        (tmp_path / "Song.mp4").write_text("y")
        os.utime(tmp_path / "Song.mp3", (1_600_000_000, 1_600_000_000))
        os.utime(tmp_path / "Song.mp4", (1_700_000_000, 1_700_000_000))
        adapter = YtdlpAdapter()
        result = adapter._resolve_output_file(tmp_path, "Song")
        assert result == tmp_path / "Song.mp4"

    def test_returns_none_when_no_match(self, tmp_path):
        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter

        adapter = YtdlpAdapter()
        assert adapter._resolve_output_file(tmp_path, "Nothing") is None


class TestDownloadCancel:
    """Tests for download cancellation."""

    def test_cancelled_before_start(self, tmp_path, sample_video):
        import threading

        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
        from youmudow.domain.enums import DownloadStatus

        cancel_event = threading.Event()
        cancel_event.set()
        adapter = YtdlpAdapter()
        result = adapter.download(sample_video, tmp_path, cancel_event=cancel_event)
        assert result.status == DownloadStatus.CANCELLED

    def test_file_not_resolved_when_cancelled(self, tmp_path, sample_video):
        import threading

        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter
        from youmudow.domain.enums import DownloadStatus

        cancel_event = threading.Event()
        cancel_event.set()
        adapter = YtdlpAdapter()
        result = adapter.download(sample_video, tmp_path, cancel_event=cancel_event)
        assert result.path == tmp_path
        assert result.status == DownloadStatus.CANCELLED


class TestParseCookieError:
    """Tests for cookie error parsing."""

    def test_browser_cookies_not_found(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert (
            parse_cookie_error("ERROR: could not find firefox cookies")
            == "Firefox cookies not found - is Firefox installed?"
        )

    def test_generic_not_found(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert parse_cookie_error("ERROR: something not found") == "Browser cookies not found"

    def test_locked(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert (
            parse_cookie_error("ERROR: cookies are locked")
            == "Cookies locked - browser may be running"
        )

    def test_profile(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert (
            parse_cookie_error("ERROR: profile not accessible") == "Browser profile not accessible"
        )

    def test_database(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert (
            parse_cookie_error("ERROR: database corrupted")
            == "Cookies database corrupted or inaccessible"
        )

    def test_directory(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert (
            parse_cookie_error("ERROR: no such file or directory")
            == "Browser profile directory not found"
        )

    def test_unknown(self):
        from youmudow.adapters.ytdlp_adapter import parse_cookie_error

        assert parse_cookie_error("ERROR: something else") == "Cookie authentication failed"


class TestParseYtDlpErrorExtended:
    """More error-parsing cases."""

    def test_region_japanese(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("この動画は地域制限") == "Video not available in your region"

    def test_connection_error(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("ERROR: network connection error") == "Connection error"

    def test_removed(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("ERROR: video has been removed") == "Video has been removed"

    def test_permission_denied(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("ERROR: permission denied") == "Permission denied"

    def test_auth_required(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("ERROR: please sign in") == "Authentication required"

    def test_captcha(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert parse_yt_dlp_error("ERROR: captcha required") == "CAPTCHA required"

    def test_cookie_delegation(self):
        from youmudow.adapters.ytdlp_adapter import parse_yt_dlp_error

        assert (
            parse_yt_dlp_error("ERROR: could not find chrome cookies")
            == "Chrome cookies not found - is Chrome installed?"
        )


class TestBuildBaseArgsFallbacks:
    """Fallback and config-level argument building."""

    def _adapter_with_config(self, **kwargs):
        return YtdlpAdapter(YtdlpConfig(**kwargs))

    def test_ffmpeg_and_user_agent(self):
        adapter = self._adapter_with_config(ffmpeg_location="/usr/bin", user_agent="UA/1.0")
        args = adapter._build_base_args()
        assert "--ffmpeg-location" in args
        assert "/usr/bin" in args
        assert "--user-agent" in args
        assert "UA/1.0" in args

    def test_config_cookies_file_without_video(self):
        adapter = self._adapter_with_config(cookies_file="/tmp/cookies.txt")
        args = adapter._build_base_args()
        assert "--cookies" in args

    def test_config_cookies_file_skipped(self):
        adapter = self._adapter_with_config(cookies_file="/tmp/cookies.txt")
        args = adapter._build_base_args(skip_cookies=True)
        assert "--cookies" not in args

    def test_browser_fallback(self):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(use_cookies=True, cookies_from_browser="chrome"),
        )
        adapter = YtdlpAdapter()
        logs = []
        adapter.set_log_callback(logs.append)
        with (
            patch(
                "youmudow.adapters.ytdlp_adapter.check_browser_profile",
                return_value=(False, "chrome not installed"),
            ),
            patch(
                "youmudow.adapters.ytdlp_adapter.get_fallback_browser",
                return_value="firefox",
            ),
        ):
            args = adapter._build_base_args(video)
        assert "--cookies-from-browser" in args
        assert "firefox" in args
        assert any("Falling back to Firefox" in log for log in logs)

    def test_fallback_equals_browser_no_change(self):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(use_cookies=True, cookies_from_browser="firefox"),
        )
        adapter = YtdlpAdapter()
        with (
            patch(
                "youmudow.adapters.ytdlp_adapter.check_browser_profile",
                return_value=(False, "not installed"),
            ),
            patch(
                "youmudow.adapters.ytdlp_adapter.get_fallback_browser",
                return_value="firefox",
            ),
        ):
            args = adapter._build_base_args(video)
        assert "firefox" in args

    def test_default_profile_has_no_suffix(self):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(
                use_cookies=True,
                cookies_from_browser="firefox",
                cookies_profile="main",
            ),
        )
        adapter = YtdlpAdapter()
        with patch(
            "youmudow.adapters.ytdlp_adapter.check_browser_profile",
            return_value=(True, ""),
        ):
            args = adapter._build_base_args(video)
        assert "--cookies-from-browser" in args
        assert "firefox:main" not in args


class TestBuildDownloadArgsExtended:
    """Metadata, chapters and subtitle options."""

    def test_embed_thumbnail_for_mp3(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp3"),
        )
        args = adapter._build_download_args(video)
        assert "--embed-thumbnail" in args

    def test_no_embed_thumbnail_for_mp4(self, adapter):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp4"),
        )
        args = adapter._build_download_args(video)
        assert "--embed-thumbnail" not in args

    def test_embed_chapters(self, adapter):
        adapter._config.add_chapters = True
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp4"),
        )
        args = adapter._build_download_args(video)
        assert "--embed-chapters" in args

    def test_parse_metadata(self, adapter):
        adapter._config.parse_metadata = "title:%(title)s"
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp3"),
        )
        args = adapter._build_download_args(video)
        assert "--parse-metadata" in args

    def test_metadata_from_title(self, adapter):
        adapter._config.metadata_from_title = "artist - title"
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp3"),
        )
        args = adapter._build_download_args(video)
        assert "--metadata-from-title" in args

    def test_config_embed_subs_without_options(self, adapter):
        adapter._config.embed_subs = True
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp4", subtitles=False),
        )
        args = adapter._build_download_args(video)
        assert "--write-subs" in args
        assert "--embed-subs" in args


class TestFormatSelectorsExtended:
    """Additional format selector cases."""

    def test_audio_quality_default(self, adapter):
        assert adapter._get_audio_quality("best") == "0"
        assert adapter._get_audio_quality("192kbps") == "2"
        assert adapter._get_audio_quality("") == "0"

    def test_video_unknown_quality(self, adapter):
        selector = adapter._get_format_selector("mp4", "8k")
        assert selector == "bestvideo+bestaudio/best"

    def test_video_known_quality(self, adapter):
        assert (
            adapter._get_format_selector("mp4", "720p") == "bestvideo[height<=720]+bestaudio/best"
        )


class TestSearch:
    """Search subprocess handling."""

    def test_parses_results(self, adapter):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "https://a.com | Song A | Artist A | 3:45\nhttps://b.com | Song B | Artist B | 90\n"
        )
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            results = adapter.search("query")
        assert len(results) == 2
        assert results[0].title == "Song A"
        assert results[0].duration == 225
        assert results[1].duration == 90

    def test_ignores_malformed_lines(self, adapter):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "no pipes here\nurl | Title | OnlyThree\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            results = adapter.search("query")
        assert results == []

    def test_timeout_returns_empty(self, adapter):
        logs = []
        adapter.set_log_callback(logs.append)
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("yt-dlp", 30),
        ):
            results = adapter.search("query")
        assert results == []
        assert any("error" in log.lower() or "timeout" in log.lower() for log in logs)

    def test_binary_missing_returns_empty(self, adapter):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            results = adapter.search("query")
        assert results == []


class TestGetMetadata:
    """Metadata subprocess handling."""

    def test_success(self, adapter):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            '{"title": "Song", "uploader": "Artist", "duration": 120, "thumbnail": "th"}'
        )
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            video = adapter.get_metadata("https://youtube.com/watch?v=test")
        assert video is not None
        assert video.title == "Song"
        assert video.uploader == "Artist"
        assert video.duration == 120
        assert video.thumbnail == "th"

    def test_empty_stdout_returns_none(self, adapter):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            assert adapter.get_metadata("https://youtube.com/watch?v=test") is None

    def test_invalid_json_returns_none(self, adapter):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            assert adapter.get_metadata("https://youtube.com/watch?v=test") is None

    def test_timeout_returns_none(self, adapter):
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("yt-dlp", 60),
        ):
            assert adapter.get_metadata("https://youtube.com/watch?v=test") is None


class TestGetPlaylistVideos:
    """Playlist fetching handling."""

    def _result(self, n):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(
            f"https://a{i}.com | Song {i} | Artist {i} | 90" for i in range(n)
        )
        mock_result.stderr = ""
        return mock_result

    def test_parses_and_truncates(self, adapter):
        logs = []
        adapter.set_log_callback(logs.append)
        with patch("subprocess.run", return_value=self._result(8)):
            videos = adapter.get_playlist_videos("https://youtube.com/playlist?list=abc", limit=3)
        assert len(videos) == 3
        assert any("truncated" in log.lower() for log in logs)

    def test_empty_stdout(self, adapter):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            assert adapter.get_playlist_videos("https://youtube.com/playlist?list=abc") == []

    def test_error_returns_empty(self, adapter):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert adapter.get_playlist_videos("https://youtube.com/playlist?list=abc") == []


class TestLogDownloadMessages:
    """Download start/success logging."""

    def test_log_start_embeds_metadata_and_thumbnail(self, adapter):
        logs = []
        adapter.set_log_callback(logs.append)
        video = Video(
            title="Song",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp3"),
        )
        adapter._log_download_start(video, "mp3")
        joined = "\n".join(logs)
        assert "[METADATA] Embedding: metadata, thumbnail" in joined

    def test_log_start_subtitles(self, adapter):
        logs = []
        adapter.set_log_callback(logs.append)
        video = Video(
            title="Song",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp3", subtitles=True, embed_subtitles=True),
        )
        adapter._log_download_start(video, "mp3")
        joined = "\n".join(logs)
        assert "[SUB] Downloading subtitles (en)" in joined
        assert "[SUB] Embedding subtitles in file" in joined

    def test_log_success(self, adapter):
        logs = []
        adapter.set_log_callback(logs.append)
        video = Video(
            title="Song",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(file_format="mp3"),
        )
        adapter._log_download_success(video, "mp3")
        joined = "\n".join(logs)
        assert "[DONE] Song" in joined


class TestIsCookieError:
    """Cookie error detection."""

    def test_matches(self, adapter):
        assert adapter._is_cookie_error("ERROR: could not find chrome cookies")
        assert adapter._is_cookie_error("cookies database locked")
        assert adapter._is_cookie_error("brave profile not found")

    def test_does_not_match(self, adapter):
        assert not adapter._is_cookie_error("ERROR: network timeout")


class FakeProcess:
    """Minimal fake subprocess for testing _run_process."""

    def __init__(self, lines, returncode):
        self._lines = lines
        self.returncode = returncode
        self.timeout_wait = False
        self.terminated = False
        self.killed = False
        self.stdout = io.StringIO("\n".join(lines) + ("\n" if lines else ""))

    def wait(self, timeout=None):
        if self.timeout_wait:
            raise subprocess.TimeoutExpired("yt-dlp", timeout)
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class TestRunProcess:
    """The yt-dlp subprocess runner."""

    def test_success_streams_and_parses_progress(self, tmp_path, sample_video):
        adapter = YtdlpAdapter(YtdlpConfig(download_timeout=30))
        progress = []
        lines = [
            "[download] 50.0% of ~10.0MiB at 1.2MiB/s ETA 00:30",
            "[error] something bad",
            "[info] finished",
        ]
        fake = FakeProcess(lines, 0)
        with patch("subprocess.Popen", return_value=fake):
            code, errors = adapter._run_process(
                ["yt-dlp"],
                tmp_path,
                sample_video,
                None,
                lambda p, s: progress.append((p, s)),
            )
        assert code == 0
        assert errors == ["[error] something bad"]
        assert progress == [(50.0, "1.2MiB/s")]

    def test_missing_binary_raises(self, tmp_path, sample_video):
        from youmudow.domain.exceptions import YtDlpNotFoundError

        adapter = YtdlpAdapter()
        with (
            patch("subprocess.Popen", side_effect=FileNotFoundError),
            pytest.raises(YtDlpNotFoundError),
        ):
            adapter._run_process(["yt-dlp"], tmp_path, sample_video, None, None)

    def test_timeout_returns_marker(self, tmp_path, sample_video):
        adapter = YtdlpAdapter()
        fake = FakeProcess([], 0)
        fake.timeout_wait = True
        with patch("subprocess.Popen", return_value=fake):
            code, _ = adapter._run_process(["yt-dlp"], tmp_path, sample_video, None, None)
        assert code == -2
        assert fake.killed

    def test_cancel_terminates_process(self, tmp_path, sample_video):
        adapter = YtdlpAdapter()
        cancel = threading.Event()
        cancel.set()
        fake = FakeProcess(["line1"], 5)
        with patch("subprocess.Popen", return_value=fake):
            _, _ = adapter._run_process(["yt-dlp"], tmp_path, sample_video, cancel, None)
        assert fake.terminated


class TestDownloadFlows:
    """End-to-end download() flows with a mocked process runner."""

    def _download(self, video, tmp_path, adapter=None, cancel_event=None):
        adapter = adapter or YtdlpAdapter(YtdlpConfig(max_retries=2))
        return adapter.download(video, tmp_path, cancel_event=cancel_event)

    def test_success(self, tmp_path, sample_video):
        adapter = YtdlpAdapter()
        with patch.object(adapter, "_run_process", return_value=(0, [])):
            result = self._download(sample_video, tmp_path, adapter=adapter)
        assert result.status == DownloadStatus.DONE

    def test_retries_then_error(self, tmp_path, sample_video):
        adapter = YtdlpAdapter(YtdlpConfig(max_retries=2))
        with (
            patch("time.sleep") as sleep,
            patch.object(
                adapter, "_run_process", return_value=(1, ["ERROR: Video is private"])
            ) as run,
        ):
            result = self._download(sample_video, tmp_path, adapter=adapter)
        assert result.status == DownloadStatus.ERROR
        assert result.error_message == "Video is private"
        assert run.call_count == 2
        sleep.assert_called()

    def test_cookie_retry_without_auth(self, tmp_path):
        video = Video(
            title="Test",
            url="https://youtube.com/watch?v=test",
            options=DownloadOptions(use_cookies=True, cookies_from_browser="chrome"),
        )
        adapter = YtdlpAdapter(YtdlpConfig(max_retries=2))
        skipped = []

        def fake_build(video, skip_cookies=False):
            skipped.append(skip_cookies)
            return ["--cookies-from-browser"] if not skip_cookies else ["--no-cookies"]

        def fake_run(args, output_path, video, cancel_event, progress_callback):
            if "--cookies-from-browser" in args:
                return (1, ["ERROR: could not find chrome cookies"])
            return (0, [])

        with (
            patch.object(adapter, "_build_download_args", side_effect=fake_build),
            patch.object(adapter, "_run_process", side_effect=fake_run),
            patch("time.sleep"),
        ):
            result = self._download(video, tmp_path, adapter=adapter)
        assert result.status == DownloadStatus.DONE
        assert skipped == [False, True]

    def test_timeout_error(self, tmp_path, sample_video):
        adapter = YtdlpAdapter()
        with patch.object(adapter, "_run_process", return_value=(-2, [])):
            result = self._download(sample_video, tmp_path, adapter=adapter)
        assert result.status == DownloadStatus.ERROR
        assert result.error_message == "Download timed out"

    def test_cancelled_after_process(self, tmp_path, sample_video):
        adapter = YtdlpAdapter()
        cancel = threading.Event()

        def fake_run(*args, **kwargs):
            cancel.set()
            return (1, [])

        with patch.object(adapter, "_run_process", side_effect=fake_run):
            result = self._download(sample_video, tmp_path, adapter=adapter, cancel_event=cancel)
        assert result.status == DownloadStatus.CANCELLED

    def test_ytdlp_error_raised(self, tmp_path, sample_video):
        from youmudow.domain.exceptions import YtDlpError

        adapter = YtdlpAdapter()
        with patch.object(adapter, "_run_process", side_effect=YtDlpError("boom")):
            result = self._download(sample_video, tmp_path, adapter=adapter)
        assert result.status == DownloadStatus.ERROR
        assert result.error_message == "boom"

    def test_unexpected_exception(self, tmp_path, sample_video):
        adapter = YtdlpAdapter()
        with patch.object(adapter, "_run_process", side_effect=RuntimeError("boom")):
            result = self._download(sample_video, tmp_path, adapter=adapter)
        assert result.status == DownloadStatus.ERROR
        assert result.error_message == "boom"

    def test_max_retries_one_no_retry(self, tmp_path, sample_video):
        adapter = YtdlpAdapter(YtdlpConfig(max_retries=1))
        with patch.object(
            adapter, "_run_process", return_value=(1, ["ERROR: private video"])
        ) as run:
            result = self._download(sample_video, tmp_path, adapter=adapter)
        assert result.status == DownloadStatus.ERROR
        assert run.call_count == 1
