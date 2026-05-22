"""Tests for domain validators."""

from youmudow.domain.validators import (
    is_valid_youtube_url,
    sanitize_filename,
    is_playlist_url,
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


class TestRateLimit:
    """Tests for rate limit validation."""

    def test_valid_rate_limits(self):
        from youmudow.domain.validators import is_valid_rate_limit
        valid_rates = ["1M", "500K", "1G", "1024K", "10M", "1M", "100K", "500"]
        for rate in valid_rates:
            assert is_valid_rate_limit(rate), f"Expected {rate} to be valid"

    def test_invalid_rate_limits(self):
        from youmudow.domain.validators import is_valid_rate_limit
        invalid_rates = ["-1M", "abc", "10MB", "10MB/s", "abc123"]
        for rate in invalid_rates:
            assert not is_valid_rate_limit(rate), f"Expected {rate} to be invalid"

    def test_empty_rate_is_valid(self):
        from youmudow.domain.validators import is_valid_rate_limit
        assert is_valid_rate_limit("")
        assert is_valid_rate_limit("   ")

    def test_none_rate_is_invalid(self):
        from youmudow.domain.validators import is_valid_rate_limit
        assert not is_valid_rate_limit(None)


class TestBrowsersCache:
    def test_get_available_browsers_cached(self):
        from youmudow.domain import validators
        validators.invalidate_browsers_cache()

        call_count = [0]
        original = validators.check_browser_profile
        def counting_check(browser):
            call_count[0] += 1
            return original(browser)

        validators.check_browser_profile = counting_check
        try:
            r1 = validators.get_available_browsers()
            call_count[0] = 0

            r2 = validators.get_available_browsers()
            calls_second = call_count[0]

            assert r1 == r2
            assert calls_second == 0, f"Cache not used: {calls_second} calls"
        finally:
            validators.check_browser_profile = original
            validators.invalidate_browsers_cache()


class TestPlaylistURL:
    """Tests for playlist URL detection."""

    def test_playlist_url_with_www(self):
        assert is_playlist_url("https://www.youtube.com/playlist?list=PL123456")

    def test_playlist_url_without_www(self):
        assert is_playlist_url("https://youtube.com/playlist?list=PLabc")

    def test_playlist_url_with_https(self):
        assert is_playlist_url("https://www.youtube.com/playlist?list=PLxyz")

    def test_playlist_url_without_https(self):
        assert is_playlist_url("youtube.com/playlist?list=PLxyz")

    def test_regular_video_not_playlist(self):
        assert not is_playlist_url("https://www.youtube.com/watch?v=abc123")
        assert not is_playlist_url("https://youtu.be/abc123")
        assert not is_playlist_url("https://youtube.com/shorts/abc123")

    def test_empty_string_not_playlist(self):
        assert not is_playlist_url("")
        assert not is_playlist_url(None)

    def test_soundcloud_set_is_playlist(self):
        assert is_playlist_url("https://soundcloud.com/user/sets/set-name")

    def test_bandcamp_album_is_playlist(self):
        assert is_playlist_url("https://artist.bandcamp.com/album/album-name")

    def test_generic_playlist_path(self):
        assert is_playlist_url("https://example.com/playlist/abc123")

    def test_youtube_channel_videos(self):
        assert is_playlist_url("https://www.youtube.com/@channelname/videos")
        assert is_playlist_url("https://www.youtube.com/channel/UC123/videos")


