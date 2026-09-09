"""Command-line interface for YouMuDow.

Reuses the same services and domain models as the desktop GUI, so the CLI
adds no duplicate download or search logic.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from youmudow import __version__
from youmudow.app.config import AppConfig
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video
from youmudow.domain.validators import is_supported_url
from youmudow.services.download_service import DownloadService
from youmudow.services.search_service import SearchService

_AUDIO_FORMATS = frozenset({"mp3", "m4a", "opus", "ogg", "flac", "wav", "aac"})
_FORMATS = _AUDIO_FORMATS | {"mp4"}
_QUALITIES = frozenset(
    {
        "best",
        "64kbps",
        "96kbps",
        "128kbps",
        "192kbps",
        "256kbps",
        "320kbps",
        "360p",
        "480p",
        "720p",
        "1080p",
    }
)

_FORMAT_HELP = f"audio ({', '.join(sorted(_AUDIO_FORMATS))}) or video (mp4)"
_QUALITY_HELP = "audio bitrate (64kbps..320kbps) or video resolution (360p..1080p, best)"

CommandFunc = Callable[[argparse.Namespace, AppConfig], int]


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youmudow-cli",
        description="YouMuDow command-line downloader and search tool.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="download a single URL")
    download.add_argument("url", help="video or audio URL")
    download.add_argument(
        "--format",
        dest="file_format",
        choices=sorted(_FORMATS),
        help=_FORMAT_HELP,
    )
    download.add_argument("--quality", choices=sorted(_QUALITIES), help=_QUALITY_HELP)
    download.add_argument(
        "--output",
        type=Path,
        help="output directory (default: configured output folder)",
    )
    download.add_argument(
        "--skip-metadata",
        action="store_true",
        help="download without resolving the title via metadata",
    )
    download.set_defaults(func=_cmd_download)

    search = subparsers.add_parser("search", help="search for videos")
    search.add_argument("query", help="search query or URL")
    search.add_argument(
        "--limit",
        type=_positive_int,
        default=10,
        help="number of results (default: 10)",
    )
    search.set_defaults(func=_cmd_search)

    return parser


def _resolve_options(args: argparse.Namespace, config: AppConfig) -> DownloadOptions:
    options = config.to_download_options()
    if args.file_format:
        options.file_format = args.file_format
    if args.quality:
        options.quality = args.quality
    return options


def _cmd_download(args: argparse.Namespace, config: AppConfig) -> int:
    options = _resolve_options(args, config)
    output_dir = args.output or config.output_path
    output_dir.mkdir(parents=True, exist_ok=True)

    if not is_supported_url(args.url):
        print(f"Invalid URL: {args.url}", file=sys.stderr)
        return 1

    service = DownloadService()
    service.set_log_callback(print)

    video: Video | None = None
    if not args.skip_metadata:
        video = SearchService().get_metadata(args.url)
    if video is None:
        video = Video(title=args.url, url=args.url)
    video.options = options

    def on_progress(percent: float, speed: str) -> None:
        suffix = f" at {speed}" if speed and speed != "Calculating..." else ""
        print(f"\r[download] {percent:5.1f}%{suffix}", end="", flush=True)

    try:
        result = service.download_now(video, output_dir, progress_callback=on_progress)
    except KeyboardInterrupt:
        print("\nCancelled", file=sys.stderr)
        return 130
    print()

    if result.status == DownloadStatus.DONE:
        destination = result.path or output_dir
        print(f"Downloaded: {result.title} -> {destination}")
        return 0
    print(f"Download failed: {result.error_message or 'unknown error'}", file=sys.stderr)
    return 1


def _cmd_search(args: argparse.Namespace, config: AppConfig) -> int:
    service = SearchService()
    service.set_log_callback(print)
    results = service.search(args.query, args.limit)

    for index, video in enumerate(results, start=1):
        print(f"{index:2}. {video.title}")
        print(f"    {video.url}")
    print(f"\n{len(results)} result(s) for {args.query!r}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the youmudow-cli script."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = AppConfig()
    func: CommandFunc = args.func
    return func(args, config)


if __name__ == "__main__":
    sys.exit(main())
