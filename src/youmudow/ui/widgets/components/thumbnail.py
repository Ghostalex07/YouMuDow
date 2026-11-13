"""Thumbnail rendering helpers for YouMuDow."""

import io
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PIL import ImageTk  # type: ignore[import-untyped]


def photoimage_from_bytes(data: bytes, width: int, height: int) -> "ImageTk.PhotoImage | None":
    """Decode image bytes and fit them within ``width`` x ``height``.

    Returns a ``PhotoImage``, or ``None`` when the bytes cannot be decoded.
    """
    from PIL import Image, ImageTk

    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((width, height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except (OSError, ValueError) as exc:
        logger.debug("Could not render thumbnail: %s", exc)
        return None
