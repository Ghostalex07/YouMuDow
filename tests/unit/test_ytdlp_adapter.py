"""Tests for ytdlp adapter."""

import pytest
import tempfile
import os
from unittest.mock import Mock

from youmudow.adapters.ytdlp_adapter import (
    YtdlpAdapter,
    YtdlpConfig,
    create_adapter,
)
from youmudow.domain.models import Video, DownloadOptions


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

    def test_create_adapter(self):
        adapter = create_adapter(audio_format="flac", embed_metadata=False)
        assert adapter._config.audio_format == "flac"
        assert adapter._config.embed_metadata is False

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
        from youmudow.domain.models import Video, DownloadOptions

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
        from youmudow.domain.models import Video, DownloadOptions

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
        from youmudow.domain.models import Video, DownloadOptions

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
        from unittest.mock import patch, Mock
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
        from unittest.mock import patch, Mock
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
        from youmudow.domain.enums import DownloadStatus
        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter

        cancel_event = threading.Event()
        cancel_event.set()
        adapter = YtdlpAdapter()
        result = adapter.download(sample_video, tmp_path, cancel_event=cancel_event)
        assert result.status == DownloadStatus.CANCELLED

    def test_file_not_resolved_when_cancelled(self, tmp_path, sample_video):
        import threading
        from youmudow.domain.enums import DownloadStatus
        from youmudow.adapters.ytdlp_adapter import YtdlpAdapter

        cancel_event = threading.Event()
        cancel_event.set()
        adapter = YtdlpAdapter()
        result = adapter.download(sample_video, tmp_path, cancel_event=cancel_event)
        assert result.path == tmp_path
        assert result.status == DownloadStatus.CANCELLED
