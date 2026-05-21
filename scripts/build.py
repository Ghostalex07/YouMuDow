#!/usr/bin/env python3
"""Build script for YouMuDow using PyInstaller."""

import subprocess
import sys
import shutil
import platform
from pathlib import Path

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ENTRY = ROOT / "src" / "youmudow" / "main.py"


def clean() -> None:
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
    for spec in ROOT.glob("*.spec"):
        spec.unlink()
    print("Cleaned previous builds.")


def build() -> None:
    system = platform.system()
    separator = ";" if system == "Windows" else ":"

    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", "YouMuDow",
        "--onefile",
        "--windowed",
        "--clean",
        f"--add-data", f"{ROOT / 'src' / 'youmudow'}{separator}youmudow",
        "--hidden-import", "youmudow",
        "--hidden-import", "youmudow.ui",
        "--hidden-import", "youmudow.ui.styles",
        "--hidden-import", "youmudow.ui.styles.colors",
        "--hidden-import", "youmudow.ui.styles.theme",
        "--hidden-import", "youmudow.ui.styles.styles",
        "--hidden-import", "youmudow.ui.widgets",
        "--hidden-import", "youmudow.app",
        "--hidden-import", "youmudow.services",
        "--hidden-import", "youmudow.adapters",
        "--hidden-import", "youmudow.domain",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageTk",
        str(ENTRY),
    ]

    print(f"Building for {system}...")
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode == 0:
        output = DIST / ("YouMuDow.exe" if system == "Windows" else "YouMuDow")
        print(f"\nBuild successful: {output}")
        print("\nNOTE: ffmpeg and yt-dlp must be installed separately by the user.")
        print("Consider bundling them or pointing users to the README.")
    else:
        print("Build failed.")
        sys.exit(1)


if __name__ == "__main__":
    clean()
    build()
