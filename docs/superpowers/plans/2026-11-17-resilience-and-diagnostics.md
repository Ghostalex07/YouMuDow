# Resilience, Tray and Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** downloads survive transient failures and app restarts, the window can live in the system tray, and users can hand support one combined diagnostics file.

**Architecture:** retry lives in `DownloadWorker` (the only place that owns a single download attempt); queue persistence is a small serialisation module used by `DownloadService`; the tray is an isolated `ui/tray.py` behind an optional dependency; diagnostics is a pure report builder in `services/` plus one menu command.

**Tech Stack:** Python 3.10, tkinter, `pystray>=0.19`, Pillow (already a dependency).

**Spec:** `docs/superpowers/specs/2026-11-17-next-features.md`

**Prerequisite:** Task 3 reuses the `stack` fixture and `pump()` helper from
`docs/superpowers/plans/2026-11-17-full-stack-ui-tests.md`. Execute that plan
first, or move the tray window test into that suite instead of creating a new
file.

## Global Constraints

- Python 3.10+, ruff line length 100, layers only depend upwards.
- No Tk call from a worker thread; tray callbacks marshal through
  `MainWindow._schedule`.
- Optional integrations (`pystray`, `ffmpeg`, `notify-send`) must degrade with
  a log line, never an exception.
- Config writes go through `AppConfig.set()` + `save()` (atomic).
- Tests: `.venv/bin/python -m pytest tests/ -q`; UI tests under `xvfb-run -a`.
- `.github/` changes require an SSH push: the OAuth token has no `workflow`
  scope.

## Review Focus

- Cancelling during a retry wait: the worker must stop immediately and emit
  CANCELLED, not sleep out the delay and retry.
- A queue file corrupted by a half-written save: startup must ignore it, keep
  the file for inspection and log, never crash or lose the rest of the app.
- Restoring a queue whose output folder was deleted: entries must still load
  and fail at download time, not at startup.
- Quitting from the tray while downloads run: same shutdown path as
  `File > Exit`, so `stop_downloads()` runs and the config is saved.
- Diagnostics on a machine without ffmpeg or without a log file: the report
  says "not found" and still exports.

---

### Task 1: Worker-level retry with backoff

**Files:**
- Modify: `src/youmudow/services/download_worker.py:25-43` (`__init__`), `:94-159` (`run`)
- Modify: `src/youmudow/services/download_service.py:52-72` (`__init__`), worker creation in `_process_queue`
- Modify: `src/youmudow/app/config.py:20-46` (default `max_retries: 2`)
- Modify: `src/youmudow/app/controller.py:55-58` (pass the config value)
- Test: `tests/unit/test_download_service.py`, `tests/unit/test_worker_retry.py` (create)

**Interfaces:**
- Produces:
  - `DownloadWorker(worker_id, adapter, output_path_getter, progress_callback, max_retries: int = 0, retry_delay: float = 2.0)`.
  - `DownloadService(..., max_retries: int = 0)` and
    `DownloadService.set_max_retries(value: int) -> None` (clamped `0..5`).
- Consumes: `YtdlpAdapter.download` raising on failure, `DownloadStatus`.

- [ ] **Step 1: Write the failing tests**

```python
class FlakyAdapter:
    def __init__(self, failures: int):
        self.calls = 0
        self._failures = failures

    def download(self, video, output_path, progress_callback=None, cancel_event=None):
        self.calls += 1
        if self.calls <= self._failures:
            raise RuntimeError("transient")
        video.status = DownloadStatus.DONE
        return video


def _run_one(adapter, max_retries):
    events = []
    worker = DownloadWorker(1, adapter, lambda: Path("/tmp"), events.append, max_retries=max_retries, retry_delay=0.01)
    worker.start()
    worker.submit(Video(title="T", url="u"))
    _wait_until(lambda: any(e.type in (DownloadEventType.COMPLETED, DownloadEventType.ERROR) for e in events))
    worker.stop()
    return adapter.calls, events[-1].type


def test_worker_retries_then_succeeds():
    calls, last = _run_one(FlakyAdapter(failures=2), max_retries=2)
    assert calls == 3
    assert last is DownloadEventType.COMPLETED


def test_worker_gives_up_after_max_retries():
    calls, last = _run_one(FlakyAdapter(failures=9), max_retries=1)
    assert calls == 2
    assert last is DownloadEventType.ERROR


def test_worker_without_retries_attempts_once():
    calls, last = _run_one(FlakyAdapter(failures=1), max_retries=0)
    assert calls == 1
    assert last is DownloadEventType.ERROR
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_worker_retry.py -q`
Expected: FAIL — `DownloadWorker.__init__` got an unexpected keyword `max_retries`;
with retries disabled the `FlakyAdapter(failures=2)` case never completes.

- [ ] **Step 3: Implement the retry loop**

In `run`, replace the single `try/except` around `self._adapter.download(...)`
with a loop over `range(self._max_retries + 1)`. Before each attempt reset
`video.status = DownloadStatus.DOWNLOADING`, `video.error_message = ""`.
On exception: store the message; if `self._cancel_event.is_set()` or
`self._shutdown.is_set()` or it was the last attempt, keep ERROR and break;
otherwise log `[RETRY] attempt N for <url>`, emit
`DownloadEvent(type=DownloadEventType.PROGRESS, video=video)` so the UI shows
the row as active, and wait with `self._shutdown.wait(self._retry_delay * (attempt + 1))`
before the next attempt (the wait exits immediately on shutdown and the
cancel check after the wait exits on cancel). Do not touch the terminal-event
mapping below the loop.

- [ ] **Step 4: Wire the setting**

`DownloadService.__init__(..., max_retries: int = 0)` stores the value and
passes `max_retries=self._max_retries` to each `DownloadWorker(...)` it creates.
`AppController` passes `max_retries=int(self._config.get("max_retries", 2)) if self._config else 2`
when it builds its default `DownloadService`. `DEFAULT_CONFIG["max_retries"] = 2`.

- [ ] **Step 5: Add the cancel-during-wait test**

```python
def test_cancel_during_retry_wait_stops_the_worker():
    # failures=9, max_retries=3, retry_delay=5.0; cancel 50 ms after start
    # assert the terminal event is CANCELLED and calls == 1 within 1 s
```

Run: `.venv/bin/python -m pytest tests/unit/test_worker_retry.py tests/unit/test_download_service.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: retry failed downloads with backoff"
```

---

### Task 2: Persist and restore the pending queue

**Files:**
- Create: `src/youmudow/services/queue_store.py`
- Modify: `src/youmudow/paths.py` (new `queue_file()`)
- Modify: `src/youmudow/services/download_service.py` (persist hooks + `restore_queue`)
- Modify: `src/youmudow/app/controller.py` (`restore_queue`)
- Modify: `src/youmudow/main.py:18-31`
- Test: `tests/unit/test_queue_store.py` (create), `tests/unit/test_download_service.py`

**Interfaces:**
- Produces:
  - `paths.queue_file() -> Path` (`config_dir() / "queue.json"`).
  - `queue_store.video_to_dict(video: Video) -> dict[str, Any]`,
    `queue_store.video_from_dict(data: dict[str, Any]) -> Video | None`,
    `queue_store.save_queue(path: Path, videos: Sequence[Video]) -> None`,
    `queue_store.load_queue(path: Path) -> list[Video]`.
  - `DownloadService(..., queue_file: Path | None = None)`,
    `DownloadService.restore_queue() -> int`.
  - `AppController.restore_queue() -> int`.
- Consumes: `persistence.write_atomic`, `DownloadQueue.peek`, `Video.options`.

- [ ] **Step 1: Write the failing store tests**

```python
def test_queue_round_trip(tmp_path):
    video = Video(
        title="T", url="https://x.test/1", uploader="U", duration=42,
        thumbnail="https://x.test/t.jpg",
        options=DownloadOptions(file_format="flac", quality="best", subtitles=True, subtitle_lang="es"),
    )
    path = tmp_path / "queue.json"
    save_queue(path, [video])
    restored = load_queue(path)
    assert len(restored) == 1
    assert restored[0].title == "T"
    assert restored[0].options.file_format == "flac"
    assert restored[0].options.subtitle_lang == "es"
    assert restored[0].status is DownloadStatus.READY


def test_corrupt_queue_is_ignored_and_kept(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_queue(path) == []
    assert path.exists()  # kept for inspection


def test_restore_does_not_touch_the_filesystem(tmp_path):
    path = tmp_path / "queue.json"
    save_queue(path, [Video(title="T", url="https://x.test/1")])
    service = DownloadService(adapter=FakeAdapter(), queue_file=path,
                              default_output_path=tmp_path / "deleted-folder")
    assert service.restore_queue() == 1
    assert service.queue_size == 1


def test_entries_without_url_are_dropped(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text('[{"title": "no url"}, {"url": "https://x.test/1", "title": "ok"}]', encoding="utf-8")
    assert [v.title for v in load_queue(path)] == ["ok"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_queue_store.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `queue_store`**

`video_to_dict` writes `title, url, uploader, duration, thumbnail` and
`options` via `dataclasses.asdict(video.options)`. `video_from_dict` requires a
non-empty `url`, rebuilds `DownloadOptions(**data.get("options", {}))` inside
`try/except TypeError`, and forces `status=DownloadStatus.READY`.
`save_queue` writes `json.dumps([...])` with `write_atomic`; `load_queue` returns
`[]` on `OSError`/`ValueError`/`TypeError` and logs a warning, keeping the file.

- [ ] **Step 4: Write the failing service test**

```python
def test_service_persists_and_restores_the_pending_queue(tmp_path):
    path = tmp_path / "queue.json"
    service = DownloadService(adapter=FakeAdapter(), queue_file=path)
    service.add_to_queue(Video(title="A", url="https://x.test/a"))
    service.add_to_queue(Video(title="B", url="https://x.test/b"))
    assert json.loads(path.read_text())[0]["url"] == "https://x.test/a"

    restarted = DownloadService(adapter=FakeAdapter(), queue_file=path)
    assert restarted.restore_queue() == 2
    assert restarted.queue_size == 2
```

- [ ] **Step 5: Implement persistence calls**

`DownloadService._persist_queue()` calls `save_queue(self._queue_file, self._queue.peek())`
when `_queue_file` is set, wrapped in `try/except OSError` with a debug log.
Call it at the end of `add_to_queue`, `add_multiple`, `clear_queue`,
`cancel_video` when it removes an entry, and inside `_process_queue` after a
video leaves the queue. `restore_queue()` returns 0 when there is no file,
otherwise adds every restored video via `self._queue.add(...)` and calls
`_persist_queue()` once.

- [ ] **Step 6: Wire startup**

`AppController.restore_queue()` delegates to the download service.
In `main.py`, after `controller.set_output_path(...)`, do
`restored = controller.restore_queue()` and log it; pass
`restored_count=restored` to `MainWindow` so the window can show
`Restored N download(s)` in the status bar once, on startup.

- [ ] **Step 7: Run and commit**

Run: `.venv/bin/python -m pytest tests/unit -q`
Commit `feat: persist the download queue and restore it on startup`.

---

### Task 3: Tray icon that keeps the app running

**Files:**
- Create: `src/youmudow/ui/tray.py`
- Modify: `pyproject.toml` (dependency `pystray>=0.19`)
- Modify: `YouMuDow.spec` (`hiddenimports` += `pystray`, `pystray._xorg`, `pystray._win32`, `pystray._darwin`)
- Modify: `src/youmudow/app/config.py` (`minimize_to_tray: False`)
- Modify: `src/youmudow/ui/menubar.py` (View menu checkbutton + callback)
- Modify: `src/youmudow/ui/window.py` (`_on_close`, tray lifecycle)
- Test: `tests/unit/test_tray.py` (create), `tests/integration/test_shutdown.py`

**Interfaces:**
- Produces:
  - `tray.TrayIcon(on_show: Callable[[], None], on_quit: Callable[[], None], on_start_queue: Callable[[], None], image_factory: Callable[[], Any])`.
  - `TrayIcon.start() -> bool` (False when `pystray` is unavailable),
    `TrayIcon.stop() -> None`, `TrayIcon.available -> bool`.
  - `MenuCallbacks.toggle_tray: Callable[[], None]` and a
    `minimize_to_tray` `tk.BooleanVar` checkbutton in the View menu.
- Consumes: `youmudow.ui.icon.get_icon_image`.

- [ ] **Step 1: Write the failing tests**

```python
def test_tray_degrades_without_pystray(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", None)
    tray = TrayIcon(lambda: None, lambda: None, lambda: None, lambda: None)
    assert tray.start() is False


def test_tray_builds_menu_items(monkeypatch):
    fake = _install_fake_pystray(monkeypatch)  # module with Icon/Menu/MenuItem recording calls
    tray = TrayIcon(show, quit_, start_q, lambda: None)
    assert tray.start() is True
    labels = [item.text for item in fake.icon.menu.items]
    assert labels == ["Show", "Start downloads", "Quit"]


def test_window_close_with_tray_enabled_keeps_running(stack):
    stack.config.set("minimize_to_tray", True)
    stack.window._on_close()
    assert stack.window._root.state() == "withdrawn"
    assert stack.downloads.is_running is True  # nothing stopped


def test_quit_from_tray_uses_the_real_shutdown_path(stack):
    stack.controller.enqueue(Video(title="T", url="https://x.test/1"))
    stack.controller.start_downloads()
    stack.window._quit_from_tray()
    pump(stack.window, lambda: stack.downloads.is_running is False)
    assert stack.downloads.is_running is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/unit/test_tray.py tests/integration/test_shutdown.py -q -k tray`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `ui/tray.py`**

Import `pystray` lazily inside `start()`; on `ImportError` log a debug line and
return False. Build `pystray.Menu(pystray.MenuItem("Show", on_show, default=True), pystray.MenuItem("Start downloads", on_start_queue), pystray.MenuItem("Quit", on_quit))`
and run the icon in a daemon thread. `stop()` calls `icon.stop()` inside
`try/except Exception` and clears the reference. Keep the module free of Tk
imports so it is unit-testable.

- [ ] **Step 4: Wire the window**

- Create `self._tray: TrayIcon | None = None` in `__init__`.
- `_on_close`: save settings as today; if `self._config` and
  `self._config.get("minimize_to_tray", False)` and the tray can start,
  `withdraw()` and return **without** stopping downloads. Otherwise run the
  current shutdown path.
- Add `_quit_from_tray()` = `self._schedule(self._on_close_real)` where
  `_on_close_real` is today's body (stop downloads + destroy), and
  `_show_from_tray()` = `self._schedule(self._tk_root.deiconify)`.
- `destroy()` stops the tray.
- Menu: build the `minimize_to_tray` BooleanVar from config in
  `_build_menubar`, add a checkbutton to View; the callback writes the value
  with `config.set(...)` + `config.save()`.

- [ ] **Step 5: Run and commit**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/ -q` and
`PYTHONPATH=src .venv/bin/python scripts/smoke_boot.py`
Commit `feat: add an opt-in system tray icon`.

---

### Task 4: Exportable diagnostics report

**Files:**
- Create: `src/youmudow/services/diagnostics_service.py`
- Modify: `src/youmudow/ui/menubar.py` (`MenuCallbacks.export_diagnostics`, Help item)
- Modify: `src/youmudow/ui/window.py` (`_on_export_diagnostics`, status message)
- Test: `tests/unit/test_diagnostics_service.py` (create), `tests/unit/test_widgets.py`/menubar test if one exists

**Interfaces:**
- Produces:
  - `diagnostics_service.SENSITIVE_KEYS: frozenset[str]` =
    `{"cookies_file", "cookies_profile", "cookies_from_browser", "search_history", "output_path"}`.
  - `redact_config(config: Mapping[str, Any]) -> dict[str, Any]` (value
    replaced by `"<redacted>"`).
  - `build_report(log_tail: str = "", config: Mapping[str, Any] | None = None) -> str`.
  - `export_diagnostics(destination: Path) -> Path`.
- Consumes: `youmudow.__version__`, `services.updater_service.get_ytdlp_version`,
  `services.environment_service.youtube_environment_status`,
  `logging_config.LOG_FILE_NAME`, `CONFIG_DIR`, `AppConfig`.

- [ ] **Step 1: Write the failing tests**

```python
def test_report_has_the_expected_sections(monkeypatch):
    monkeypatch.setattr("youmudow.services.diagnostics_service.get_ytdlp_version", lambda: "2026.01.01")
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_diagnostics_service.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Report layout: `YouMuDow diagnostics` title, `Generated: <iso8601>`, app
version, `platform.platform()`, `sys.version`, yt-dlp version,
`_ffmpeg_version()` (first line of `ffmpeg -version`, `"not found"` on any
`OSError`/`FileNotFoundError`/`TimeoutExpired`), a `youtube_environment_status()`
dump, the redacted config as indented JSON, and a `Log tail` section.
`export_diagnostics` creates the parent directory and writes UTF-8.

- [ ] **Step 4: Wire the menu**

`MenuCallbacks.export_diagnostics`; a Help item
`Export Diagnostics...` that opens
`filedialog.asksaveasfilename(defaultextension=".txt", initialfile="youmudow-diagnostics.txt")`,
calls `export_diagnostics`, and sets the status bar to
`Diagnostics saved to <path>`. Cancel (`""` path) returns silently.

- [ ] **Step 5: Run and commit**

Run: `.venv/bin/python -m pytest tests/unit -q`
Commit `feat: export a combined diagnostics report`.

---

### Task 5: Documentation, changelog and version 1.6.0

**Files:**
- Modify: `README.md` (features list, troubleshooting: tray on Linux, retries,
  queue restore, diagnostics)
- Modify: `CHANGELOG.md` (new `## [1.6.0] - 2026-11-17` section)
- Modify: `pyproject.toml` (`version = "1.6.0"`)
- Modify: `docs/backlog.md` if any TODO from this work is left

**Interfaces:**
- Consumes: everything above. Produces: a releasable tree.

- [ ] **Step 1: Update docs**

README: add bullets for channels, presets, size preview, retries, queue
restore, tray (with the "needs a status-notifier host on Linux" caveat) and
`Help > Export Diagnostics...`. No screenshots required.

- [ ] **Step 2: Changelog and version**

CHANGELOG under `## [1.6.0] - 2026-11-17` with `### Added` for each feature and
`### Changed` for the playlist limit default. Bump `pyproject.toml` and run
`.venv/bin/pip install -e . --no-deps` so the smoke test reports 1.6.0.

- [ ] **Step 3: Final gates**

```bash
ruff format src/ tests/ && ruff check src/ tests/ && .venv/bin/python -m mypy
.venv/bin/python -m pytest tests/ -q
PYTHONPATH=src .venv/bin/python scripts/smoke_boot.py   # BOOT OK (... v1.6.0 ...)
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: release v1.6.0"
```

---

## Self-review notes

- Spec coverage: retry/resume row (Tasks 1–2), tray row (Task 3), diagnostics
  row (Task 4), release hygiene (Task 5). Notifications already exist and are
  not rebuilt.
- Retry state lives only in the worker, so `DownloadService` keeps its event
  contract untouched: the UI still receives exactly one terminal event per
  video.
- Queue persistence is additive: with `queue_file=None` (tests, CLI) the
  service behaves exactly as before.
