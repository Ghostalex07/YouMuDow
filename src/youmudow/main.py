"""Main entry point for YouMuDow application."""

import os
from pathlib import Path

from youmudow.app import AppController
from youmudow.ui import MainWindow


def main() -> None:
    """Run the YouMuDow application."""
    controller = AppController()
    
    default_path = Path.home() / "Desktop" / "music"
    default_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(default_path)
    
    window = MainWindow(controller)
    window.run()


if __name__ == "__main__":
    main()
