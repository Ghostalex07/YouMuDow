"""Single composition root for every entry point.

The GUI, the CLI and the headless server used to assemble their services
separately, which meant three places to change whenever a dependency moved.
Everything that needs the real graph now starts here.
"""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from youmudow import paths
from youmudow.app.config import AppConfig
from youmudow.app.controller import AppController
from youmudow.services.library_store import LibraryError, LibraryStore

logger = logging.getLogger(__name__)


def open_library_store(
    database: Path | None = None,
    *,
    legacy_dir: Path | None = None,
    legacy_queue: Path | None = None,
    quiet: bool = False,
) -> LibraryStore | None:
    """Open the SQLite library, importing the JSON files left by 1.10 and older.

    Returns None instead of raising: history is a convenience, never a reason to
    refuse to start.
    """
    legacy_dir = legacy_dir if legacy_dir is not None else paths.config_dir()
    try:
        store = LibraryStore(database or paths.database_file())
    except (OSError, sqlite3.Error, LibraryError) as exc:
        message = "Could not open the library database, using JSON history: %s"
        if quiet:
            logger.debug(message, exc)
        else:
            logger.warning(message, exc)
        return None

    store.import_history_json(legacy_dir / "history.json")
    store.import_queue_json(legacy_queue or paths.queue_file())
    return store


@dataclass(frozen=True)
class Services:
    """The wired application graph, built once per process."""

    config: AppConfig
    library_store: LibraryStore | None
    controller: AppController


def build_services(
    config: AppConfig | None = None,
    *,
    library_store: LibraryStore | None = None,
    open_store: bool = True,
) -> Services:
    """Assemble the controller with its services and the shared library."""
    config = config or AppConfig()
    if library_store is None and open_store:
        library_store = open_library_store()
    controller = AppController(
        config=config,
        queue_file=paths.queue_file(),
        library_store=library_store,
    )
    return Services(config=config, library_store=library_store, controller=controller)
