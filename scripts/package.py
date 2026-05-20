#!/usr/bin/env python3
"""
Package script: builds the executable and creates a distributable folder
with ffmpeg and yt-dlp bundled (Windows only for now).

Usage:
    python scripts/package.py

Output: dist/YouMuDow-<platform>/
    YouMuDow.exe (or YouMuDow on Linux/macOS)
    README.txt
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
SYSTEM = platform.system()
PKG_NAME = f"YouMuDow-{SYSTEM.lower()}"
PKG_DIR = DIST / PKG_NAME


def run_build() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")])
    if result.returncode != 0:
        sys.exit(1)


def create_package() -> None:
    PKG_DIR.mkdir(parents=True, exist_ok=True)

    exe_name = "YouMuDow.exe" if SYSTEM == "Windows" else "YouMuDow"
    exe_src = DIST / exe_name
    if exe_src.exists():
        shutil.copy2(exe_src, PKG_DIR / exe_name)

    readme = PKG_DIR / "README.txt"
    readme.write_text(
        "YouMuDow\n"
        "========\n\n"
        "Requirements:\n"
        "  - ffmpeg: https://ffmpeg.org/download.html\n"
        "  - yt-dlp: pip install yt-dlp (or use Help > Update yt-dlp in the app)\n\n"
        "Usage:\n"
        "  Run YouMuDow (or YouMuDow.exe on Windows)\n"
    )

    archive = shutil.make_archive(str(DIST / PKG_NAME), "zip", DIST, PKG_NAME)
    print(f"\nPackage created: {archive}")


if __name__ == "__main__":
    run_build()
    create_package()
