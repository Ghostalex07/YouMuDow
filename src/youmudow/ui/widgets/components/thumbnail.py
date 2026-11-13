"""Thumbnail rendering helpers for YouMuDow."""

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _lanczos_filter() -> Any:
    """Return the LANCZOS resampling filter across Pillow versions.

    Pillow 10 introduced the public ``Image.Resampling`` enum and Pillow 12
    dropped the module-level ``Image.LANCZOS`` alias. Older versions only
    have the alias, so fall back to it when the enum is missing. The alias
    lookup goes through ``getattr`` on purpose: it does not exist in every
    supported Pillow, and a static attribute access would be a type error.
    """
    from PIL import Image  # type: ignore[import-untyped, unused-ignore]

    resampling = getattr(Image, "Resampling", None)
    if resampling is not None:
        return resampling.LANCZOS
    legacy_name = "LANCZOS"
    return getattr(Image, legacy_name)


def photoimage_from_bytes(data: bytes, width: int, height: int) -> Any:
    """Decode image bytes and fit them within ``width`` x ``height``.

    Returns a ``PhotoImage``, or ``None`` when the bytes cannot be decoded.
    """
    # Pillow ships stubs from v12 but not before, so the ignore is needed in
    # one environment and unused in the other.
    from PIL import Image, ImageTk  # type: ignore[import-untyped, unused-ignore]

    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((width, height), _lanczos_filter())
        return ImageTk.PhotoImage(img)
    except (OSError, ValueError) as exc:
        logger.debug("Could not render thumbnail: %s", exc)
        return None
