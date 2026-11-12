"""Tests for the UI design tokens (type scale)."""

from youmudow.ui.styles.constants import FONT


def test_type_scale_sizes() -> None:
    assert FONT["display"][1] == 18
    assert FONT["h1"][1] == 15
    assert FONT["h2"][1] == 13
    assert FONT["h3"][1] == 12
    assert FONT["body"][1] == 11
    assert FONT["small"][1] == 10
    assert FONT["label"][1] == 10


def test_type_scale_keys_preserved() -> None:
    assert {"h1", "h2", "h3", "body", "small", "label", "mono"} <= set(FONT)
