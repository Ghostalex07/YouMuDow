"""Main entry point for YouMuDow application."""

import logging

from youmudow.app import AppController
from youmudow.app.config import AppConfig, CONFIG_DIR
from youmudow.logging_config import setup_logging
from youmudow.ui import MainWindow

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the YouMuDow application."""
    config = AppConfig()
    setup_logging(
        log_dir=CONFIG_DIR, level=logging.DEBUG if config.get("debug_mode", False) else logging.INFO
    )

    logger.info("Starting YouMuDow")
    controller = AppController(config=config)

    output_path = config.output_path
    output_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(output_path)

    debug_mode = config.get("debug_mode", False)
    window = MainWindow(controller, debug_mode=debug_mode, config=config)
    window.run()


if __name__ == "__main__":
    main()
