"""Package YouMuDow for distribution."""

import subprocess
import sys


def package() -> None:
    """Package the application."""
    print("Packaging YouMuDow...")
    subprocess.run([sys.executable, "scripts/build.py"], check=True)
    print("Packaging complete!")


if __name__ == "__main__":
    package()
