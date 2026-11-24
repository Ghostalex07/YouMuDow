"""Main entry point for YouMuDow application."""

import logging

from youmudow.app.config import CONFIG_DIR, AppConfig
from youmudow.bootstrap import build_services
from youmudow.i18n import resolve_language, set_language
from youmudow.logging_config import setup_logging
from youmudow.ui import MainWindow

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the YouMuDow application."""
    config = AppConfig()
    set_language(resolve_language(config.get_str("language", "auto")))
    setup_logging(
        log_dir=CONFIG_DIR, level=logging.DEBUG if config.get("debug_mode", False) else logging.INFO
    )

    logger.info("Starting YouMuDow")
    controller = build_services(config).controller

    output_path = config.output_path
    output_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(output_path)
    restored = controller.restore_queue()

    debug_mode = config.get("debug_mode", False)
    window = MainWindow(controller, debug_mode=debug_mode, config=config, restored_count=restored)
    window.run()


if __name__ == "__main__":
    main()
