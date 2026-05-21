import base64
import struct
import zlib
import io

def _make_chunk(chunk_type, data):
    chunk = chunk_type + data
    return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)

def _create_png_bytes():
    size = 64
    cx = size // 2
    pixels = []
    for y in range(size):
        row = []
        for x in range(size):
            # Determine if pixel is part of arrow
            is_arrow = False
            # Shaft: vertical bar in center
            shaft_half = 4
            shaft_top = 8
            shaft_bottom = 34
            if abs(x - cx) <= shaft_half and shaft_top <= y <= shaft_bottom:
                is_arrow = True
            # Head: triangle at bottom
            head_top = 30
            head_bottom = 52
            if head_top <= y <= head_bottom:
                progress = (y - head_top) / (head_bottom - head_top) if head_bottom != head_top else 1
                half_width = shaft_half + progress * 24
                if abs(x - cx) <= half_width:
                    is_arrow = True

            if is_arrow:
                row.append((255, 255, 255, 255))  # white arrow
            else:
                row.append((99, 102, 241, 255))  # indigo bg
        pixels.append(row)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    ihdr = _make_chunk(b'IHDR', ihdr_data)

    raw = b''
    for row in pixels:
        raw += b'\x00'
        for r, g, b, a in row:
            raw += struct.pack('BBBB', r, g, b, a)
    compressed = zlib.compress(raw)
    idat = _make_chunk(b'IDAT', compressed)
    iend = _make_chunk(b'IEND', b'')

    return sig + ihdr + idat + iend

try:
    _png_data = _create_png_bytes()
    ICON_BASE64 = base64.b64encode(_png_data).decode('ascii')
except Exception:
    ICON_BASE64 = ""

def get_icon_image():
    if not ICON_BASE64:
        return None
    try:
        import tkinter as tk
        data = base64.b64decode(ICON_BASE64)
        img = tk.PhotoImage(data=data)
        return img
    except Exception:
        return None
