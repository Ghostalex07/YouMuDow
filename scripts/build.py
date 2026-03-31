"""Build script for YouMuDow."""

import subprocess
import sys


def build() -> None:
    """Build the project."""
    print("Building YouMuDow...")
    subprocess.run([sys.executable, "-m", "build"], check=True)
    print("Build complete!")


if __name__ == "__main__":
    build()
