"""An indeterminate progress spinner drawn as an arc on a Tk canvas.

The arc is redrawn every frame with an advancing start angle, giving the
impression of rotation. Colors are resolved at draw time so the spinner
stays in sync with theme changes without needing a reconfiguration hook.
"""

import tkinter as tk

from youmudow.ui.styles.constants import _c


class Spinner(tk.Canvas):
    """A small, theme-aware indeterminate spinner."""

    _EXTENT = 240
    _STEP = 30
    _DELAY_MS = 50
    _WIDTH = 2

    def __init__(self, master: tk.Misc, *, size: int = 16, color: str | None = None) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            highlightthickness=0,
            borderwidth=0,
            bg=_c("bg"),
        )
        self._size = size
        self._color = color
        self._running = False
        self._angle = 0
        self._after_id: str | None = None
        self._draw()

    def _resolve_color(self) -> str:
        if self._color is None:
            return _c("primary")
        return self._color if self._color.startswith("#") else _c(self._color)

    def _draw(self) -> None:
        self.delete("all")
        pad = self._WIDTH
        bbox = (pad, pad, self._size - pad, self._size - pad)
        self.create_arc(
            *bbox,
            start=self._angle,
            extent=self._EXTENT,
            style="arc",
            outline=self._resolve_color(),
            width=self._WIDTH,
        )

    def _tick(self) -> None:
        if not self._running:
            return
        self._angle = (self._angle + self._STEP) % 360
        self._draw()
        self._after_id = self.after(self._DELAY_MS, self._tick)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._after_id = self.after(self._DELAY_MS, self._tick)

    def stop(self) -> None:
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def is_running(self) -> bool:
        return self._running
