"""yt-dlp adapter for YouMuDow.

This module provides a wrapper around yt-dlp functionality.
The adapter pattern allows swapping the underlying downloader implementation
without affecting the rest of the application.

The adapter only orchestrates. Its building blocks live in sibling modules:
argument building in :mod:`youmudow.adapters.ytdlp_args`, output parsing in
:mod:`youmudow.adapters.ytdlp_parsing`, the streaming subprocess in
:mod:`youmudow.adapters.ytdlp_process` and result-file resolution in
:mod:`youmudow.adapters.ytdlp_files`.
"""

import json
import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from youmudow.adapters.ytdlp_args import (
    THUMBNAIL_EMBED_FORMATS,
    build_base_args,
    build_download_args,
    build_flat_playlist_args,
)
from youmudow.adapters.ytdlp_files import existing_files, resolve_destination
from youmudow.adapters.ytdlp_parsing import (
    ProgressInfo,
    is_cookie_error,
    normalize_playlist_url,
    parse_cookie_error,
    parse_flat_results,
    parse_json_output,
    parse_yt_dlp_error,
)
from youmudow.adapters.ytdlp_process import run_capture, run_process
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.exceptions import YtDlpError
from youmudow.domain.models import Video
from youmudow.domain.validators import sanitize_filename

logger = logging.getLogger(__name__)

__all__ = [
    "LogCallback",
    "ProgressCallback",
    "ProgressInfo",
    "YtdlpAdapter",
    "YtdlpConfig",
    "parse_cookie_error",
    "parse_yt_dlp_error",
]

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[float, str], None]


@dataclass
class YtdlpConfig:
    """Configuration for yt-dlp adapter."""

    output_template: str = "%(title)s.%(ext)s"
    format_preference: str = "best[ext=mp3]/best"
    audio_format: str = "mp3"
    audio_quality: str = "0"
    ffmpeg_location: str | None = None
    cookies_file: str | None = None
    user_agent: str | None = None
    verify_certificates: bool = True
    # Inactivity timeout in seconds, not a total wall-clock limit: the deadline
    # is pushed back every time yt-dlp writes a line, so a download that keeps
    # reporting progress is never killed. A run started without a cancel_event
    # still uses it as a hard cap via process.wait().
    download_timeout: int = 300
    max_retries: int = 2

    embed_metadata: bool = True
    embed_thumbnail: bool = True
    add_chapters: bool = False
    embed_subs: bool = False
    parse_metadata: str | None = None
    metadata_from_title: str | None = None


class YtdlpAdapter:
    """Adapter for yt-dlp operations."""

    def __init__(self, config: YtdlpConfig | None = None) -> None:
        self._config = config or YtdlpConfig()
        self._log_callback: LogCallback | None = None
        self._destination_local = threading.local()

    @property
    def _last_destination(self) -> Path | None:
        # The captured destination is thread-local: several DownloadWorker
        # threads may run download() concurrently on this single adapter, and
        # one run's destination must never be attributed to another's.
        return getattr(self._destination_local, "path", None)

    @_last_destination.setter
    def _last_destination(self, value: Path | None) -> None:
        self._destination_local.path = value

    @property
    def config(self) -> YtdlpConfig:
        return self._config

    def set_log_callback(self, callback: LogCallback | None) -> None:
        """Set callback for real-time log output."""
        self._log_callback = callback

    def _log(self, message: str) -> None:
        """Emit log message to callback if set."""
        if self._log_callback:
            self._log_callback(message)

    def _build_download_args(self, video: Video, skip_cookies: bool = False) -> list[str]:
        """Build arguments for download including metadata options."""
        return build_download_args(self._config, video, skip_cookies, self._log)

    def _log_command_error(self, label: str, result: subprocess.CompletedProcess[str]) -> None:
        """Log the first stderr line of a failed one-shot yt-dlp command."""
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        first_line = error_msg.split("\n")[0][:120]
        self._log(f"[{label}] yt-dlp error (code {result.returncode}): {first_line}")

    def search(self, query: str, limit: int = 10) -> list[Video]:
        """Search yt-dlp for up to ``limit`` videos matching ``query``."""
        args = build_flat_playlist_args(self._config, f"ytsearch{limit}:{query}", log=self._log)

        self._log(f"[SEARCH] Searching for: {query}")

        try:
            result = run_capture(args, timeout=30)

            if result.returncode != 0:
                self._log_command_error("SEARCH", result)

            videos = parse_flat_results(result.stdout)

            self._log(f"[SEARCH] Found {len(videos)} results")
            return videos

        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
            OSError,
        ) as e:
            self._log(f"[SEARCH] yt-dlp not found or error: {e}")
            logger.warning("Search failed: %s", e)
            return []

    def get_metadata(self, url: str) -> Video | None:
        """Fetch metadata for a single URL without downloading it."""
        args = build_base_args(self._config, log=self._log)
        args.extend(["--dump-json", "--no-download", url])

        self._log(f"[METADATA] Fetching: {url}")

        try:
            result = run_capture(args, timeout=60)

            if result.returncode == 0 and result.stdout:
                data = parse_json_output(result.stdout)
                if data:
                    title = str(data.get("title") or "Unknown")
                    uploader = str(data.get("uploader") or data.get("uploader_id") or "")
                    duration = data.get("duration") or 0
                    try:
                        duration = int(duration)
                    except (TypeError, ValueError):
                        duration = 0
                    thumbnail = data.get("thumbnail") or ""
                    if not thumbnail:
                        thumbnails = data.get("thumbnails")
                        if isinstance(thumbnails, list) and thumbnails:
                            first = thumbnails[0]
                            if isinstance(first, dict):
                                thumbnail = str(first.get("url") or "")
                    self._log(f"[METADATA] Got: {title}")
                    return Video(
                        title=title,
                        url=url,
                        uploader=uploader,
                        duration=duration,
                        thumbnail=thumbnail,
                    )
            elif result.returncode != 0:
                self._log_command_error("METADATA", result)

        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
            OSError,
            json.JSONDecodeError,
        ) as e:
            self._log(f"[METADATA] Error: {e}")
            logger.warning("Metadata fetch failed for %s: %s", url, e)

        return None

    def get_playlist_videos(self, url: str, limit: int = 50) -> list[Video]:
        """Fetch up to ``limit`` videos from a playlist.

        Non-YouTube URLs (SoundCloud sets, Bandcamp albums, ...) are passed
        through unchanged. YouTube watch URLs carrying a ``list`` parameter
        are normalized to their playlist URL.

        ``--playlist-end`` limits how many entries yt-dlp extracts, so huge
        playlists are not fully enumerated when only ``limit`` items are needed.
        """
        if limit is None:
            limit = 50
        if limit <= 0:
            return []
        args = build_flat_playlist_args(
            self._config, normalize_playlist_url(url), playlist_end=limit, log=self._log
        )

        self._log(f"[PLAYLIST] Fetching: {url}")

        try:
            result = run_capture(args, timeout=120)

            videos = parse_flat_results(result.stdout)

            total = len(videos)
            if total > limit:
                self._log(f"[INFO] Playlist truncated to {limit} videos (found {total})")

            self._log(f"[PLAYLIST] Found {min(total, limit)} videos")
            return videos[:limit]

        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
            OSError,
        ) as e:
            self._log(f"[PLAYLIST] yt-dlp not found or error: {e}")
            logger.warning("Playlist fetch failed: %s", e)
            return []

    def _log_download_start(self, video: Video, fmt: str) -> None:
        """Log download start information."""
        self._log(f"[DOWNLOAD] Starting: {video.title}")
        self._log(f"[DOWNLOAD] Format: {fmt}")
        self._log(f"[DOWNLOAD] Output: {video.path.name if video.path else 'unknown'}")

        metadata_parts = []
        if self._config.embed_metadata:
            metadata_parts.append("metadata")
        if self._config.embed_thumbnail and fmt in THUMBNAIL_EMBED_FORMATS:
            metadata_parts.append("thumbnail")
        if self._config.add_chapters:
            metadata_parts.append("chapters")
        if metadata_parts:
            self._log(f"[METADATA] Embedding: {', '.join(metadata_parts)}")

        if video.options and video.options.subtitles:
            lang = video.options.subtitle_lang or "en"
            self._log(f"[SUB] Downloading subtitles ({lang})")
            if video.options.embed_subtitles:
                self._log("[SUB] Embedding subtitles in file")

        self._log("-" * 50)

    def _log_download_success(self, video: Video, fmt: str) -> None:
        """Log successful download completion."""
        self._log("-" * 50)
        self._log(f"[DONE] {video.title}")
        if self._config.embed_metadata:
            self._log(f"[METADATA] {video.title} tags applied")
        if self._config.embed_thumbnail and fmt in THUMBNAIL_EMBED_FORMATS:
            self._log(f"[METADATA] {video.title} artwork embedded")

    def _run_process(
        self,
        args: list[str],
        output_path: Path,
        video: Video,
        cancel_event: threading.Event | None,
        progress_callback: ProgressCallback | None,
    ) -> tuple[int, list[str], list[str], list[str]]:
        """Run yt-dlp for ``video`` and remember the last reported destination.

        See :func:`youmudow.adapters.ytdlp_process.run_process` for the return
        tuple and the inactivity-timeout semantics.
        """
        result = run_process(
            args,
            output_path,
            video,
            cancel_event,
            progress_callback,
            self._config,
            self._log,
        )
        destinations = result[2]
        if destinations:
            self._last_destination = Path(destinations[-1])
        return result

    def download(
        self,
        video: Video,
        output_path: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Video:
        """Download ``video`` into ``output_path``, with retries and cancel support."""
        output_path.mkdir(parents=True, exist_ok=True)
        video.status = DownloadStatus.DOWNLOADING
        video.path = output_path
        self._last_destination = None

        opts = video.options
        fmt = opts.file_format if opts else "mp3"
        safe_title = sanitize_filename(video.title)
        args = self._build_download_args(video)

        self._log_download_start(video, fmt)

        last_error = ""
        cookie_failed = False
        cancelled = False
        destinations: list[str] = []
        already_downloaded: list[str] = []
        # yt-dlp's output template keeps whatever already exists in the output
        # directory. To never mistake a pre-existing file for this download,
        # snapshot the directory before the first attempt and drop any
        # destination captured by an earlier run on this adapter.
        pre_existing = existing_files(output_path)
        self._last_destination = None

        try:
            # max_retries is the maximum number of *attempts*: always attempt at
            # least once, and never launch more attempts than configured.
            attempts = max(1, self._config.max_retries)
            for attempt in range(1, attempts + 1):
                if cancel_event and cancel_event.is_set():
                    self._log("[CANCEL] Download cancelled by user")
                    cancelled = True
                    break

                if attempt > 1:
                    wait = attempt - 1
                    self._log(
                        f"[RETRY] Attempt {attempt}/{self._config.max_retries}, waiting {wait}s..."
                    )
                    if cancel_event:
                        if cancel_event.wait(wait):
                            cancelled = True
                            break
                    else:
                        time.sleep(wait)

                result = self._run_process(
                    args, output_path, video, cancel_event, progress_callback
                )
                returncode = result[0]
                error_lines = result[1]
                # _run_process reports per-call destinations and already-
                # downloaded files as the third and fourth elements. Older
                # mocks in tests may return a shorter tuple; tolerate that.
                destinations = result[2] if len(result) > 2 else []
                already_downloaded = result[3] if len(result) > 3 else []
                if destinations:
                    last_destination = Path(destinations[-1])
                    self._last_destination = last_destination

                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break

                if returncode == -2:  # timeout
                    last_error = "Download timed out"
                    break

                if returncode == 0:
                    video.status = DownloadStatus.DONE
                    self._log_download_success(video, fmt)
                    break

                # Error handling
                error_output = "\n".join(error_lines[-10:])
                user_message = parse_yt_dlp_error(error_output)
                last_error = user_message
                self._log(f"[ERROR] {user_message} (code: {returncode})")

                if (
                    is_cookie_error(error_output)
                    and opts
                    and opts.use_cookies
                    and not cookie_failed
                    and attempt == 1
                ):
                    cookie_failed = True
                    self._log("[AUTH] Failed to load browser cookies, retrying without auth")
                    args = self._build_download_args(video, skip_cookies=True)
                    continue

                if attempt < self._config.max_retries and not cookie_failed:
                    self._log(f"[RETRY] Will retry in {attempt}s...")

        except YtDlpError as e:
            video.status = DownloadStatus.ERROR
            video.error_message = str(e)
            self._log(f"[FATAL] {e}")
        except Exception as e:
            video.status = DownloadStatus.ERROR
            video.error_message = str(e)
            self._log(f"[FATAL] {e}")
            logger.exception("Unexpected error while downloading %s", video.url)

        if cancelled:
            video.status = DownloadStatus.CANCELLED
            video.error_message = "Download cancelled"
        elif video.status != DownloadStatus.DONE:
            video.status = DownloadStatus.ERROR
            video.error_message = video.error_message or last_error or "Download failed"
        else:
            video.path = resolve_destination(
                destinations,
                output_path,
                safe_title,
                pre_existing,
                already_downloaded,
                captured=self._last_destination,
            )
            if video.path is None:
                # Completion is only valid when a result file can be attributed
                # to this run. A successful exit that left no file is a failure,
                # not a COMPLETED download with an unknown path.
                video.status = DownloadStatus.ERROR
                video.error_message = "yt-dlp reported success but produced no output file"
                self._log(f"[ERROR] {video.error_message}")

        return video
