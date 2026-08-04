"""Music & Video Downloader - A modern desktop application."""

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("youmudow")
except (PackageNotFoundError, ImportError):
    __version__ = "dev"
__author__ = "YouMuDow"
