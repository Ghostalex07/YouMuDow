"""Run YouMuDow in development mode."""

import subprocess
import sys


def run_dev() -> None:
    """Run the application in development mode."""
    print("Starting YouMuDow in development mode...")
    subprocess.run([sys.executable, "-m", "youmudow.main"])


if __name__ == "__main__":
    run_dev()
