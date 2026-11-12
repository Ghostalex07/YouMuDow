"""Shared atomic persistence helpers.

Single source of truth for writing files safely (atomic replace) and
preserving corrupt files so user data is never silently lost.
"""

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def write_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically, leaving no temp file behind."""
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp = Path(f.name)
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        raise


def backup_corrupt(path: Path) -> Path | None:
    """Rename ``path`` to a ``.corrupt`` sibling so it can be inspected later."""
    backup = path.with_suffix(path.suffix + ".corrupt")
    try:
        os.replace(path, backup)
    except OSError as e:
        logger.warning("Could not preserve corrupt file %s: %s", path, e)
        return None
    return backup
