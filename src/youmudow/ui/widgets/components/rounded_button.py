"""A rounded button drawn on a Tk canvas.

Replaces hand-rolled ``tk.Button`` instances, which each carried their own
``_theme`` dict and hover bindings. Variants map to the single color system
in ``constants._c`` and stay in sync with theme changes because colors are
resolved at draw time, not cached.
"""

import tkinter as tk
from tkinter import font as tkfont

from youmudow.ui.styles.constants import FONT, _c

# fill: color key or ``None`` (transparent). text: hex literal or color key.
# hover: fill key used while the pointer is over the button.
_VARIANTS: dict[str, dict[str, str | None]] = {
    "primary": {"fill": "primary", "text": "#FFFFFF", "hover": "secondary"},
    "secondary": {"fill": "surface", "text": "text", "hover": "hover", "border": "border"},
    "danger": {"fill": "error", "text": "#FFFFFF", "hover": "error"},
    "ghost": {"fill": None, "text": "primary", "hover": "hover"},
}


class RoundedButton(tk.Canvas):
    """A rounded, theme-aware button with hover and disabled states."""

    _RADIUS = 8
    _PADDING_X = 16

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        *,
        command: object | None = None,
        variant: str = "primary",
        width: int | None = None,
        height: int = 34,
        font: tuple | None = None,
    ) -> None:
        super().__init__(
            master,
            height=height,
            width=width or self._measure_width(text, font),
            highlightthickness=0,
            borderwidth=0,
            bg=_c("bg"),
        )
        if variant not in _VARIANTS:
            raise ValueError(f"unknown variant: {variant!r}")
        self._command = command
        self._variant = variant
        self._enabled = True
        self._hovered = False
        self._label_text = text
        self._font = font or FONT["body"]
        self._fill_color: str | None = None
        self._text_color: str = _c("text")
        self._update_colors()

        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    @staticmethod
    def _measure_width(text: str, font: tuple | None) -> int:
        return tkfont.Font(font=font or FONT["body"]).measure(text) + 2 * RoundedButton._PADDING_X

    @staticmethod
    def _resolve(value: str) -> str:
        return value if value.startswith("#") else _c(value)

    def _update_colors(self) -> None:
        v = _VARIANTS[self._variant]
        if not self._enabled:
            self._fill_color = _c("disabled") if v["fill"] is not None else None
            self._text_color = _c("text_secondary")
            return
        fill = v["fill"]
        if fill is not None:
            self._fill_color = _c(v["hover"]) if self._hovered else _c(fill)
        else:
            self._fill_color = _c("hover") if self._hovered else None
        self._text_color = self._resolve(v["text"])

    def _draw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return

        v = _VARIANTS[self._variant]
        fill = self._fill_color or _c("bg")
        outline = _c(v["border"]) if v.get("border") else fill

        self._rounded_rect(
            0.5, 0.5, width - 0.5, height - 0.5, self._RADIUS, fill=fill, outline=outline
        )
        self.create_text(
            width / 2,
            height / 2,
            text=self._label_text,
            fill=self._text_color,
            font=self._font,
        )

    def _rounded_rect(
        self, x1: float, y1: float, x2: float, y2: float, radius: int, **kwargs: object
    ) -> int:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def set_text(self, text: str) -> None:
        self._label_text = text
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._update_colors()
        self._draw()

    def invoke(self) -> None:
        if self._enabled and self._command is not None:
            self._command()

    def _on_enter(self, _event: tk.Event) -> None:
        if not self._enabled:
            return
        self._hovered = True
        self._update_colors()
        self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        if not self._enabled:
            return
        self._hovered = False
        self._update_colors()
        self._draw()

    def _on_click(self, _event: tk.Event) -> None:
        self.invoke()
