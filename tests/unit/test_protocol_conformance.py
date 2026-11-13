"""Static conformance checks between MainWindow and MainWindowProtocol.

The widgets receive the window through ``MainWindowProtocol``. If the concrete
window drifts from that surface, mypy must fail here rather than at the first
widget that calls a missing member.
"""

from __future__ import annotations

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.protocols import MainWindowProtocol


class TestMainWindowConformsToProtocol:
    def test_main_window_declares_the_protocol_as_a_base(self):
        from youmudow.ui.window import MainWindow

        assert MainWindowProtocol in MainWindow.__mro__

    def test_protocol_covers_the_widget_surface(self):
        from youmudow.ui.protocols import MainWindowProtocol

        names = set(MainWindowProtocol.__annotations__)
        names |= {name for name in MainWindowProtocol.__dict__ if not name.startswith("_abc")}
        assert {
            "_root",
            "_controller",
            "_selected_video",
            "_results_cards",
            "_search_bar",
            "_detail_panel",
            "_status_bar",
            "_history_panel",
            "_notebook",
            "_main_content_frame",
        } <= names

    def test_widgets_do_not_probe_the_window_with_getattr_or_hasattr(self):
        """Declared members must be used directly, not probed at runtime."""
        import re
        from pathlib import Path

        widgets = Path("src/youmudow/ui/widgets")
        offenders: list[str] = []
        for path in sorted(widgets.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"(?:hasattr|getattr)\(\s*self\._mw\s*,", text):
                offenders.append(f"{path.name}: {match.group(0)}")
        assert offenders == []
