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

    def _build_base_args(self) -> list[str]:
        args = ["yt-dlp", "--no-check-certificate"]
        
        if self._config.ffmpeg_location:
            args.extend(["--ffmpeg-location", self._config.ffmpeg_location])
        if self._config.cookies_file:
            args.extend(["--cookies", self._config.cookies_file])
        if self._config.user_agent:
            args.extend(["--user-agent", self._config.user_agent])
        
        return args

    def _build_download_args(self, video: Video) -> list[str]:
        """Build arguments for download including metadata options."""
        args = self._build_base_args()
        
        args.extend([
            "-f", self._get_format_selector(video.format),
            "-o", str(self._config.output_template),
        ])
        
        if video.format in ("mp3", "m4a", "opus", "ogg", "flac", "wav"):
            args.extend([
                "--extract-audio",
                "--audio-format", video.format,
                "--audio-quality", self._config.audio_quality,
            ])
        
        if self._config.embed_metadata:
            args.append("--add-metadata")
        
        if self._config.embed_thumbnail and video.format in ("mp3", "m4a", "opus"):
            args.append("--embed-thumbnail")
        
        if self._config.add_chapters:
            args.append("--embed-chapters")
        
        if self._config.embed_subs:
            args.append("--embed-subs")
        
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
        args = self._build_base_args()
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
        args = self._build_base_args()
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

    def download(
        self,
        video: Video,
        output_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> Video:
        output_path.mkdir(parents=True, exist_ok=True)

        args = self._build_download_args(video)
        
        video.status = DownloadStatus.DOWNLOADING
        video.path = output_path

        self._log(f"[DOWNLOAD] Starting: {video.title}")
        self._log(f"[DOWNLOAD] Format: {video.format}")
        self._log(f"[DOWNLOAD] Output: {output_path}")
        
        metadata_parts = []
        if self._config.embed_metadata:
            metadata_parts.append("metadata")
        if self._config.embed_thumbnail and video.format in ("mp3", "m4a", "opus"):
            metadata_parts.append("thumbnail")
        if self._config.add_chapters:
            metadata_parts.append("chapters")
        
        if metadata_parts:
            self._log(f"[METADATA] Embedding: {', '.join(metadata_parts)}")
        
        self._log("-" * 50)

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

            stdout = process.stdout
            if stdout:
                for line in stdout:
                    line = line.strip()
                    if line:
                        self._log(line)
                        
                        if progress_callback:
                            progress_info = self._parse_progress(line)
                            if progress_info:
                                video.progress = progress_info.progress
                                progress_callback(progress_info.progress, progress_info.speed)

            process.wait()

            if process.returncode == 0:
                video.status = DownloadStatus.DONE
                self._log("-" * 50)
                self._log(f"[DONE] {video.title}")
                if self._config.embed_metadata:
                    self._log(f"[METADATA] {video.title} tags applied")
                if self._config.embed_thumbnail and video.format in ("mp3", "m4a", "opus"):
                    self._log(f"[METADATA] {video.title} artwork embedded")
            else:
                video.status = DownloadStatus.ERROR
                video.error_message = "Download failed"
                self._log(f"[ERROR] Download failed with code {process.returncode}")

        except subprocess.SubprocessError as e:
            video.status = DownloadStatus.ERROR
            video.error_message = str(e)
            self._log(f"[ERROR] {e}")

        return video

    def _get_format_selector(self, fmt: str) -> str:
        if fmt == "mp3":
            return "bestaudio/best"
        elif fmt == "mp4":
            return "bestvideo+bestaudio/best"
        return "best"

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
