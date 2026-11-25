"""Keyboard shortcuts that do not need a display."""

from youmudow.ui import shortcuts


def test_tab_shortcuts_map_numbers_to_indexes():
    assert shortcuts.tab_index_for("1") == 0
    assert shortcuts.tab_index_for("3") == 2
    assert shortcuts.tab_index_for("9") is None
