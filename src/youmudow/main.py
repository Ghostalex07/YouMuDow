"""Main entry point for YouMuDow application."""

import logging

from youmudow.app import AppController
from youmudow.app.config import CONFIG_DIR, AppConfig
from youmudow.logging_config import setup_logging
from youmudow.paths import queue_file
from youmudow.ui import MainWindow

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the YouMuDow application."""
    config = AppConfig()
    setup_logging(
        log_dir=CONFIG_DIR, level=logging.DEBUG if config.get("debug_mode", False) else logging.INFO
    )

    logger.info("Starting YouMuDow")
    controller = AppController(config=config, queue_file=queue_file())

    output_path = config.output_path
    output_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(output_path)
    restored = controller.restore_queue()
    if restored:
        logger.info("Restored %s download(s) from the previous session", restored)

    debug_mode = config.get("debug_mode", False)
    window = MainWindow(controller, debug_mode=debug_mode, config=config, restored_count=restored)
    window.run()


if __name__ == "__main__":
    main()
