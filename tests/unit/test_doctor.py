"""Tests for the environment self-check."""

import sqlite3
from pathlib import Path

from youmudow.services import doctor


def test_run_checks_covers_every_subsystem(tmp_path, monkeypatch):
    # ffmpeg and yt-dlp presence is machine-specific; the composition is what
    # this test pins, so they answer with fixed results.
    monkeypatch.setattr(doctor, "check_ffmpeg", lambda: doctor.CheckResult("ffmpeg", True, "x"))
    monkeypatch.setattr(doctor, "check_ytdlp", lambda: doctor.CheckResult("yt-dlp", True, "y"))

    results = doctor.run_checks(output=tmp_path / "out", db_path=tmp_path / "lib.db")

    assert [r.name for r in results] == [
        "YouMuDow",
        "Python",
        "yt-dlp",
        "ffmpeg",
        "Output folder",
        "Config folder",
        "Library database",
    ]
    assert all(r.ok for r in results)


def test_missing_ffmpeg_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _name: None)
    result = doctor.check_ffmpeg()
    assert result.ok is False
    assert "PATH" in result.detail


def test_unwritable_output_folder_is_reported(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder", encoding="utf-8")
    result = doctor.check_output_folder(blocker / "nested")
    assert result.ok is False
    assert "not writable" in result.detail


def test_broken_database_is_reported(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a database at all" * 10)
    result = doctor.check_database(path)
    assert result.ok is False


def test_database_check_counts_downloads(tmp_path):
    path = tmp_path / "lib.db"
    store = doctor.LibraryStore(path)
    store.close()
    result = doctor.check_database(path)
    assert result.ok is True
    assert "0 downloads" in result.detail


def test_report_says_when_everything_is_fine():
    report = doctor.format_report([doctor.CheckResult("YouMuDow", True, "1.20.0")])
    assert report.startswith("ok   YouMuDow")
    assert report.endswith("All checks passed.")


def test_report_counts_failures():
    report = doctor.format_report(
        [
            doctor.CheckResult("A", True, "fine"),
            doctor.CheckResult("B", False, "broken"),
        ]
    )
    assert "FAIL B: broken" in report
    assert report.endswith("1 check(s) failed.")


def test_python_version_is_always_supported_here():
    assert doctor.check_python().ok is True


def test_ytdlp_failure_does_not_raise(monkeypatch):
    def explode():
        raise RuntimeError("pip is broken")

    monkeypatch.setattr(doctor, "get_ytdlp_version", explode)
    result = doctor.check_ytdlp()
    assert result.ok is False
    assert "pip is broken" in result.detail


def test_sqlite_error_is_caught(monkeypatch):
    def explode(_path):
        raise sqlite3.DatabaseError("locked")

    monkeypatch.setattr(doctor, "LibraryStore", explode)
    assert doctor.check_database(Path("/tmp/x.db")).ok is False
