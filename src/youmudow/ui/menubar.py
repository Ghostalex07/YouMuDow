"""Menu bar construction for the main window.

The menu tree is declarative: ``MainWindow`` builds a ``MenuCallbacks`` bundle
and this module turns it into Tk menus, so the window keeps no menu-building
code of its own.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

from youmudow.i18n import available_languages, get_language, t
from youmudow.ui.styles.constants import _c


@dataclass(frozen=True)
class MenuCallbacks:
    """Actions reachable from the menu bar."""

    set_output: Callable[[], None]
    open_output_folder: Callable[[], None]
    export_logs: Callable[[], None]
    clear_thumbnail_cache: Callable[[], None]
    close: Callable[[], None]
    quit: Callable[[], None]
    start_queue: Callable[[], None]
    clear_queue: Callable[[], None]
    toggle_debug: Callable[[], None]
    open_guide: Callable[[], None]
    toggle_theme: Callable[[], None]
    toggle_tray: Callable[[], None]
    update_ytdlp: Callable[[], None]
    repair_youtube: Callable[[], None]
    show_ytdlp_version: Callable[[], None]
    export_diagnostics: Callable[[], None]
    download_update: Callable[[], None]
    set_language: Callable[[str], None]
    about: Callable[[], None]


def _language_command(callbacks: MenuCallbacks, code: str) -> Callable[[], None]:
    def apply() -> None:
        callbacks.set_language(code)

    return apply


def _submenu(menubar: tk.Menu) -> tk.Menu:
    return tk.Menu(menubar, tearoff=0, bg=_c("surface"), fg=_c("text"), bd=1)


def build_menubar(
    menubar: tk.Menu,
    callbacks: MenuCallbacks,
    debug_var: tk.BooleanVar,
    tray_var: tk.BooleanVar | None = None,
    language_var: tk.StringVar | None = None,
) -> None:
    """Fill ``menubar`` with the File/Queue/View/Help menus."""
    if tray_var is None:
        tray_var = tk.BooleanVar(value=False)
    if language_var is None:
        language_var = tk.StringVar(value="auto")
    file_menu = _submenu(menubar)
    menubar.add_cascade(label=t("File"), menu=file_menu)
    file_menu.add_command(label=t("Set Output Folder"), command=callbacks.set_output)
    file_menu.add_command(
        label=t("Open Output Folder    Ctrl+O"), command=callbacks.open_output_folder
    )
    file_menu.add_command(label=t("Export Logs..."), command=callbacks.export_logs)
    file_menu.add_separator()
    file_menu.add_command(label=t("Clear Thumbnail Cache"), command=callbacks.clear_thumbnail_cache)
    file_menu.add_separator()
    file_menu.add_command(label=t("Exit"), command=callbacks.quit)

    queue_menu = _submenu(menubar)
    menubar.add_cascade(label=t("Queue"), menu=queue_menu)
    queue_menu.add_command(label=t("Start Downloads"), command=callbacks.start_queue)
    queue_menu.add_command(label=t("Clear Queue"), command=callbacks.clear_queue)

    view_menu = _submenu(menubar)
    menubar.add_cascade(label=t("View"), menu=view_menu)
    view_menu.add_checkbutton(
        label=t("Debug Mode"), variable=debug_var, command=callbacks.toggle_debug
    )
    view_menu.add_checkbutton(
        label=t("Keep Running in Tray"), variable=tray_var, command=callbacks.toggle_tray
    )
    view_menu.add_separator()
    view_menu.add_command(label=t("User Guide    F1"), command=callbacks.open_guide)
    language_menu = _submenu(view_menu)
    view_menu.add_cascade(label=t("Language"), menu=language_menu)
    for code, name in available_languages().items():
        language_menu.add_radiobutton(
            label=name,
            value=code,
            variable=language_var,
            command=_language_command(callbacks, code),
        )
    language_menu.add_separator()
    language_menu.add_radiobutton(
        label="Automático" if get_language() == "es" else "Automatic",
        value="auto",
        variable=language_var,
        command=_language_command(callbacks, "auto"),
    )
    view_menu.add_separator()
    view_menu.add_command(
        label=t("Toggle Light/Dark Theme    Ctrl+T"), command=callbacks.toggle_theme
    )

    help_menu = _submenu(menubar)
    menubar.add_cascade(label=t("Help"), menu=help_menu)
    help_menu.add_command(label=t("Update yt-dlp"), command=callbacks.update_ytdlp)
    help_menu.add_command(label=t("Repair YouTube Downloads"), command=callbacks.repair_youtube)
    help_menu.add_command(label=t("Export Diagnostics..."), command=callbacks.export_diagnostics)
    help_menu.add_command(label=t("Download Update..."), command=callbacks.download_update)
    help_menu.add_command(label="yt-dlp version", command=callbacks.show_ytdlp_version)
    help_menu.add_separator()
    help_menu.add_command(label=t("About"), command=callbacks.about)


def create_menubar(
    root: tk.Tk,
    callbacks: MenuCallbacks,
    debug_var: tk.BooleanVar,
    tray_var: tk.BooleanVar | None = None,
    language_var: tk.StringVar | None = None,
) -> tk.Menu:
    """Create the menu bar, attach it to ``root`` and populate it."""
    menubar = tk.Menu(root, bg=_c("bg"), fg=_c("text"), bd=0, relief="flat")
    root.configure(menu=menubar)
    build_menubar(menubar, callbacks, debug_var, tray_var)
    return menubar
