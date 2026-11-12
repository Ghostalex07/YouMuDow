"""Headless smoke boot: build the full MainWindow on the real X display and exit 0.

Usage: PYTHONPATH=src python3 scripts/smoke_boot.py
Prints BOOT OK and exits 0 on success; nonzero on any error.
"""

from __future__ import annotations

import sys

from youmudow.app import AppController
from youmudow.app.config import AppConfig
from youmudow.ui import MainWindow


def _pump(root, seconds: float) -> None:
    """Drive the Tk event loop for a short wall-clock span without mainloop()."""
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        root.update_idletasks()


def main() -> int:
    config = AppConfig()
    controller = AppController(config=config)

    output_path = config.output_path
    output_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(output_path)

    window = MainWindow(controller, debug_mode=False, config=config)
    root = window._root  # noqa: SLF001 — MainWindow wraps tk.Tk
    try:
        _pump(root, 0.5)
        window._on_toggle_theme()  # noqa: SLF001 — intentional smoke exercise
        _pump(root, 0.3)
        print(f"BOOT OK (title={root.title()}, widgets={len(root.winfo_children())})")
    finally:
        window.destroy()

    return 0


if __name__ == "__main__":
    sys.exit(main())
