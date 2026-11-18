"""Tests for the exportable diagnostics report."""

import json
from pathlib import Path

from youmudow.services import diagnostics_service
from youmudow.services.diagnostics_service import (
    SENSITIVE_KEYS,
    build_report,
    export_diagnostics,
    redact_config,
)


def test_report_has_the_expected_sections(monkeypatch):
    monkeypatch.setattr(
        "youmudow.services.diagnostics_service.get_ytdlp_version", lambda: "2026.01.01"
    )
    report = build_report(log_tail="line1", config={"format": "mp3", "cookies_file": "/secret"})
    for needle in ("YouMuDow", "Python", "yt-dlp", "ffmpeg", "cookie", "line1"):
        assert needle.lower() in report.lower()
    assert "/secret" not in report
    assert "<redacted>" in report


def test_missing_log_and_ffmpeg_do_not_break_the_report(monkeypatch):
    monkeypatch.setattr(diagnostics_service, "_ffmpeg_version", lambda: "not found")
    assert "not found" in build_report(log_tail="", config={})


def test_export_writes_the_file(tmp_path):
    destination = export_diagnostics(tmp_path / "diag.txt")
    assert destination.exists()
    assert destination.read_text(encoding="utf-8").startswith("YouMuDow diagnostics")


def test_redact_config_replaces_every_sensitive_value():
    config = {
        "format": "mp3",
        "cookies_file": "/home/me/secret.txt",
        "output_path": "/home/me/Music",
        "search_history": ["private query"],
    }
    redacted = redact_config(config)
    assert redacted["format"] == "mp3"
    for key in ("cookies_file", "output_path", "search_history"):
        assert redacted[key] == "<redacted>"
    assert set(SENSITIVE_KEYS) == {
        "cookies_file",
        "cookies_profile",
        "cookies_from_browser",
        "search_history",
        "output_path",
    }


def test_config_section_is_valid_json(monkeypatch):
    monkeypatch.setattr(
        "youmudow.services.diagnostics_service.get_ytdlp_version", lambda: "2026.01.01"
    )
    report = build_report(log_tail="", config={"format": "mp3"})
    config_block = report.split("Config\n", 1)[1]
    assert json.loads(config_block.split("Log tail", 1)[0])["format"] == "mp3"


def test_export_creates_missing_parent_directories(tmp_path):
    destination = export_diagnostics(tmp_path / "nested" / "dir" / "diag.txt")
    assert destination.exists()
    assert isinstance(destination, Path)
