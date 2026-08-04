"""yt-dlp adapter for YouMuDow.

This module provides a wrapper around yt-dlp functionality.
The adapter pattern allows swapping the underlying downloader implementation
without affecting the rest of the application.
"""

import json
import logging
import re
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from youmudow.adapters.browser_profiles import check_browser_profile, get_fallback_browser
from youmudow.domain.enums import DownloadStatus
from youmudow.domain.exceptions import YtDlpError, YtDlpNotFoundError
from youmudow.domain.models import Video
from youmudow.domain.validators import sanitize_filename

logger = logging.getLogger(__name__)

AUDIO_FORMATS: frozenset[str] = frozenset({"mp3", "m4a", "opus", "ogg", "flac", "wav", "aac"})
THUMBNAIL_EMBED_FORMATS: frozenset[str] = frozenset({"mp3", "m4a", "opus"})

_VIDEO_QUALITY_SELECTORS: dict[str, str] = {
    "1080p": "bestvideo[height<=1080]+bestaudio/best",
    "720p": "bestvideo[height<=720]+bestaudio/best",
    "480p": "bestvideo[height<=480]+bestaudio/best",
    "360p": "bestvideo[height<=360]+bestaudio/best",
}


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[float, str], None]

_ERROR_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("private video", "video is private"), "Video is private"),
    (("not available", "unavailable"), "Video not available"),
    (("removed", "deleted"), "Video has been removed"),
    (("connection", "network", "http error"), "Connection error"),
    (("permission denied", "permission"), "Permission denied"),
    (("auth", "login", "sign in"), "Authentication required"),
    (("captcha", "verification"), "CAPTCHA required"),
]

_COOKIE_BROWSER_NAMES: tuple[str, ...] = ("chrome", "firefox", "edge", "brave", "opera", "vivaldi")

_COOKIE_ERROR_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("locked", "lock"), "Cookies locked - browser may be running"),
    (("profile",), "Browser profile not accessible"),
    (("database",), "Cookies database corrupted or inaccessible"),
    (("no such file", "directory"), "Browser profile directory not found"),
]


def parse_cookie_error(error_output: str) -> str:
    """Parse cookie-related errors and return a user-friendly message."""
    error_lower = error_output.lower()

    if "could not find" in error_lower or "not found" in error_lower:
        for browser in _COOKIE_BROWSER_NAMES:
            if browser in error_lower:
                return f"{browser.capitalize()} cookies not found - is {browser.capitalize()} installed?"
        return "Browser cookies not found"

    for keywords, message in _COOKIE_ERROR_PATTERNS:
        if any(kw in error_lower for kw in keywords):
            return message

    return "Cookie authentication failed"


def parse_yt_dlp_error(error_output: str) -> str:
    """Parse yt-dlp error output and return a user-friendly message."""
    if not error_output:
        return "Download failed"
    error_lower = error_output.lower()
    if "地域" in error_output or "region" in error_lower:
        return "Video not available in your region"
    if "cookies" in error_lower or "cookie" in error_lower:
        return parse_cookie_error(error_output)
    for keywords, message in _ERROR_PATTERNS:
        if any(kw in error_lower for kw in keywords):
            return message
    return "Download failed"


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
    download_timeout: int = 300
    max_retries: int = 2

    embed_metadata: bool = True
    embed_thumbnail: bool = True
    add_chapters: bool = False
    embed_subs: bool = False
    parse_metadata: str | None = None
    metadata_from_title: str | None = None


@dataclass
class ProgressInfo:
    """Parsed progress information from yt-dlp output."""

    progress: float
    speed: str
    eta: str
    size: str
    line: str = ""


class YtdlpAdapter:
    """Adapter for yt-dlp operations."""

    def __init__(self, config: YtdlpConfig | None = None) -> None:
        self._config = config or YtdlpConfig()
        self._log_callback: LogCallback | None = None

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

    def _build_base_args(self, video: Video | None = None, skip_cookies: bool = False) -> list[str]:
        args = ["yt-dlp", "--no-check-certificate"]

        if self._config.ffmpeg_location:
            args.extend(["--ffmpeg-location", self._config.ffmpeg_location])
        if self._config.user_agent:
            args.extend(["--user-agent", self._config.user_agent])

        if video and video.options and not skip_cookies:
            opts = video.options
            if opts.use_cookies:
                if opts.cookies_from_browser:
                    browser = opts.cookies_from_browser.lower()
                    exists, message = check_browser_profile(browser)
                    if not exists:
                        self._log(f"[AUTH] {message}")
                        fallback = get_fallback_browser()
                        if fallback and fallback != browser:
                            self._log(f"[AUTH] Falling back to {fallback.capitalize()}")
                            browser = fallback
                            opts.cookies_from_browser = fallback
                            opts.cookies_profile = None
                    profile = opts.cookies_profile
                    cookie_arg = browser
                    if profile and profile.lower() not in ["default", "main"]:
                        cookie_arg = f"{browser}:{profile}"
                    args.extend(["--cookies-from-browser", cookie_arg])
                    profile_msg = (
                        f" ({profile})"
                        if profile and profile.lower() not in ["default", "main"]
                        else ""
                    )
                    self._log(f"[AUTH] Using {browser.capitalize()}{profile_msg} cookies")
                elif opts.cookies_file:
                    cookie_path = Path(opts.cookies_file)
                    if cookie_path.exists():
                        args.extend(["--cookies", str(cookie_path)])
                        self._log("[AUTH] Using cookies file")
                    else:
                        self._log(f"[WARNING] Cookies file not found: {opts.cookies_file}")
        elif self._config.cookies_file and not skip_cookies:
            args.extend(["--cookies", self._config.cookies_file])

        return args

    def _build_download_args(self, video: Video, skip_cookies: bool = False) -> list[str]:
        """Build arguments for download including metadata options."""
        args = self._build_base_args(video, skip_cookies)

        opts = video.options
        format_selector = self._get_format_selector(opts.file_format, opts.quality)
        args.extend(
            [
                "-f",
                format_selector,
                "-o",
                str(self._config.output_template),
            ]
        )

        if opts.file_format in AUDIO_FORMATS:
            audio_quality = self._get_audio_quality(opts.quality)
            args.extend(
                [
                    "--extract-audio",
                    "--audio-format",
                    opts.file_format,
                    "--audio-quality",
                    audio_quality,
                ]
            )

        if self._config.embed_metadata:
            args.append("--embed-metadata")

        if self._config.embed_thumbnail and opts.file_format in THUMBNAIL_EMBED_FORMATS:
            args.append("--embed-thumbnail")

        if self._config.add_chapters:
            args.append("--embed-chapters")

        if opts.subtitles:
            args.extend(["--write-subs", "--sub-langs", opts.subtitle_lang])
            if opts.embed_subtitles:
                args.append("--embed-subs")
        elif self._config.embed_subs:
            args.extend(["--write-subs", "--embed-subs"])

        if opts.rate_limit:
            args.extend(["--limit-rate", opts.rate_limit])

        if opts.split_chapters:
            args.append("--split-chapters")

        if self._config.parse_metadata:
            args.extend(["--parse-metadata", self._config.parse_metadata])

        if self._config.metadata_from_title:
            args.extend(["--metadata-from-title", self._config.metadata_from_title])

        args.append(video.url)

        return args

    def _parse_progress(self, line: str) -> ProgressInfo | None:
        progress_pattern = r"\[download\]\s+(\d+\.?\d*)%.*?at\s+(\S+).*?ETA\s+(\S+)"
        size_pattern = r"\[download\]\s+(\d+\.?\d*)%.*?of\s+~?([~\d.]+\w+)"

        progress_match = re.search(progress_pattern, line)
        if progress_match:
            return ProgressInfo(
                progress=float(progress_match.group(1)),
                speed=progress_match.group(2),
                eta=progress_match.group(3),
                size="",
                line=line,
            )

        size_match = re.search(size_pattern, line)
        if size_match:
            return ProgressInfo(
                progress=float(size_match.group(1)),
                speed="",
                eta="",
                size=size_match.group(2),
                line=line,
            )

        return None

    def search(self, query: str, limit: int = 10) -> list[Video]:
        args = self._build_base_args(None)
        args.extend(
            [
                "--flat-playlist",
                "--print",
                "%(url)s | %(title)s | %(uploader)s | %(duration)s",
                f"ytsearch{limit}:{query}",
            ]
        )

        self._log(f"[SEARCH] Searching for: {query}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                first_line = error_msg.split("\n")[0][:120]
                self._log(f"[SEARCH] yt-dlp error (code {result.returncode}): {first_line}")

            videos = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line and " | " in line:
                        parts = line.split(" | ", 3)
                        if len(parts) >= 4:
                            videos.append(
                                Video(
                                    title=parts[1].strip(),
                                    url=parts[0].strip(),
                                    uploader=parts[2].strip(),
                                    duration=self._parse_duration(parts[3]),
                                )
                            )

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
        args = self._build_base_args(None)
        args.extend(
            [
                "--dump-json",
                "--no-download",
                url,
            ]
        )

        self._log(f"[METADATA] Fetching: {url}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                self._log(f"[METADATA] Got: {data.get('title', 'Unknown')}")
                return Video(
                    title=data.get("title", "Unknown"),
                    url=url,
                    uploader=data.get("uploader", ""),
                    duration=data.get("duration", 0) or 0,
                    thumbnail=data.get("thumbnail", ""),
                )
            elif result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                first_line = error_msg.split("\n")[0][:120]
                self._log(f"[METADATA] yt-dlp error (code {result.returncode}): {first_line}")

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
        """Fetch all videos from a playlist."""
        args = self._build_base_args(None)
        args.extend(
            [
                "--flat-playlist",
                "--print",
                "%(url)s | %(title)s | %(uploader)s | %(duration)s",
                f"https://www.youtube.com/playlist?list={url.split('list=')[-1].split('&')[0]}",
            ]
        )

        self._log(f"[PLAYLIST] Fetching: {url}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

            videos = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line and " | " in line:
                        parts = line.split(" | ", 3)
                        if len(parts) >= 4:
                            videos.append(
                                Video(
                                    title=parts[1].strip(),
                                    url=parts[0].strip(),
                                    uploader=parts[2].strip(),
                                    duration=self._parse_duration(parts[3]),
                                )
                            )

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
    ) -> tuple[int, list[str]]:
        """
        Run yt-dlp subprocess, stream output, return (returncode, error_lines).
        Returns (-1, []) if cancelled before process starts.
        """
        error_lines: list[str] = []
        output_lock = threading.Lock()

        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(output_path),
            )
        except FileNotFoundError as e:
            raise YtDlpNotFoundError(
                "yt-dlp binary not found. Install it with: pip install yt-dlp"
            ) from e

        def read_output() -> None:
            stdout = process.stdout
            if stdout is None:
                return
            try:
                for line in stdout:
                    if cancel_event and cancel_event.is_set():
                        process.terminate()
                        break
                    if line:
                        stripped = line.strip()
                        with output_lock:
                            if "error" in stripped.lower() or "warning" in stripped.lower():
                                error_lines.append(stripped)
                        self._log(stripped)
                        if progress_callback:
                            info = self._parse_progress(stripped)
                            if info:
                                video.progress = info.progress
                                progress_callback(info.progress, info.speed)
            except (OSError, ValueError, json.JSONDecodeError) as e:
                logger.debug("Output reader stopped for %s: %s", video.url, e)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()

        try:
            process.wait(timeout=self._config.download_timeout)
        except subprocess.TimeoutExpired:
            self._log("[ERROR] Download timed out")
            process.kill()
            reader.join(timeout=1)
            return -2, error_lines
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

        reader.join(timeout=1)
        return process.returncode, error_lines

    def _is_cookie_error(self, error_output: str) -> bool:
        """Check if error output indicates a cookie/auth problem."""
        keywords = (
            "could not find",
            "cookies",
            "database",
            "chrome",
            "firefox",
            "edge",
            "brave",
            "opera",
            "vivaldi",
            "profile",
            "not found",
            "locked",
        )
        lower = error_output.lower()
        return any(kw in lower for kw in keywords)

    def download(
        self,
        video: Video,
        output_path: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Video:
        output_path.mkdir(parents=True, exist_ok=True)
        video.status = DownloadStatus.DOWNLOADING
        video.path = output_path

        opts = video.options
        fmt = opts.file_format if opts else "mp3"
        safe_title = sanitize_filename(video.title)
        args = self._build_download_args(video)

        self._log_download_start(video, fmt)

        last_error = ""
        cookie_failed = False
        cancelled = False

        try:
            for attempt in range(1, self._config.max_retries + 1):
                if cancel_event and cancel_event.is_set():
                    self._log("[CANCEL] Download cancelled by user")
                    cancelled = True
                    break

                if attempt > 1:
                    wait = attempt - 1
                    self._log(
                        f"[RETRY] Attempt {attempt}/{self._config.max_retries}, waiting {wait}s..."
                    )
                    time.sleep(wait)

                returncode, error_lines = self._run_process(
                    args, output_path, video, cancel_event, progress_callback
                )

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
                    self._is_cookie_error(error_output)
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
            video.path = self._resolve_output_file(output_path, safe_title)

        return video

    def _resolve_output_file(self, output_path: Path, safe_title: str) -> Path | None:
        """Best-effort resolution of the actual downloaded file."""
        try:
            matches = sorted(
                output_path.glob(f"{safe_title}.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            return matches[0] if matches else None
        except OSError:
            return None

    def _get_format_selector(self, fmt: str, quality: str = "best") -> str:
        """Build yt-dlp format selector based on format and quality."""
        if fmt in AUDIO_FORMATS:
            return "bestaudio/best"

        # Formatos de vídeo: usar tabla de calidades
        quality_selector = _VIDEO_QUALITY_SELECTORS.get(quality.lower())
        if quality_selector:
            return quality_selector

        return "bestvideo+bestaudio/best"

    def _get_audio_quality(self, quality: str) -> str:
        """Get audio quality setting for yt-dlp."""
        quality = quality.lower()

        quality_map = {
            "320kbps": "0",
            "256kbps": "1",
            "192kbps": "2",
            "128kbps": "3",
            "96kbps": "4",
            "64kbps": "5",
        }

        return quality_map.get(quality, "0")

    def _parse_duration(self, duration_str: str) -> int:
        try:
            if ":" in duration_str:
                parts = duration_str.split(":")
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return int(float(duration_str))
        except (ValueError, TypeError):
            return 0
