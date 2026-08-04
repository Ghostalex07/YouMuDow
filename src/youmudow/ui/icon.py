"""Programmatically generated application icon.

The icon is rendered at import time and embedded as base64, avoiding any
external asset files or binary dependencies in the package.
"""

import base64
import struct
import tkinter as tk
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    chunk = chunk_type + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)


def _create_png_bytes(size: int = 64) -> bytes:
    """Render a download-arrow icon on an indigo background as PNG bytes."""
    half = size // 2
    rows: list[bytes] = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            is_arrow = _is_arrow_pixel(x, y, half)
            if is_arrow:
                row += b"\xff\xff\xff\xff"  # white arrow
            else:
                row += b"\x63\x66\xf1\xff"  # indigo background
        rows.append(b"\x00" + bytes(row))

    raw = b"".join(rows)
    ihdr = _make_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    idat = _make_chunk(b"IDAT", zlib.compress(raw))
    iend = _make_chunk(b"IEND", b"")
    return _SIGNATURE + ihdr + idat + iend


def _is_arrow_pixel(x: int, y: int, half: int) -> bool:
    shaft_half = 4
    if abs(x - half) <= shaft_half and 8 <= y <= 34:
        return True
    if 30 <= y <= 52:
        progress = (y - 30) / 22
        return abs(x - half) <= shaft_half + progress * 24
    return False


def _build_icon_data() -> str:
    try:
        return base64.b64encode(_create_png_bytes()).decode("ascii")
    except (ValueError, struct.error, zlib.error):
        return ""


ICON_BASE64 = _build_icon_data()


def get_icon_image() -> tk.PhotoImage | None:
    """Return a Tkinter PhotoImage for the app icon, or None if unavailable."""
    if not ICON_BASE64:
        return None
    try:
        return tk.PhotoImage(data=base64.b64decode(ICON_BASE64))
    except (ValueError, OSError, tk.TclError):
        return None
