from PyInstaller.utils.hooks import collect_submodules

# Override PyInstaller's bundled hook-PIL.Image.py, which collects every PIL
# image plugin. YouMuDow only ever renders JPEG/PNG/GIF/WebP thumbnails and the
# embedded UI images, so only those plugins need to be frozen. Image.open()
# imports format modules lazily, so the rest would never be reached.
_KEEP = (
    "PIL.JpegImagePlugin",
    "PIL.PngImagePlugin",
    "PIL.GifImagePlugin",
    "PIL.WebPImagePlugin",
)

hiddenimports = [
    name for name in collect_submodules("PIL", lambda mod: "ImagePlugin" in mod) if name in _KEEP
]
