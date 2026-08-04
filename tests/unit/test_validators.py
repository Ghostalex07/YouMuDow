"""Tests for domain validators."""

from youmudow.domain.validators import (
    is_playlist_url,
    is_valid_youtube_url,
    sanitize_filename,
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
        assert is_valid_youtube_url(
            "https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        )

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
