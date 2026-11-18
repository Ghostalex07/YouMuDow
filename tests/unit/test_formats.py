import pytest

from youmudow.domain.formats import FormatInfo, estimate_size, parse_formats
from youmudow.domain.models import DownloadOptions
from youmudow.domain.sizes import format_size


def test_parse_formats_reads_sizes_and_falls_back_to_approx():
    payload = {
        "formats": [
            {"format_id": "251", "ext": "webm", "abr": 160.0, "filesize": 1000},
            {"format_id": "140", "ext": "m4a", "abr": 128.0, "filesize_approx": 2000},
            {"ext": "mp4", "vcodec": "none"},
        ]
    }
    result = parse_formats(payload)
    assert [f.format_id for f in result] == ["251", "140"]
    assert result[1].filesize == 2000


def test_parse_formats_tolerates_garbage():
    assert parse_formats({}) == []
    assert parse_formats({"formats": "nope"}) == []


def test_audio_estimate_uses_the_requested_bitrate():
    options = DownloadOptions(file_format="mp3", quality="320kbps")
    assert estimate_size([], options, duration=60) == 60 * 320_000 // 8


def test_audio_estimate_best_uses_the_highest_bitrate():
    options = DownloadOptions(file_format="mp3", quality="best")
    formats = [FormatInfo("1", "m4a", 0, 128.0, 0.0, 0), FormatInfo("2", "m4a", 0, 256.0, 0.0, 0)]
    assert estimate_size(formats, options, 60) == 60 * 256_000 // 8


def test_video_estimate_picks_the_best_format_at_or_below_the_target():
    options = DownloadOptions(file_format="mp4", quality="720p")
    formats = [
        FormatInfo("137", "mp4", 1080, 0.0, 0.0, 50_000_000),
        FormatInfo("136", "mp4", 720, 0.0, 0.0, 20_000_000),
        FormatInfo("135", "mp4", 480, 0.0, 0.0, 8_000_000),
    ]
    assert estimate_size(formats, options, 60) == 20_000_000


def test_video_estimate_says_nothing_when_only_larger_formats_exist():
    options = DownloadOptions(file_format="mp4", quality="360p")
    formats = [FormatInfo("313", "mp4", 2160, 0.0, 0.0, 900_000_000)]
    assert estimate_size(formats, options, 60) is None


def test_estimate_is_none_without_duration_or_formats():
    assert estimate_size([], DownloadOptions(), 0) is None
    assert estimate_size([], DownloadOptions(file_format="mp4", quality="720p"), 60) is None


@pytest.mark.parametrize(
    "value,expected", [(0, ""), (999, "999.0 B"), (1024, "1.0 KB"), (5 * 1024**2, "5.0 MB")]
)
def test_format_size(value, expected):
    assert format_size(value) == expected
