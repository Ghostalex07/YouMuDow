"""Thumbnail rendering helpers for YouMuDow."""

import io
import logging

from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


def photoimage_from_bytes(data: bytes, width: int, height: int) -> ImageTk.PhotoImage | None:
    """Decode image bytes and fit them within ``width`` x ``height``.

    Returns a ``PhotoImage``, or ``None`` when the bytes cannot be decoded.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((width, height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except (OSError, ValueError) as exc:
        logger.debug("Could not render thumbnail: %s", exc)
        return None
