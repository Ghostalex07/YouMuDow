"""Measure wall-clock time to construct the application (config + controller + window).

Usage: PYTHONPATH=src python3 scripts/measure_startup.py
Prints construction time in milliseconds.
"""

from __future__ import annotations

import sys
import time

from youmudow.app import AppController
from youmudow.app.config import AppConfig
from youmudow.ui import MainWindow


def main() -> int:
    start = time.perf_counter()

    config = AppConfig()
    controller = AppController(config=config)
    output_path = config.output_path
    output_path.mkdir(parents=True, exist_ok=True)
    controller.set_output_path(output_path)
    window = MainWindow(controller, debug_mode=False, config=config)
    window._root.update_idletasks()  # noqa: SLF001 — MainWindow wraps tk.Tk

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    print(f"startup: {elapsed_ms:.1f} ms")

    window.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
