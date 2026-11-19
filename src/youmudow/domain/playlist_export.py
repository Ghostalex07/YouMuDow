"""Export a loaded playlist as an .m3u file."""

from collections.abc import Sequence

from youmudow.domain.models import Video


def playlist_to_m3u(videos: Sequence[Video]) -> str:
    """Render ``videos`` as M3U text, one entry per line.

    Unknown durations use the M3U convention of ``-1``.
    """
    lines = ["#EXTM3U"]
    for video in videos:
        duration = video.duration if video.duration and video.duration > 0 else -1
        lines.append(f"#EXTINF:{duration},{video.title}")
        lines.append(video.url)
    return "\n".join(lines) + "\n"
