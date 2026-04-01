"""Tests for domain validators."""

import pytest
from youmudow.domain.validators import (
    is_valid_youtube_url,
    sanitize_filename,
    is_valid_format,
)


class TestIsValidYoutubeUrl:
    """Tests for URL validation."""

    def test_valid_watch_url(self):
        assert is_valid_youtube_url("https://www.youtube.com/watch?v=abc123")

    def test_valid_www_youtube_url(self):
        assert is_valid_youtube_url("https://youtube.com/watch?v=abc123")

    def test_valid_youtu_be_url(self):
        assert is_valid_youtube_url("https://youtu.be/abc123")

    def test_valid_short_url(self):
        assert is_valid_youtube_url("https://youtube.com/shorts/abc123")

    def test_valid_playlist_url(self):
        assert is_valid_youtube_url("https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")

    def test_valid_url_without_https(self):
        assert is_valid_youtube_url("youtube.com/watch?v=abc123")

    def test_invalid_url(self):
        assert not is_valid_youtube_url("https://example.com/video")

    def test_invalid_random_string(self):
        assert not is_valid_youtube_url("not a url")

    def test_empty_string(self):
        assert not is_valid_youtube_url("")

    def test_none_input(self):
        assert not is_valid_youtube_url(None)

    def test_whitespace_only(self):
        assert not is_valid_youtube_url("   ")


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_normal_filename(self):
        assert sanitize_filename("video.mp3") == "video.mp3"

    def test_removes_forward_slash(self):
        assert sanitize_filename("video/test.mp3") == "video_test.mp3"

    def test_removes_backward_slash(self):
        assert sanitize_filename("video\\test.mp3") == "video_test.mp3"

    def test_removes_colon(self):
        assert sanitize_filename("video:test.mp3") == "video_test.mp3"

    def test_removes_pipe(self):
        assert sanitize_filename("video|test.mp3") == "video_test.mp3"

    def test_removes_question_mark(self):
        assert sanitize_filename("video?test.mp3") == "video_test.mp3"

    def test_removes_asterisk(self):
        assert sanitize_filename("video*test.mp3") == "video_test.mp3"

    def test_removes_angle_brackets(self):
        assert sanitize_filename("video<test>.mp3") == "video_test_.mp3"

    def test_strips_whitespace(self):
        assert sanitize_filename("  video.mp3  ") == "video.mp3"

    def test_strips_leading_dot(self):
        assert sanitize_filename(".video.mp3") == "video.mp3"

    def test_empty_string_returns_untitled(self):
        assert sanitize_filename("") == "untitled"

    def test_whitespace_only_returns_untitled(self):
        assert sanitize_filename("   ") == "untitled"

    def test_custom_replacement(self):
        assert sanitize_filename("video/test.mp3", replacement="-") == "video-test.mp3"


class TestIsValidFormat:
    """Tests for format validation."""

    @pytest.mark.parametrize("fmt", ["mp3", "MP3", "mp4", "MP4", "wav", "flac", "aac", "m4a", "ogg"])
    def test_valid_formats(self, fmt):
        assert is_valid_format(fmt)

    @pytest.mark.parametrize("fmt", ["avi", "mkv", "mov", "wmv"])
    def test_invalid_formats(self, fmt):
        assert not is_valid_format(fmt)

    def test_empty_string(self):
        assert not is_valid_format("")

    def test_none_input(self):
        assert not is_valid_format(None)


class TestBrowserSupport:
    """Tests for browser and profile functionality."""

    def test_supported_browsers_constant(self):
        from youmudow.domain.validators import SUPPORTED_BROWSERS
        assert isinstance(SUPPORTED_BROWSERS, list)
        assert len(SUPPORTED_BROWSERS) == 7
        expected = ["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi"]
        assert SUPPORTED_BROWSERS == expected

    def test_get_available_browsers_returns_list(self):
        from youmudow.domain.validators import get_available_browsers
        result = get_available_browsers()
        assert isinstance(result, list)
        for browser in result:
            assert browser in ["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi"]

    def test_check_browser_profile_returns_tuple(self):
        from youmudow.domain.validators import check_browser_profile
        result = check_browser_profile("firefox")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_check_browser_profile_unknown(self):
        from youmudow.domain.validators import check_browser_profile
        exists, message = check_browser_profile("unknown_browser")
        assert exists is False
        assert "not installed" in message.lower() or "available" in message.lower()

    def test_get_fallback_browser_returns_or_none(self):
        from youmudow.domain.validators import get_fallback_browser
        result = get_fallback_browser()
        if result is not None:
            assert result in ["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi"]

    def test_get_all_browser_profiles_returns_dict(self):
        from youmudow.domain.validators import get_all_browser_profiles, SUPPORTED_BROWSERS
        result = get_all_browser_profiles()
        assert isinstance(result, dict)
        for browser, profiles in result.items():
            assert browser in SUPPORTED_BROWSERS
            assert isinstance(profiles, list)

    def test_browser_profile_dataclass(self):
        from youmudow.domain.validators import BrowserProfile
        profile = BrowserProfile(name="Default", path="/path/to/profile", browser="chrome")
        assert profile.name == "Default"
        assert profile.path == "/path/to/profile"
        assert profile.browser == "chrome"
