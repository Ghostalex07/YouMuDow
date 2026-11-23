"""Command-line interface for YouMuDow.

Reuses the same services and domain models as the desktop GUI, so the CLI
adds no duplicate download or search logic.
"""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from youmudow import __version__
from youmudow.app.config import AppConfig
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video
from youmudow.domain.url_batch import parse_url_list
from youmudow.domain.validators import (
    AUDIO_FORMATS,
    SUPPORTED_FORMATS,
    SUPPORTED_QUALITIES,
    is_playlist_url,
    is_supported_url,
)
from youmudow.services.download_service import DownloadService
from youmudow.services.search_service import SearchService

_FORMATS = SUPPORTED_FORMATS
_QUALITIES = SUPPORTED_QUALITIES

_FORMAT_HELP = f"audio ({', '.join(sorted(AUDIO_FORMATS))}) or video (mp4)"
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

    download = subparsers.add_parser("download", help="download a URL or a list of URLs")
    download.add_argument("url", nargs="?", help="video or audio URL")
    download.add_argument(
        "--from-file",
        type=Path,
        help="download every URL listed in this file (one per line, # comments allowed)",
    )
    download.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print a JSON summary instead of progress lines",
    )
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
        "--limit",
        type=_positive_int,
        default=50,
        help="maximum playlist or channel entries (default: 50)",
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

    serve = subparsers.add_parser("serve", help="run a headless HTTP download server")
    serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to listen on (default: 127.0.0.1)",
    )
    serve.add_argument(
        "--port",
        type=_positive_int,
        default=8765,
        help="TCP port (default: 8765)",
    )
    serve.add_argument(
        "--token",
        help="bearer token; required when listening beyond localhost",
    )
    serve.add_argument(
        "--output",
        type=Path,
        help="download folder (default: the configured one)",
    )
    serve.set_defaults(func=_cmd_serve)

    doctor = subparsers.add_parser("doctor", help="check the environment")
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def _resolve_options(args: argparse.Namespace, config: AppConfig) -> DownloadOptions:
    options = config.to_download_options()
    if args.file_format:
        options.file_format = args.file_format
    if args.quality:
        options.quality = args.quality
    return options


def _open_cli_store():
    """Open the shared library database, or None when it is unavailable."""
    try:
        from youmudow.paths import database_file
        from youmudow.services.library_store import LibraryStore

        return LibraryStore(database_file())
    except Exception:  # noqa: BLE001 - the CLI must work without the database
        print("(continuing without the download history)", file=sys.stderr)
        return None


def _cmd_download_batch(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        text = Path(args.from_file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Could not read {args.from_file}: {exc}", file=sys.stderr)
        return 1

    urls = parse_url_list(text)
    if not urls:
        print("No usable URLs in the file", file=sys.stderr)
        return 1

    options = _resolve_options(args, config)
    output_dir = args.output or config.output_path
    output_dir.mkdir(parents=True, exist_ok=True)
    store = _open_cli_store()

    service = DownloadService()
    service.set_log_callback(lambda line: None if args.as_json else print(line))

    results: list[dict[str, str]] = []
    downloaded = skipped = failed = 0
    for index, url in enumerate(urls, start=1):
        if store is not None and store.has_url(url):
            skipped += 1
            results.append({"url": url, "status": "skipped"})
            continue
        video = Video(title=url, url=url, options=options)
        if not args.as_json:
            print(f"[{index}/{len(urls)}] {url}")
        try:
            service.download_now(video, output_dir)
            downloaded += 1
            results.append({"url": url, "status": "downloaded"})
        except Exception as exc:  # noqa: BLE001 - one bad URL must not stop the batch
            failed += 1
            results.append({"url": url, "status": "failed", "reason": str(exc)})

    summary = {
        "requested": len(urls),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
    if args.as_json:
        print(json.dumps(summary))
    else:
        print(f"Downloaded {downloaded}, skipped {skipped}, failed {failed} of {len(urls)}")
    return 0 if failed == 0 else 1


def _cmd_download(args: argparse.Namespace, config: AppConfig) -> int:
    if args.from_file:
        return _cmd_download_batch(args, config)
    if not args.url:
        print("Either a URL or --from-file is required", file=sys.stderr)
        return 2
    options = _resolve_options(args, config)
    output_dir = args.output or config.output_path
    output_dir.mkdir(parents=True, exist_ok=True)

    if not is_supported_url(args.url):
        print(f"Invalid URL: {args.url}", file=sys.stderr)
        return 1

    service = DownloadService()
    service.set_log_callback(print)

    def on_progress(percent: float, speed: str) -> None:
        suffix = f" at {speed}" if speed and speed != "Calculating..." else ""
        print(f"\r[download] {percent:5.1f}%{suffix}", end="", flush=True)

    if is_playlist_url(args.url):
        return _download_playlist(args, service, options, output_dir, on_progress)

    video: Video | None = None
    if not args.skip_metadata:
        video = SearchService().get_metadata(args.url)
    if video is None:
        video = Video(title=args.url, url=args.url)
    video.options = options

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


def _download_playlist(
    args: argparse.Namespace,
    service: DownloadService,
    options: DownloadOptions,
    output_dir: Path,
    on_progress: Callable[[float, str], None],
) -> int:
    search = SearchService()
    search.set_log_callback(print)
    videos = search.get_playlist(args.url, min(args.limit, 500))
    if not videos:
        print(f"No videos found in {args.url}", file=sys.stderr)
        return 1

    print(f"Found {len(videos)} video(s)")
    if len(videos) >= min(args.limit, 500):
        print(f"(limited to {min(args.limit, 500)}; use --limit to change)")
    failures = 0
    for index, video in enumerate(videos, start=1):
        print(f"[{index}/{len(videos)}] {video.title}")
        video.options = options
        try:
            result = service.download_now(video, output_dir, progress_callback=on_progress)
        except KeyboardInterrupt:
            print()  # close the in-place progress line
            print("Cancelled", file=sys.stderr)
            return 130
        if result.status != DownloadStatus.DONE:
            failures += 1
    return 0 if failures == 0 else 1


def _cmd_search(args: argparse.Namespace, config: AppConfig) -> int:
    service = SearchService()
    service.set_log_callback(print)
    results = service.search(args.query, args.limit)

    for index, video in enumerate(results, start=1):
        print(f"{index:2}. {video.title}")
        print(f"    {video.url}")
    print(f"\n{len(results)} result(s) for {args.query!r}")
    return 0


def _cmd_serve(args: argparse.Namespace, config: AppConfig) -> int:
    from youmudow.server import serve

    return serve(
        host=args.host,
        port=args.port,
        token=args.token,
        output=args.output,
        config=config,
    )


def _cmd_doctor(args: argparse.Namespace, config: AppConfig) -> int:
    from youmudow.services.doctor import format_report, run_checks

    results = run_checks(output=config.output_path)
    print(format_report(results))
    return 0 if all(result.ok for result in results) else 1


def main(argv: list[str] | None = None) -> int:
    """Entry point for the youmudow-cli script."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = AppConfig()
    func: CommandFunc = args.func
    return func(args, config)


if __name__ == "__main__":
    sys.exit(main())
