"""Domain exceptions for YouMuDow.

Custom exception hierarchy so services can raise clear, typed errors
and let the UI layer decide how to present them.
"""


class YouMuDowError(Exception):
    """Base class for all YouMuDow errors."""


class InvalidUrlError(YouMuDowError, ValueError):
    """Raised when a provided URL is empty, malformed or unsupported."""


class DownloadError(YouMuDowError):
    """Raised when a download operation fails."""


class YtDlpError(DownloadError):
    """Raised when the underlying yt-dlp tool fails."""


class YtDlpNotFoundError(YtDlpError):
    """Raised when the yt-dlp binary is not available on the system."""


class ConfigurationError(YouMuDowError):
    """Raised when application configuration is invalid or unreadable."""
