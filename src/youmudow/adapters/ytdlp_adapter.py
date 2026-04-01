"""yt-dlp adapter for YouMuDow.

This module provides a wrapper around yt-dlp functionality.
The adapter pattern allows swapping the underlying downloader implementation
without affecting the rest of the application.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from youmudow.domain.models import Video
from youmudow.domain.enums import DownloadStatus


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
        from youmudow.domain.validators import check_browser_profile, get_fallback_browser, get_all_browser_profiles, SUPPORTED_BROWSERS
        
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
                    profile = opts.cookies_profile
                    
                    valid_browsers = SUPPORTED_BROWSERS
                    if browser in valid_browsers:
                        exists, message = check_browser_profile(browser)
                        if not exists:
                            self._log(f"[AUTH] {message}")
                            fallback = get_fallback_browser()
                            if fallback and fallback != browser:
                                self._log(f"[AUTH] Falling back to {fallback.capitalize()}")
                                browser = fallback
                                profile = None
                            else:
                                self._log(f"[AUTH] Skipping cookies - no browser found")
                                skip_cookies = True
                        else:
                            cookie_arg = browser
                            if profile and profile.lower() not in ["default", "main"]:
                                cookie_arg = f"{browser}:{profile}"
                            args.extend(["--cookies-from-browser", cookie_arg])
                            profile_msg = f" ({profile})" if profile and profile.lower() not in ["default", "main"] else ""
                            self._log(f"[AUTH] Using {browser.capitalize()}{profile_msg} cookies")
                    else:
                        self._log(f"[WARNING] Unknown browser: {browser}")
                elif opts.cookies_file:
                    from pathlib import Path
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
        format_selector = self._get_format_selector(opts.format, opts.quality)
        args.extend([
            "-f", format_selector,
            "-o", str(self._config.output_template),
        ])
        
        if opts.format in ("mp3", "m4a", "opus", "ogg", "flac", "wav"):
            audio_quality = self._get_audio_quality(opts.quality)
            args.extend([
                "--extract-audio",
                "--audio-format", opts.format,
                "--audio-quality", audio_quality,
            ])
        
        if self._config.embed_metadata:
            args.append("--add-metadata")
        
        if self._config.embed_thumbnail and opts.format in ("mp3", "m4a", "opus"):
            args.append("--embed-thumbnail")
        
        if self._config.add_chapters:
            args.append("--embed-chapters")
        
        if opts.subtitles:
            args.extend(["--write-subs", "--sub-langs", opts.subtitle_lang])
            if opts.embed_subtitles:
                args.append("--embed-subs")
        elif self._config.embed_subs:
            args.append("--embed-subs")
        
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
        args.extend([
            "--flat-playlist",
            "--print", "%(url)s | %(title)s | %(uploader)s | %(duration)s",
            f"ytsearch{limit}:{query}",
        ])

        self._log(f"[SEARCH] Searching for: {query}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            videos = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line and " | " in line:
                        parts = line.split(" | ", 3)
                        if len(parts) >= 4:
                            videos.append(Video(
                                title=parts[1].strip(),
                                url=parts[0].strip(),
                                uploader=parts[2].strip(),
                                duration=self._parse_duration(parts[3]),
                            ))
            
            self._log(f"[SEARCH] Found {len(videos)} results")
            return videos
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            self._log(f"[SEARCH] Error: {e}")
            return []

    def get_metadata(self, url: str) -> Video | None:
        args = self._build_base_args(None)
        args.extend([
            "--dump-json",
            "--no-download",
            url,
        ])

        self._log(f"[METADATA] Fetching: {url}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60,
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
                
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError) as e:
            self._log(f"[METADATA] Error: {e}")

        return None

    def get_playlist_videos(self, url: str, limit: int = 53) -> list[Video]:
        """Fetch all videos from a playlist."""
        args = self._build_base_args(None)
        args.extend([
            "--flat-playlist",
            "--print", "%(url)s | %(title)s | %(uploader)s | %(duration)s",
            f"https://www.youtube.com/playlist?list={url.split('list=')[-1].split('&')[0]}",
        ])

        self._log(f"[PLAYLIST] Fetching: {url}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=120,
            )

            videos = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line and " | " in line:
                        parts = line.split(" | ", 3)
                        if len(parts) >= 4:
                            videos.append(Video(
                                title=parts[1].strip(),
                                url=parts[0].strip(),
                                uploader=parts[2].strip(),
                                duration=self._parse_duration(parts[3]),
                            ))

            total = len(videos)
            if total > limit:
                self._log(f"[INFO] Playlist truncated to {limit} videos (found {total})")
            
            self._log(f"[PLAYLIST] Found {min(total, limit)} videos")
            return videos[:limit]

        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            self._log(f"[PLAYLIST] Error: {e}")
            return []

    def download(
        self,
        video: Video,
        output_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> Video:
        from youmudow.domain.validators import sanitize_filename, get_unique_filename, validate_format_quality, parse_yt_dlp_error
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        args = self._build_download_args(video)
        
        video.status = DownloadStatus.DOWNLOADING
        video.path = output_path

        opts = video.options
        fmt = opts.format
        qty = opts.quality

        is_valid, warning = validate_format_quality(fmt, qty)
        if warning:
            self._log(warning)
        
        safe_title = sanitize_filename(video.title)
        
        self._log(f"[DOWNLOAD] Starting: {video.title}")
        self._log(f"[DOWNLOAD] Format: {fmt} ({qty})")
        self._log(f"[DOWNLOAD] Output: {output_path.name}")
        
        metadata_parts = []
        if self._config.embed_metadata:
            metadata_parts.append("metadata")
        if self._config.embed_thumbnail and fmt in ("mp3", "m4a", "opus"):
            metadata_parts.append("thumbnail")
        if self._config.add_chapters:
            metadata_parts.append("chapters")
        
        if metadata_parts:
            self._log(f"[METADATA] Embedding: {', '.join(metadata_parts)}")
        
        if opts.subtitles:
            self._log(f"[SUB] Downloading subtitles ({opts.subtitle_lang})")
            if opts.embed_subtitles:
                self._log(f"[SUB] Embedding subtitles in file")
        
        self._log("-" * 50)

        max_retries = self._config.max_retries
        last_error = ""
        process = None
        cookie_failed = False
        
        try:
            for attempt in range(1, max_retries + 1):
                if attempt > 1:
                    wait_time = attempt - 1
                    self._log(f"[RETRY] Attempt {attempt}/{max_retries}, waiting {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                
                try:
                    process = subprocess.Popen(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        cwd=str(output_path),
                    )

                    error_lines = []
                    
                    import threading
                    output_lines = []
                    output_lock = threading.Lock()
                    
                    def read_output():
                        try:
                            for line in process.stdout:
                                if line:
                                    with output_lock:
                                        output_lines.append(line.strip())
                        except Exception:
                            pass
                    
                    reader = threading.Thread(target=read_output, daemon=True)
                    reader.start()
                    
                    try:
                        process.wait(timeout=self._config.download_timeout)
                    except subprocess.TimeoutExpired:
                        self._log("[ERROR] Download timed out")
                        last_error = "Download timed out"
                        process.kill()
                        break
                    reader.join(timeout=1)
                    
                    for line in output_lines:
                        if line:
                            if "error" in line.lower() or "warning" in line.lower():
                                error_lines.append(line)
                            self._log(line)
                            
                            if progress_callback:
                                progress_info = self._parse_progress(line)
                                if progress_info:
                                    video.progress = progress_info.progress
                                    progress_callback(progress_info.progress, progress_info.speed)

                    if process.returncode == 0:
                        final_path = get_unique_filename(output_path, f"{safe_title}.{fmt}")
                        if final_path.name != f"{safe_title}.{fmt}":
                            self._log(f"[INFO] File renamed to: {final_path.name}")
                        
                        video.status = DownloadStatus.DONE
                        self._log("-" * 50)
                        self._log(f"[DONE] {video.title}")
                        if self._config.embed_metadata:
                            self._log(f"[METADATA] {video.title} tags applied")
                        if self._config.embed_thumbnail and fmt in ("mp3", "m4a", "opus"):
                            self._log(f"[METADATA] {video.title} artwork embedded")
                        break
                    else:
                        error_output = "\n".join(error_lines[-10:])
                        user_message = parse_yt_dlp_error(error_output)
                        last_error = user_message
                        self._log(f"[ERROR] {user_message} (code: {process.returncode})")
                        
                        is_cookie_error = any(x in error_output.lower() for x in [
                            "could not find", "cookies", "database", "chrome", "firefox", 
                            "edge", "brave", "opera", "profile", "not found", "locked"
                        ])
                        
                        if is_cookie_error and opts.use_cookies and not cookie_failed and attempt == 1:
                            cookie_failed = True
                            self._log(f"[AUTH] Failed to load browser cookies, will retry without authentication")
                            args = self._build_download_args(video, skip_cookies=True)
                            continue
                        
                        if attempt < max_retries and not cookie_failed:
                            self._log(f"[RETRY] Will retry in {attempt}s...")

                except subprocess.SubprocessError as e:
                    last_error = str(e)
                    self._log(f"[ERROR] {e}")
                    if attempt < max_retries and not cookie_failed:
                        self._log(f"[RETRY] Will retry in {attempt}s...")
                finally:
                    if process and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()

            if video.status != DownloadStatus.DONE:
                video.status = DownloadStatus.ERROR
                video.error_message = last_error or "Download failed"

        except Exception as e:
            video.status = DownloadStatus.ERROR
            video.error_message = str(e)
            self._log(f"[FATAL] {e}")
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

        return video

    def _get_format_selector(self, fmt: str, quality: str = "best") -> str:
        """Build yt-dlp format selector based on format and quality."""
        quality = quality.lower()
        
        if fmt == "mp3":
            return "bestaudio/best"
        
        if fmt == "mp4":
            if quality == "1080p":
                return "bestvideo[height<=1080]+bestaudio/best"
            elif quality == "720p":
                return "bestvideo[height<=720]+bestaudio/best"
            elif quality == "480p":
                return "bestvideo[height<=480]+bestaudio/best"
            return "bestvideo+bestaudio/best"
        
        if quality == "1080p":
            return "bestvideo[height<=1080]+bestaudio/best"
        elif quality == "720p":
            return "bestvideo[height<=720]+bestaudio/best"
        elif quality == "480p":
            return "bestvideo[height<=480]+bestaudio/best"
        
        return "best"

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


def create_adapter(**kwargs: Any) -> YtdlpAdapter:
    """Factory function to create a configured adapter."""
    config = YtdlpConfig(**kwargs)
    return YtdlpAdapter(config)
