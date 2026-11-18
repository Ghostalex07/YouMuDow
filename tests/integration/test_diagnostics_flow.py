"""Diagnostics export must never block the Tk main thread."""

import threading
import time

from conftest import pump

import youmudow.services.diagnostics_service as diag


def test_export_runs_off_the_ui_thread(stack, tmp_path, monkeypatch):
    destination = tmp_path / "diag.txt"
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **kwargs: str(destination))
    started = threading.Event()
    release = threading.Event()

    def slow_export(path):
        started.set()
        release.wait(2.0)
        return path

    monkeypatch.setattr(diag, "export_diagnostics", slow_export)

    began = time.monotonic()
    stack.window._on_export_diagnostics()
    elapsed = time.monotonic() - began

    assert elapsed < 0.2, f"export blocked the UI for {elapsed:.2f}s"
    assert started.wait(1.0)
    release.set()
    pump(stack.window, lambda: "Diagnostics saved" in stack.window._status_bar._status_var.get())
