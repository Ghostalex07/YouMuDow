"""File dialogs and OS integration for the main window."""

from __future__ import annotations

import logging
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

logger = logging.getLogger(__name__)


def choose_output_folder() -> str | None:
    """Ask the user for an output folder; return ``None`` when cancelled."""
    return filedialog.askdirectory(title="Select Output Folder") or None


def export_logs(log_terminal, set_status) -> None:
    """Ask for a file and write the log terminal contents to it."""
    default_name = f"youmudow_logs_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S')}.txt"
    path = filedialog.asksaveasfilename(
        title="Export Logs",
        defaultextension=".txt",
        initialfile=default_name,
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
    )
    if not path:
        return
    try:
        log_terminal.export_to_file(Path(path))
        set_status(f"Logs exported to {path}")
    except (OSError, ValueError) as e:
        set_status(f"Export failed: {e}")


def open_output_folder(path: Path) -> bool:
    """Open ``path`` in the system file manager.

    Returns ``False`` when no file manager could be launched, so the caller can
    fall back to reporting the path.
    """
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", str(path)])
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except (OSError, ValueError) as e:
        logger.debug("Could not open folder: %s", e)
        return False
    return True
