#!/usr/bin/env python3
"""
Package script: builds the executable and creates a distributable archive.

Usage:
    python scripts/package.py              # dist/YouMuDow-linux.zip
    python scripts/package.py --version 1.2.0   # dist/YouMuDow-1.2.0-linux.zip

The archive contains the executable plus a README.txt that lists ffmpeg and
yt-dlp as external requirements — they are NOT bundled.
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
SYSTEM = platform.system()


def run_build() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], check=False)
    if result.returncode != 0:
        sys.exit(1)


def create_package(version: str | None = None) -> None:
    suffix = SYSTEM.lower()
    pkg_name = f"YouMuDow-{version}-{suffix}" if version else f"YouMuDow-{suffix}"
    pkg_dir = DIST / pkg_name

    pkg_dir.mkdir(parents=True, exist_ok=True)

    exe_name = "YouMuDow.exe" if SYSTEM == "Windows" else "YouMuDow"
    exe_src = DIST / exe_name
    if exe_src.exists():
        shutil.copy2(exe_src, pkg_dir / exe_name)

    readme = pkg_dir / "README.txt"
    readme.write_text(
        "YouMuDow\n"
        "========\n\n"
        "Requirements:\n"
        "  - ffmpeg: https://ffmpeg.org/download.html\n"
        "  - yt-dlp: pip install yt-dlp (or use Help > Update yt-dlp in the app)\n\n"
        "Usage:\n"
        "  Run YouMuDow (or YouMuDow.exe on Windows)\n"
    )

    archive = shutil.make_archive(str(DIST / pkg_name), "zip", DIST, pkg_name)
    print(f"\nPackage created: {archive}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Package YouMuDow for distribution.")
    parser.add_argument(
        "--version",
        help="Version string to include in the archive name (e.g. 1.2.0)",
        default=None,
    )
    args = parser.parse_args()
    run_build()
    create_package(args.version)
