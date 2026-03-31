"""Download status enumerations."""

from enum import Enum


class DownloadStatus(str, Enum):
    """Status states for video downloads."""

    READY = "ready"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    DONE = "done"
    ERROR = "error"
