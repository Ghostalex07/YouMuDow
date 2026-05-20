"""Main entry point for YouMuDow application."""

from youmudow.app import AppController
from youmudow.app.config import AppConfig
from youmudow.ui import MainWindow


def main() -> None:
    """Run the YouMuDow application."""
    config = AppConfig()
    
    controller = AppController()
    
    output_path = config.output_path
    output_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(output_path)
    
    debug_mode = config.get("debug_mode", False)
    window = MainWindow(controller, debug_mode=debug_mode, config=config)
    window.run()


if __name__ == "__main__":
    main()
