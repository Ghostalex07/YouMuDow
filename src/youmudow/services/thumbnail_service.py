"""Thumbnail service for YouMuDow.

Handles thumbnail URL generation for YouTube videos.
"""

import re


class ThumbnailService:
    """Service for generating YouTube thumbnail URLs."""

    def extract_video_id(self, url: str) -> str | None:
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

    def get_url(self, video_id: str, quality: str = "hqdefault") -> str:
        return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"

    def get_thumbnail_url(self, url: str) -> str:
        video_id = self.extract_video_id(url)
        if video_id:
            return self.get_url(video_id, "hqdefault")
        return ""
