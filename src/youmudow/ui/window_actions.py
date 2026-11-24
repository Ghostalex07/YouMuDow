"""Library, import and export actions of the main window.

Split out of ``ui/window.py`` so the window keeps the wiring and these handlers
stay readable. Every method mirrors a ``MainWindow`` handler of the same name.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING

from youmudow.domain.playlist_export import playlist_to_m3u
from youmudow.domain.url_batch import parse_url_list
from youmudow.i18n import t
from youmudow.services.folder_scan import ScannedFile

if TYPE_CHECKING:
    from youmudow.ui.window import MainWindow

logger = logging.getLogger(__name__)


class WindowActions:
    """Handlers that talk to the controller on behalf of the window."""

    def __init__(self, window: MainWindow) -> None:
        self._window = window

    # ------------------------------------------------------------------
    # Playlists and links
    # ------------------------------------------------------------------

    def export_playlist(self) -> None:
        window = self._window
        cards = window._results_cards
        videos = list(cards.playlist_videos) if cards is not None else []
        if not videos:
            return
        path = filedialog.asksaveasfilename(
            title=t("Export list..."),
            defaultextension=".m3u",
            initialfile="playlist.m3u",
            filetypes=[(t("M3U playlist"), "*.m3u"), ("*.*", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(playlist_to_m3u(videos), encoding="utf-8")
        except OSError as exc:
            window._set_status(t("Could not save the file: {error}", error=exc))
            return
        window._set_status(t("Playlist saved to {path}", path=path))

    def import_urls_text(self, text: str) -> int:
        window = self._window
        added = window._controller.enqueue_urls(parse_url_list(text))
        window._set_status(t("Added {count} link(s) to the queue", count=added))
        window._update_button_states()
        return added

    def import_urls(self) -> None:
        window = self._window
        path = filedialog.askopenfilename(
            title=t("Import URLs"),
            filetypes=[(t("Text files"), "*.txt *.csv"), (t("All files"), "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as exc:
            window._set_status(t("Could not read the list: {message}", message=exc))
            return
        self.import_urls_text(text)

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    def scan_folder(self) -> list[ScannedFile]:
        return self._window._controller.scan_library_folder()

    def import_files(self, files: list[ScannedFile]) -> int:
        window = self._window
        imported = window._controller.import_scanned_files(files)
        window._set_status(t("Imported {count} files", count=imported))
        return imported

    def check_library(self) -> list[str]:
        window = self._window
        missing = window._controller.missing_downloads()
        window._set_status(t("Missing files: {count}", count=len(missing)))
        return [entry.title for entry in missing]

    def requeue_missing(self) -> int:
        window = self._window
        added = window._controller.requeue_missing()
        window._set_status(t("Queued {count} missing download(s)", count=added))
        window._update_button_states()
        return added

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def export_diagnostics(self) -> None:
        window = self._window
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="youmudow-diagnostics.txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        destination = Path(path)
        window._set_status(t("Writing diagnostics..."))

        def write() -> None:
            # The report shells out to yt-dlp and ffmpeg: never on the Tk thread.
            from youmudow.services.diagnostics_service import export_diagnostics

            try:
                saved = export_diagnostics(destination, config=window._current_config())
            except OSError as exc:
                logger.exception("Could not export diagnostics")
                window._schedule(window._set_status, f"Could not save diagnostics: {exc}")
                return
            window._schedule(window._set_status, t("Diagnostics saved to {path}", path=saved))

        threading.Thread(target=write, name="diagnostics-export", daemon=True).start()
