"""Startup checks and yt-dlp maintenance actions.

Everything here runs off the Tk main loop: the functions take a ``schedule``
callback (normally ``MainWindow._schedule``) and a ``set_status`` callback so
they can be tested with plain callables.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

from youmudow import __version__
from youmudow.domain.validators import is_supported_url
from youmudow.services.environment_service import (
    detect_js_runtime,
    is_ejs_installed,
    repair_youtube_environment,
)
from youmudow.services.updater_service import get_ytdlp_version, update_ytdlp

logger = logging.getLogger(__name__)

Scheduler = Callable[..., Any]
StatusSetter = Callable[[str], None]


def check_clipboard(root: tk.Misc, on_supported_url: Callable[[str], None]) -> None:
    """Offer a supported URL found in the clipboard to ``on_supported_url``."""
    try:
        clipboard = root.clipboard_get()
    except tk.TclError as e:
        logger.debug("Clipboard check failed: %s", e)
        return
    if clipboard and is_supported_url(clipboard.strip()):
        on_supported_url(clipboard.strip())


def check_ytdlp(schedule: Scheduler, set_status: StatusSetter) -> None:
    """Warn when yt-dlp is missing; otherwise check the YouTube environment."""

    def resolve() -> None:
        version = get_ytdlp_version()
        if not version:
            schedule(set_status, "⚠ yt-dlp not found. Install it with: pip install yt-dlp")
            return
        threading.Thread(
            target=run_environment_check, args=(schedule, set_status), daemon=True
        ).start()

    threading.Thread(target=resolve, daemon=True).start()


def run_environment_check(schedule: Scheduler, set_status: StatusSetter) -> None:
    """Auto-detect the YouTube environment and repair it if needed.

    YouTube requires an external JS runtime (deno/node) plus the EJS
    challenge scripts. When a runtime is present but the EJS package is
    missing (a common cause of "HTTP Error 403: Forbidden" on pip-installed
    yt-dlp), install it automatically in the background.
    """
    runtime = detect_js_runtime()
    ejs = is_ejs_installed()

    if runtime and ejs:
        schedule(lambda: set_status(f"YouTube ready (JS runtime: {runtime})"))
        return

    if runtime and not ejs:
        schedule(
            lambda: set_status("YouTube fix: installing JS challenge scripts (yt-dlp[default])...")
        )
        repair_youtube_environment(
            on_success=lambda msg: schedule(lambda: set_status(f"Fix applied: {msg}")),
            on_error=lambda err: schedule(lambda: set_status(f"Fix failed: {err}")),
        )
        return

    schedule(
        lambda: set_status(
            "⚠ YouTube 403 risk: no JS runtime found. "
            "Install deno: curl -fsSL https://deno.land/install.sh | sh"
        )
    )


def repair_environment(schedule: Scheduler, set_status: StatusSetter) -> None:
    """Force a YouTube environment repair (update + cache) in the background."""
    set_status("Repairing YouTube environment (update + cache)...")
    repair_youtube_environment(
        on_success=lambda msg: schedule(lambda: set_status(f"Repair OK: {msg}")),
        on_error=lambda err: schedule(lambda: set_status(f"Repair failed: {err}")),
    )


def install_ytdlp_update(schedule: Scheduler, set_status: StatusSetter) -> None:
    """Update yt-dlp, reporting progress through ``set_status``."""
    set_status("Updating yt-dlp...")

    def on_success(version: str) -> None:
        schedule(lambda: set_status(f"yt-dlp updated to {version}"))

    def on_error(error: str) -> None:
        schedule(lambda: set_status(f"Update failed: {error}"))

    update_ytdlp(on_success, on_error)


def show_ytdlp_version(schedule: Scheduler, set_status: StatusSetter) -> None:
    """Show the installed yt-dlp version in a message box."""
    set_status("Checking yt-dlp version...")

    def resolve() -> None:
        version = get_ytdlp_version()
        schedule(
            messagebox.showinfo,
            "yt-dlp version",
            f"Installed version: {version or 'not found'}",
        )

    threading.Thread(target=resolve, daemon=True).start()


def show_about(schedule: Scheduler, set_status: StatusSetter) -> None:
    """Show the About dialog and refresh the yt-dlp version in the status bar."""
    messagebox.showinfo(
        "About YouMuDow",
        f"YouMuDow v{__version__}\n"
        "Music & Video Downloader\n"
        "Supports YouTube, SoundCloud, Vimeo, Twitter and 1000+ sites via yt-dlp\n"
        "github.com/Ghostalex07/YouMuDow",
    )

    def resolve() -> None:
        version = get_ytdlp_version()
        schedule(set_status, f"yt-dlp: {version or 'not found'}")

    threading.Thread(target=resolve, daemon=True).start()
