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