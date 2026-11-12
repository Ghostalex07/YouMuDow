"""Restore and persist the settings owned by the main window.

The options themselves are read and written by ``OptionsPanel``; this module
adds the window-level pieces (geometry, output folder) and the final save, so
``MainWindow`` does not carry a 50-line config block on close.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from typing import Any

from youmudow.ui.widgets.options_panel import OptionsPanel

logger = logging.getLogger(__name__)

_DEFAULT_WIDTH = 1200
_DEFAULT_HEIGHT = 800


def apply_settings(config: Any, options: OptionsPanel, root: tk.Tk) -> None:
    """Load persisted options and window geometry, ignoring corrupt values."""
    if not config:
        return
    try:
        options.load_settings(config)
        geometry = config.window_geometry
        if geometry:
            _restore_geometry(root, geometry)
    except (tk.TclError, KeyError, TypeError, ValueError) as e:
        logger.warning("Could not apply saved config: %s", e)


def save_settings(
    config: Any, options: OptionsPanel, root: tk.Tk, output_path: Path | None
) -> None:
    """Persist options, geometry, output folder and flush the config file."""
    if not config:
        return
    options.save_settings(config)
    try:
        config.window_geometry = root.geometry()
    except (tk.TclError, KeyError, TypeError, ValueError) as e:
        logger.debug("Could not store window geometry: %s", e)
    try:
        if output_path is not None:
            # Never persist ``None`` over a previously saved folder: when the
            # controller cannot report its output path, keep the stored one.
            config.output_path = output_path
    except (tk.TclError, KeyError, TypeError, ValueError) as e:
        logger.debug("Could not store output path: %s", e)
    try:
        config.save()
    except (tk.TclError, KeyError, TypeError, ValueError) as e:
        logger.debug("Could not save config on close: %s", e)


def _restore_geometry(root: tk.Tk, geometry: str) -> None:
    try:
        root.geometry(geometry)
        root.update_idletasks()
        x = root.winfo_x()
        y = root.winfo_y()
        width = root.winfo_width()
        height = root.winfo_height()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        if x + width < 0 or y + height < 0 or x > screen_width or y > screen_height:
            root.geometry(
                f"{min(screen_width, _DEFAULT_WIDTH)}x{min(screen_height, _DEFAULT_HEIGHT)}+0+0"
            )
    except tk.TclError as e:
        logger.debug("Could not restore window geometry: %s", e)
