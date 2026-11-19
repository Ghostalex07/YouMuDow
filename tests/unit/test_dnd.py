"""Tests for optional drag-and-drop support."""

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

from youmudow.ui.dnd import parse_drop_data, register_drop_target


def test_parse_single_url():
    assert parse_drop_data("https://youtube.com/watch?v=abc") == ["https://youtube.com/watch?v=abc"]


def test_parse_braced_list_of_urls():
    payload = "{https://youtube.com/watch?v=a} {https://youtube.com/watch?v=b}"
    assert parse_drop_data(payload) == [
        "https://youtube.com/watch?v=a",
        "https://youtube.com/watch?v=b",
    ]


def test_parse_drops_unsupported_entries():
    payload = "{/home/user/file.txt} {https://youtube.com/watch?v=a}"
    assert parse_drop_data(payload) == ["https://youtube.com/watch?v=a"]


def test_parse_accepts_a_sequence():
    assert parse_drop_data(["https://youtube.com/watch?v=a", "junk"]) == [
        "https://youtube.com/watch?v=a"
    ]


def test_parse_ignores_empty_payloads():
    assert parse_drop_data("") == []
    assert parse_drop_data(None) == []


def test_register_degrades_without_tkinterdnd2(monkeypatch):
    monkeypatch.setitem(sys.modules, "tkinterdnd2", None)
    assert register_drop_target(Mock(), Mock()) is False


def test_register_wires_the_drop_event(monkeypatch):
    module = ModuleType("tkinterdnd2")
    module.DND_FILES = "DND_Files"
    monkeypatch.setitem(sys.modules, "tkinterdnd2", module)
    widget = Mock()
    on_urls = Mock()

    assert register_drop_target(widget, on_urls) is True
    widget.drop_target_register.assert_called_once_with("DND_Files")
    handler = widget.dnd_bind.call_args.args[1]
    handler(SimpleNamespace(data="{https://youtube.com/watch?v=a}"))
    on_urls.assert_called_once_with(["https://youtube.com/watch?v=a"])


def test_register_reports_a_broken_extension(monkeypatch):
    module = ModuleType("tkinterdnd2")
    module.DND_FILES = "DND_Files"
    monkeypatch.setitem(sys.modules, "tkinterdnd2", module)
    widget = Mock()
    widget.drop_target_register.side_effect = RuntimeError("no tkdnd")

    assert register_drop_target(widget, Mock()) is False
