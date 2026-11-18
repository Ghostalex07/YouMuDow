# Full-stack UI Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a `tests/integration/` suite that drives the real `AppController`, real services and the real `MainWindow` against fake yt-dlp adapters, so search, playlist, download and shutdown wiring is covered end to end.

**Architecture:** fake adapters implement the same protocol as `YtdlpAdapter`/`DownloadService`'s adapter, so `SearchService` and `DownloadService` run unmodified. Each test builds one Tk root through `MainWindow`, pumps the event loop with a small helper, and asserts on the widgets the user actually sees.

**Tech Stack:** pytest 9, stdlib `tkinter`, `unittest.mock`, `xvfb-run` in CI.

**Spec:** `docs/superpowers/specs/2026-11-17-next-features.md`

## Global Constraints

- Python 3.10+; ruff line length 100.
- No new runtime or dev dependency.
- UI tests must skip cleanly when no display is available (local machines
  without X), and must run in CI where `xvfb-run -a` is already used.
- Every test that builds a window must destroy it in a `finally`/fixture; the
  autouse fixtures in `tests/conftest.py` (`_no_leaked_thumbnail_workers`,
  `_collect_tk_garbage_on_main_thread`) stay untouched.
- Layers: tests may import `app`, `services`, `domain` and `ui`.

## Review Focus

- A download that finishes while the window is closing: the terminal callback
  must not touch destroyed widgets (this is exactly how the old SIGABRT
  happened).
- Empty search results and a failing search: the UI must leave "Searching…"
  and show the empty state, not hang.
- Playlist fetch failing (network error, private list): status must say so and
  `_is_searching` must go back to False.
- A video whose adapters raise inside `download()`: the queue must drop the
  active entry and the UI must show ERROR, never a phantom "downloading" row.
- Tk roots created by a test that fails mid-way: the next test must still get a
  clean root (leaked-root detection is part of the harness).

---

### Task 1: Harness, display gate and a testable startup

**Files:**
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_harness.py`
- Modify: `src/youmudow/ui/window.py:63-125` (`__init__`)
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]`, add `markers`)
- Modify: `Makefile` (new `test-ui` target)

**Interfaces:**
- Consumes: `MainWindow(controller, debug_mode=True, config=None)`, `AppController(...)`, `SearchService(adapter=...)`, `DownloadService(adapter=..., default_output_path=...)`.
- Produces:
  - `MainWindow(..., run_startup_checks: bool = True)` — when False, the two
    `after()` startup checks (clipboard, yt-dlp) are not scheduled.
  - `tests.integration.conftest.FakeSearchAdapter` with
    `search(query, limit=10) -> list[Video]`,
    `get_metadata(url) -> Video | None`,
    `get_playlist_videos(url, limit=50) -> list[Video]`,
    `set_log_callback(cb) -> None`.
  - `FakeDownloadAdapter` with
    `download(video, output_path, progress_callback=None, cancel_event=None) -> Video`,
    `set_log_callback(cb) -> None`, plus `downloaded: list[Video]`,
    `fail_urls: set[str]`, `progress_steps: list[float]`.
  - Fixture `stack` returning
    `SimpleNamespace(window=..., controller=..., search=<SearchService>, adapter=<FakeSearchAdapter>, downloads=<DownloadService>, config=<AppConfig>)`.
    The fake search adapter is exposed directly as `stack.adapter` because
    `SearchService` keeps it in `_adapter`.
  - Helper `pump(window, predicate, timeout=3.0)` that calls
    `window._root.update()` + `time.sleep(0.01)` until `predicate()` is true,
    and raises `AssertionError` on timeout.

- [ ] **Step 1: Write the failing harness test**

```python
# tests/integration/test_harness.py
from youmudow.ui.window import MainWindow


def test_window_builds_against_real_controller(stack):
    assert "YouMuDow" in stack.window._root.title()
    assert stack.window._search_bar is not None
    assert stack.window._results_cards is not None
    assert stack.window._detail_panel is not None


def test_startup_checks_can_be_skipped(stack):
    # run_startup_checks=False must leave no pending startup timers
    pending = stack.window._root.tk.call("after", "info")
    assert pending == () or pending == ""
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_harness.py -q`
Expected: FAIL — `tests/integration` does not exist / `fixture 'stack' not found`.

- [ ] **Step 3: Add the `run_startup_checks` keyword to `MainWindow`**

In `src/youmudow/ui/window.py`, change the signature to
`def __init__(self, controller: "AppController", debug_mode: bool = True, config: Any = None, run_startup_checks: bool = True) -> None`
and wrap the two `self._tk_root.after(500, self._check_clipboard_on_start)` /
`after(3000, self._check_ytdlp_on_start)` calls in
`if run_startup_checks:`. No other behavior changes.

- [ ] **Step 4: Write `tests/integration/conftest.py`**

Contents, in this order:
1. `pytest.importorskip("tkinter")`.
2. `collect_ignore_glob` set to `["*.py"]` when `platform.system() == "Linux" and not os.environ.get("DISPLAY")` (a `pytest.skip` at conftest import time is an error; `collect_ignore_glob` is the supported way).
3. `FakeSearchAdapter` storing `results`, `playlist`, `metadata`, and recording `queries`.
4. `FakeDownloadAdapter`: for each url in `fail_urls` set
   `video.status = DownloadStatus.ERROR`, `video.error_message = "boom"` and
   return the video; otherwise emit `progress_callback(50.0, "1.0MiB/s")`,
   set `video.status = DownloadStatus.DONE`,
   `video.path = output_path / f"{video.title}.{video.options.file_format}"`,
   touch that file, return the video. Record every video in `downloaded`.
5. Fixture `stack(tmp_path, monkeypatch)`:
   - `monkeypatch.setattr("youmudow.app.config.CONFIG_DIR", tmp_path / "cfg")` and `CONFIG_FILE` accordingly, then build a real `AppConfig()`.
   - `search = SearchService(adapter=FakeSearchAdapter(...))`,
     `downloads = DownloadService(adapter=FakeDownloadAdapter(), default_output_path=tmp_path)`.
   - `controller = AppController(search_service=search, download_service=downloads, config=config)`.
   - `window = MainWindow(controller=controller, config=config, run_startup_checks=False)`.
   - `try: yield SimpleNamespace(...)` / `finally: window.destroy(); downloads.stop()`.
6. `pump()` helper as described in Interfaces.

- [ ] **Step 5: Run the harness tests**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/integration/test_harness.py -q`
Expected: 2 passed.

- [ ] **Step 6: Register the marker and the Makefile target**

`pyproject.toml`: `markers = ["integration: full-stack UI tests, need a display (xvfb-run -a)"]`.
`Makefile`: `test-ui:` runs `xvfb-run -a .venv/bin/python -m pytest tests/integration -q` (plain pytest when `DISPLAY` is set).

- [ ] **Step 7: Full gates and commit**

```bash
ruff format src/ tests/ && ruff check src/ tests/ && .venv/bin/python -m mypy
.venv/bin/python -m pytest tests/ -q
PYTHONPATH=src .venv/bin/python scripts/smoke_boot.py
git add -A && git commit -m "test: add a full-stack UI harness with fake adapters"
```

---

### Task 2: Search flow end to end

**Files:**
- Create: `tests/integration/test_search_flow.py`
- Modify: none (production code is only used)

**Interfaces:**
- Consumes: `stack`, `pump`, `FakeSearchAdapter.results`.
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

```python
from youmudow.domain.models import Video


def test_query_renders_one_card_per_result(stack):
    stack.adapter.results = [
        Video(title="Lofi One", url="https://example.com/1", uploader="A", duration=61),
        Video(title="Lofi Two", url="https://example.com/2", uploader="B", duration=122),
    ]
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count == 2)
    assert stack.window._results_cards.card_count == 2
    assert stack.window._is_searching is False


def test_selecting_a_card_fills_the_detail_panel(stack):
    video = Video(title="Lofi One", url="https://example.com/1", uploader="A")
    stack.adapter.results = [video]
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count == 1)
    stack.window._results_cards.select(0)
    stack.window._root.update()
    assert stack.window._selected_video is video
    assert stack.window._detail_panel._detail_title.cget("text") == "Lofi One"


def test_empty_query_never_reaches_the_service(stack):
    stack.window._search_bar.search_var.set("   ")
    stack.window._on_search()
    assert stack.adapter.queries == []


def test_failing_search_leaves_the_busy_state(stack, monkeypatch):
    def explode(query, limit=10):
        raise RuntimeError("network down")

    monkeypatch.setattr(stack.adapter, "search", explode)
    stack.window._search_bar.search_var.set("lofi")
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._is_searching is False)
    assert stack.window._results_cards.card_count == 0
```

Note: if `AppController._perform_search` already swallows exceptions and calls
the callback with `[]`, the last test passes as written; if it propagates into
a background thread, change the assertion to `pump(..., timeout=1.0)` plus
`assert stack.window._results_cards.card_count == 0` and a `caplog` check that
the failure was logged. Do not change production behaviour to satisfy the test.

- [ ] **Step 2: Run to verify they fail**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/integration/test_search_flow.py -q`
Expected: FAIL (fixture/module missing) until Task 1 lands; then any real
wiring bug shows up here.

- [ ] **Step 3: Fix only real wiring bugs the tests reveal**

Examples that are in scope: `_is_searching` never cleared on an empty result,
the callback scheduled on a dead root, cards not cleared between searches. Any
fix gets its own assertion first. No refactors.

- [ ] **Step 4: Run and commit**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/integration -q`
Expected: all pass. Commit `test: cover the search flow end to end`.

---

### Task 3: Playlist and channel flow

**Files:**
- Create: `tests/integration/test_playlist_flow.py`
- Modify: `src/youmudow/domain/validators.py` only if Task 1 of the library plan already landed; otherwise leave classification to that plan and use a playlist URL here.

**Interfaces:**
- Consumes: `FakeSearchAdapter.playlist`, `ResultsCards.is_playlist`, `ResultsCards.playlist_videos`, `DetailPanel._add_all_to_queue`, `AppController.enqueue_multiple`.
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

```python
from youmudow.domain.models import Video

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL123"


def test_playlist_url_marks_the_results_as_a_playlist(stack):
    stack.adapter.playlist = [
        Video(title="P1", url="https://example.com/p1"),
        Video(title="P2", url="https://example.com/p2"),
    ]
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._results_cards.card_count == 2)
    assert stack.window._results_cards.is_playlist is True


def test_add_all_enqueues_every_playlist_entry(stack):
    videos = [Video(title=f"P{i}", url=f"https://example.com/p{i}") for i in range(3)]
    stack.adapter.playlist = videos
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: len(stack.window._results_cards.playlist_videos) == 3)
    stack.window._detail_panel._add_all_to_queue()
    assert stack.downloads.queue_size == 3


def test_playlist_fetch_failure_recovers_the_ui(stack, monkeypatch):
    def explode(url, limit=50):
        raise RuntimeError("private playlist")

    monkeypatch.setattr(stack.adapter, "get_playlist_videos", explode)
    stack.window._search_bar.search_var.set(PLAYLIST_URL)
    stack.window._on_search()
    pump(stack.window, lambda: stack.window._is_searching is False, timeout=2.0)
    assert stack.window._results_cards.card_count == 0
```

- [ ] **Step 2: Run to verify the current behaviour**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/integration/test_playlist_flow.py -q`
Expected: first two pass if the existing wiring is sound; the third fails
today because `_handle_playlist_input`'s thread swallows `RuntimeError` as
"window closed" and never clears `_is_searching`.

- [ ] **Step 3: Fix the failure-recovery bug**

In `MainWindow._handle_playlist_input`, catch `Exception` (not only
`RuntimeError`/`TclError`), log it, and schedule a new
`_on_playlist_failed(message: str)` on the main loop that sets
`_is_searching = False`, clears the cards, calls `_set_status(f"Could not load playlist: {message}")`
and `_update_button_states()`.

- [ ] **Step 4: Add the matching test assertion**

Extend the third test with
`assert "Could not load playlist" in stack.window._status_bar._label.cget("text")`
(use whatever attribute the status bar exposes; if it exposes only a
`set_status` method, spy on it instead).

- [ ] **Step 5: Run and commit**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/integration -q`
Expected: all pass. Commit `test: cover playlist flows and failure recovery`.

---

### Task 4: Download lifecycle end to end

**Files:**
- Create: `tests/integration/test_download_flow.py`
- Modify: none unless a bug appears.

**Interfaces:**
- Consumes: `fake downloads.downloaded`, `progress_steps`, `fail_urls`, `DownloadService.queue_size`, `MainWindow._is_downloading`, `StatusBar`.
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

```python
from youmudow.domain.models import Video


def test_queue_drains_and_updates_the_ui(stack):
    video = Video(title="Song", url="https://example.com/song")
    stack.controller.enqueue(video)
    stack.controller.start_downloads()
    pump(stack.window, lambda: len(stack.downloads.adapter.downloaded) == 1)
    pump(stack.window, lambda: stack.window._is_downloading is False, timeout=3.0)
    assert stack.downloads.queue_size == 0
    assert stack.downloads.adapter.progress_steps == [50.0]


def test_failing_download_reports_error_without_hanging(stack):
    stack.downloads.adapter.fail_urls.add("https://example.com/bad")
    stack.controller.enqueue(Video(title="Bad", url="https://example.com/bad"))
    stack.controller.start_downloads()
    pump(stack.window, lambda: stack.downloads.adapter.downloaded, timeout=3.0)
    pump(stack.window, lambda: stack.window._is_downloading is False, timeout=3.0)
    assert stack.window._results_cards.card_count == 0


def test_completion_notification_is_sent(stack, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "youmudow.services.notification_service.notify",
        lambda title, message: calls.append((title, message)),
    )
    stack.controller.enqueue(Video(title="Song", url="https://example.com/song"))
    stack.controller.start_downloads()
    pump(stack.window, lambda: calls, timeout=3.0)
    assert calls and calls[0][0] == "YouMuDow"
```

- [ ] **Step 2: Run and observe**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/integration/test_download_flow.py -q`
Expected: failures only where the real wiring is broken (for example
`_is_downloading` never cleared, or the notification path imported lazily so
the monkeypatch target must be `youmudow.services.notification_service.notify`).

- [ ] **Step 3: Fix real bugs, one assertion at a time**

Keep fixes minimal: clear the busy flag from the state snapshot, not from the
completion callback (that is the existing contract, see
`test_on_download_complete_keeps_downloading_until_snapshot_says_otherwise`).

- [ ] **Step 4: Run and commit**

Commit `test: cover the download lifecycle end to end`.

---

### Task 5: Shutdown safety

**Files:**
- Create: `tests/integration/test_shutdown.py`
- Modify: `src/youmudow/ui/window.py` only if a race is found.

**Interfaces:**
- Consumes: `MainWindow._on_close`, `MainWindow.destroy`, `DownloadService.stop`.
- Produces: nothing new.

- [ ] **Step 1: Write the failing tests**

```python
from youmudow.domain.models import Video


def test_close_stops_downloads_and_destroys_the_root(stack):
    stack.controller.enqueue(Video(title="Song", url="https://example.com/song"))
    stack.controller.start_downloads()
    stack.window._on_close()
    assert stack.downloads.is_running is False


def test_terminal_callback_after_destroy_is_harmless(stack, caplog):
    callback = stack.controller.on_download_complete.call_args.args[0]
    video = Video(title="Late", url="https://example.com/late")
    stack.window.destroy()
    with caplog.at_level(logging.DEBUG):
        callback(video)  # a worker finishing after the window is gone
    assert "Late" not in caplog.text  # nothing rendered, nothing raised
```

Use `caplog.at_level(logging.DEBUG)` if the implementation logs a debug line
when it drops a scheduled callback; assert on that line instead of an absence.

- [ ] **Step 2: Run and observe**

Run: `xvfb-run -a .venv/bin/python -m pytest tests/integration/test_shutdown.py -q`
Expected: PASS if `_schedule` already guards `TclError`; otherwise FAIL with
`TclError: can't invoke "after" command: application has been destroyed`,
which is the real-world crash this task exists to prevent.

- [ ] **Step 3: Fix the guard and rerun**

If it fails, extend `MainWindow._schedule` to also catch
`RuntimeError` and `AttributeError` when `_tk_root` is gone, and log at debug.
Run the whole suite twice in a row to prove there are no leaks:
`xvfb-run -a .venv/bin/python -m pytest tests/ -q` (twice).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test: pin shutdown safety with full-stack tests"
```

---

## Self-review notes

- Spec coverage: the "UI integration tests" row of the spec is covered by
  Tasks 1–5; nothing else in the spec is touched here.
- Playlist failure recovery (Task 3) is a production bug fix, not a test-only
  change; it is the one place this plan edits behaviour.
- Type consistency: `FakeDownloadAdapter.download` mirrors
  `YtdlpAdapter.download(video, output_path, progress_callback, cancel_event)`
  exactly, so `DownloadWorker` can use it unchanged.
