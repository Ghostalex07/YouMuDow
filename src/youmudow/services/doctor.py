"""Environment self-check for ``youmudow-cli doctor``.

Every check returns a result instead of raising, so the command can report all
of them in one pass — which is the whole point when someone is asking for help.
"""

import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from youmudow import __version__
from youmudow.paths import config_dir, database_file
from youmudow.services.library_store import LibraryError, LibraryStore
from youmudow.services.updater_service import get_ytdlp_version

MIN_PYTHON = (3, 10)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def check_python() -> CheckResult:
    version = sys.version.split()[0]
    ok = sys.version_info[:2] >= MIN_PYTHON
    expected = ".".join(str(part) for part in MIN_PYTHON)
    detail = version if ok else f"{version} (needs {expected}+)"
    return CheckResult("Python", ok, detail)


def check_ytdlp() -> CheckResult:
    try:
        version = get_ytdlp_version()
    except Exception as exc:  # noqa: BLE001 - a broken install must not abort the report
        return CheckResult("yt-dlp", False, f"not available ({exc})")
    return CheckResult("yt-dlp", bool(version), version or "not available")


def check_ffmpeg() -> CheckResult:
    binary = shutil.which("ffmpeg")
    if binary is None:
        return CheckResult(
            "ffmpeg", False, "not found in PATH (audio conversion and merging need it)"
        )
    try:
        result = subprocess.run(
            [binary, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CheckResult("ffmpeg", False, f"could not run it ({exc})")
    first_line = (result.stdout or "").splitlines()[0] if result.stdout else ""
    return CheckResult("ffmpeg", result.returncode == 0, first_line or binary)


def _check_writable_file(directory: Path) -> CheckResult:
    name = "Output folder" if directory.name != config_dir().name else "Config folder"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".youmudow-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(name, False, f"{directory} is not writable ({exc})")
    return CheckResult(name, True, str(directory))


def check_output_folder(path: Path) -> CheckResult:
    return _check_writable_file(path)


def check_config_folder(path: Path) -> CheckResult:
    return _check_writable_file(path)


def check_database(path: Path) -> CheckResult:
    try:
        store = LibraryStore(path)
        count = store.count_history()
        store.close()
    except (OSError, sqlite3.Error, LibraryError) as exc:
        return CheckResult("Library database", False, f"{path} ({exc})")
    return CheckResult("Library database", True, f"{path} ({count} downloads)")


def run_checks(output: Path | None = None, db_path: Path | None = None) -> list[CheckResult]:
    return [
        CheckResult("YouMuDow", True, __version__),
        check_python(),
        check_ytdlp(),
        check_ffmpeg(),
        check_output_folder(output or Path.home() / "Downloads"),
        check_config_folder(config_dir()),
        check_database(db_path or database_file()),
    ]


def format_report(results: list[CheckResult]) -> str:
    lines = [
        f"{'ok  ' if result.ok else 'FAIL'} {result.name}: {result.detail}" for result in results
    ]
    failures = sum(1 for result in results if not result.ok)
    lines.append("")
    lines.append("All checks passed." if failures == 0 else f"{failures} check(s) failed.")
    return "\n".join(lines)
