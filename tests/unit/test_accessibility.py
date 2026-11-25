"""Contrast and keyboard-accessibility guards."""

from youmudow.ui.styles.colors import DARK_COLORS, LIGHT_COLORS


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(first: str, second: str) -> float:
    a, b = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def test_body_text_meets_wcag_aa_on_both_backgrounds():
    for colors in (DARK_COLORS, LIGHT_COLORS):
        assert _ratio(colors.TEXT, colors.BACKGROUND) >= 4.5
        assert _ratio(colors.TEXT, colors.SURFACE) >= 4.5


def test_secondary_text_meets_wcag_aa():
    for colors in (DARK_COLORS, LIGHT_COLORS):
        assert _ratio(colors.TEXT_SECONDARY, colors.BACKGROUND) >= 4.5
        assert _ratio(colors.TEXT_SECONDARY, colors.SURFACE) >= 4.5
