"""Centralized logging configuration for YouMuDow."""

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE_NAME = "youmudow.log"

_configured = False


def setup_logging(
    log_dir: Path | None = None,
    level: int = logging.INFO,
) -> None:
    """Configure the root logger once.

    Applies a consistent format, an optional file handler writing to
    ``log_dir/youmudow.log``, and a stream handler for console output.
    Calling this function more than once is a no-op.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / LOG_FILE_NAME, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            root.warning("Could not create log file in %s", log_dir)

    _configured = True
