"""Tests for the download-failure taxonomy."""

import pytest

from youmudow.domain.errors import DownloadErrorKind, classify_download_error


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("ERROR: Sign in to confirm you're not a bot", DownloadErrorKind.COOKIES),
        ("Private video. Sign in if you've been granted access", DownloadErrorKind.PRIVATE),
        ("The uploader has not made this video available in your country", DownloadErrorKind.GEO),
        ("Unable to download webpage: [Errno 8] getaddrinfo failed", DownloadErrorKind.NETWORK),
        ("Unsupported URL: https://example.com/x", DownloadErrorKind.UNSUPPORTED),
        ("[Errno 28] No space left on device", DownloadErrorKind.DISK),
        ("something unexpected", DownloadErrorKind.OTHER),
        ("", DownloadErrorKind.OTHER),
        (None, DownloadErrorKind.OTHER),
    ],
)
def test_messages_map_to_the_kind_a_person_can_act_on(message, expected):
    assert classify_download_error(message) is expected


def test_a_bot_check_is_not_reported_as_private():
    message = "Sign in to confirm you're not a bot. This video is unavailable."
    assert classify_download_error(message) is DownloadErrorKind.COOKIES
