"""Tests for grouping download failures by cause."""

from youmudow.domain.error_causes import ErrorCause, classify_error, summarize_failures
from youmudow.domain.models import Video


def test_private_and_removed_videos_are_one_cause():
    assert classify_error("ERROR: Private video. Sign in if you've been granted access") is (
        ErrorCause.PRIVATE
    )
    assert classify_error("This video is unavailable") is ErrorCause.PRIVATE


def test_cookie_failures_win_over_private_wording():
    message = "Sign in to confirm you're not a bot. Use --cookies-from-browser"
    assert classify_error(message) is ErrorCause.COOKIES


def test_geo_blocked_is_its_own_cause():
    assert classify_error("The uploader has not made this video available in your country") is (
        ErrorCause.GEO
    )


def test_network_errors():
    assert classify_error("Read timed out") is ErrorCause.NETWORK
    assert classify_error("Temporary failure in name resolution") is ErrorCause.NETWORK


def test_disk_errors():
    assert classify_error("OSError: [Errno 28] No space left on device") is ErrorCause.DISK


def test_unknown_messages_fall_back_to_other():
    assert classify_error("boom") is ErrorCause.OTHER
    assert classify_error("") is ErrorCause.OTHER
    assert classify_error(None) is ErrorCause.OTHER


def test_summary_counts_and_orders_by_frequency():
    videos = [
        Video(title="a", url="u1", error_message="Private video"),
        Video(title="b", url="u2", error_message="Private video"),
        Video(title="c", url="u3", error_message="Sign in to confirm you're not a bot"),
        Video(title="d", url="u4", error_message="boom"),
    ]
    assert summarize_failures(videos) == [
        (ErrorCause.PRIVATE, 2),
        (ErrorCause.COOKIES, 1),
        (ErrorCause.OTHER, 1),
    ]


def test_summary_of_no_failures_is_empty():
    assert summarize_failures([]) == []
