"""Main entry point for YouMuDow application."""

import logging
import sqlite3

from youmudow.app import AppController
from youmudow.app.config import CONFIG_DIR, AppConfig
from youmudow.i18n import resolve_language, set_language
from youmudow.logging_config import setup_logging
from youmudow.paths import database_file, queue_file
from youmudow.services.library_store import LibraryStore
from youmudow.ui import MainWindow

logger = logging.getLogger(__name__)


def _open_library_store() -> LibraryStore | None:
    """Open the SQLite library, falling back to JSON history if it cannot."""
    try:
        store = LibraryStore(database_file())
    except (OSError, sqlite3.Error) as exc:
        logger.warning("Could not open the library database, using JSON history: %s", exc)
        return None
    store.import_history_json(CONFIG_DIR / "history.json")
    store.import_queue_json(queue_file())
    return store


def main() -> None:
    """Run the YouMuDow application."""
    config = AppConfig()
    set_language(resolve_language(config.get_str("language", "auto")))
    setup_logging(
        log_dir=CONFIG_DIR, level=logging.DEBUG if config.get("debug_mode", False) else logging.INFO
    )

    logger.info("Starting YouMuDow")
    controller = AppController(
        config=config, queue_file=queue_file(), library_store=_open_library_store()
    )

    output_path = config.output_path
    output_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(output_path)
    restored = controller.restore_queue()

    debug_mode = config.get("debug_mode", False)
    window = MainWindow(controller, debug_mode=debug_mode, config=config, restored_count=restored)
    window.run()


if __name__ == "__main__":
    main()
