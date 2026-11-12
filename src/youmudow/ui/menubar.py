"""Menu bar construction for the main window.

The menu tree is declarative: ``MainWindow`` builds a ``MenuCallbacks`` bundle
and this module turns it into Tk menus, so the window keeps no menu-building
code of its own.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

from youmudow.ui.styles.constants import _c


@dataclass(frozen=True)
class MenuCallbacks:
    """Actions reachable from the menu bar."""

    set_output: Callable[[], None]
    open_output_folder: Callable[[], None]
    export_logs: Callable[[], None]
    close: Callable[[], None]
    start_queue: Callable[[], None]
    clear_queue: Callable[[], None]
    toggle_debug: Callable[[], None]
    toggle_theme: Callable[[], None]
    update_ytdlp: Callable[[], None]
    repair_youtube: Callable[[], None]
    show_ytdlp_version: Callable[[], None]
    about: Callable[[], None]


def _submenu(menubar: tk.Menu) -> tk.Menu:
    return tk.Menu(menubar, tearoff=0, bg=_c("surface"), fg=_c("text"), bd=1)


def build_menubar(menubar: tk.Menu, callbacks: MenuCallbacks, debug_var: tk.BooleanVar) -> None:
    """Fill ``menubar`` with the File/Queue/View/Help menus."""
    file_menu = _submenu(menubar)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Set Output Folder", command=callbacks.set_output)
    file_menu.add_command(
        label="Open Output Folder    Ctrl+O", command=callbacks.open_output_folder
    )
    file_menu.add_command(label="Export Logs...", command=callbacks.export_logs)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=callbacks.close)

    queue_menu = _submenu(menubar)
    menubar.add_cascade(label="Queue", menu=queue_menu)
    queue_menu.add_command(label="Start Downloads", command=callbacks.start_queue)
    queue_menu.add_command(label="Clear Queue", command=callbacks.clear_queue)

    view_menu = _submenu(menubar)
    menubar.add_cascade(label="View", menu=view_menu)
    view_menu.add_checkbutton(
        label="Debug Mode", variable=debug_var, command=callbacks.toggle_debug
    )
    view_menu.add_separator()
    view_menu.add_command(label="Toggle Light/Dark Theme    Ctrl+T", command=callbacks.toggle_theme)

    help_menu = _submenu(menubar)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="Update yt-dlp", command=callbacks.update_ytdlp)
    help_menu.add_command(label="Repair YouTube Downloads", command=callbacks.repair_youtube)
    help_menu.add_command(label="yt-dlp version", command=callbacks.show_ytdlp_version)
    help_menu.add_separator()
    help_menu.add_command(label="About", command=callbacks.about)


def create_menubar(root: tk.Tk, callbacks: MenuCallbacks, debug_var: tk.BooleanVar) -> tk.Menu:
    """Create the menu bar, attach it to ``root`` and populate it."""
    menubar = tk.Menu(root, bg=_c("bg"), fg=_c("text"), bd=0, relief="flat")
    root.configure(menu=menubar)
    build_menubar(menubar, callbacks, debug_var)
    return menubar
