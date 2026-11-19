"""Tests for exporting a loaded playlist as an .m3u file."""

from youmudow.domain.models import Video
from youmudow.domain.playlist_export import playlist_to_m3u


def test_m3u_header_and_entries():
    videos = [
        Video(title="One", url="https://x.test/1", duration=61),
        Video(title="Two", url="https://x.test/2"),
    ]
    lines = playlist_to_m3u(videos).splitlines()
    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#EXTINF:61,One"
    assert lines[2] == "https://x.test/1"
    assert lines[3] == "#EXTINF:-1,Two"
    assert lines[4] == "https://x.test/2"


def test_m3u_has_a_trailing_newline():
    assert playlist_to_m3u([Video(title="One", url="https://x.test/1")]).endswith("\n")


def test_m3u_of_an_empty_playlist_is_just_the_header():
    assert playlist_to_m3u([]) == "#EXTM3U\n"


def test_m3u_keeps_commas_in_the_title():
    text = playlist_to_m3u([Video(title="A, B", url="https://x.test/1", duration=5)])
    assert "A, B" in text
