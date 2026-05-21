"""Theme management for YouMuDow."""

from dataclasses import dataclass
from typing import Callable, Literal

from youmudow.ui.styles.colors import Colors, LIGHT_COLORS, DARK_COLORS


ThemeName = Literal["light", "dark"]


@dataclass
class Theme:
    """Theme definition."""

    name: ThemeName
    colors: Colors


class ThemeManager:
    """Manages application themes."""

    _themes = {
        "light": Theme(name="light", colors=LIGHT_COLORS),
        "dark": Theme(name="dark", colors=DARK_COLORS),
    }

    def __init__(self, theme_name: ThemeName = "light") -> None:
        self._current_theme = self._themes[theme_name]
        self._change_callbacks: list[Callable[[Theme], None]] = []

    @property
    def current(self) -> Theme:
        return self._current_theme

    @property
    def colors(self) -> Colors:
        return self._current_theme.colors

    def set_theme(self, theme_name: ThemeName) -> None:
        if theme_name in self._themes:
            self._current_theme = self._themes[theme_name]
            self._notify_change()

    def on_change(self, callback: Callable[[Theme], None]) -> None:
        self._change_callbacks.append(callback)

    def _notify_change(self) -> None:
        for callback in self._change_callbacks:
            callback(self._current_theme)


_default_theme_manager: ThemeManager | None = None


def get_theme_manager() -> ThemeManager:
    global _default_theme_manager
    if _default_theme_manager is None:
        _default_theme_manager = ThemeManager()
    return _default_theme_manager


def set_default_theme(theme_name: ThemeName) -> None:
    get_theme_manager().set_theme(theme_name)
