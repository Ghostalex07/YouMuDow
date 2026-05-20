"""Thumbnail service for YouMuDow.

Handles thumbnail URL generation and caching.
"""

from pathlib import Path
from typing import Optional


THUMBNAIL_QUALITIES = ["maxresdefault", "hqdefault", "mqdefault", "sddefault"]


class ThumbnailService:
    """Service for handling video thumbnails."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or Path.home() / ".cache" / "youmudow" / "thumbnails"
        self._memory_cache: dict[str, str] = {}

    def get_url(self, video_id: str, quality: str = "hqdefault") -> str:
        return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"

    def extract_video_id(self, url: str) -> str | None:
        import re
        patterns = [
            r"(?:v=|/v/)([\w-]{11})",
            r"youtu\.be/([\w-]{11})",
            r"shorts/([\w-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_thumbnail_url(self, url: str) -> str:
        video_id = self.extract_video_id(url)
        if video_id:
            return self.get_url(video_id, "hqdefault")
        return ""

    def get_all_quality_urls(self, url: str) -> dict[str, str]:
        video_id = self.extract_video_id(url)
        if not video_id:
            return {}

        return {
            quality: self.get_url(video_id, quality)
            for quality in THUMBNAIL_QUALITIES
        }

    def get_best_thumbnail_url(self, url: str) -> str:
        video_id = self.extract_video_id(url)
        if video_id:
            return self.get_url(video_id, "maxresdefault")
        return ""

    def cache_thumbnail(self, video_id: str, data: bytes) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_dir / f"{video_id}.jpg"
        
        if not cache_path.exists():
            cache_path.write_bytes(data)
            self._memory_cache[video_id] = str(cache_path)
        
        return cache_path

    def get_cached_path(self, video_id: str) -> Optional[Path]:
        if video_id in self._memory_cache:
            path = Path(self._memory_cache[video_id])
            if path.exists():
                return path

        cache_path = self._cache_dir / f"{video_id}.jpg"
        if cache_path.exists():
            self._memory_cache[video_id] = str(cache_path)
            return cache_path

        return None

    def clear_cache(self) -> None:
        self._memory_cache.clear()
        for path in self._cache_dir.glob("*.jpg"):
            path.unlink(missing_ok=True)
