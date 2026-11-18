# Next features — spec (2026-11-17)

**Goal:** close the real gaps left after v1.5.1 in the eight areas the maintainer
listed, without rebuilding what already ships.

## Inventory: what already exists

Verified against `09fca27` + the v1.5.1 tag.

| Requested | State today | Real gap |
|---|---|---|
| Playlists and channels | `is_playlist_url()` → `ResultsCards.is_playlist` → background `controller.search_playlist(url)` (limit 50) → "Add all" button. SoundCloud sets and Bandcamp albums accepted. | Channel URLs are only recognised with a `/videos` suffix. Limit is hardcoded. `youmudow-cli` cannot take a playlist. |
| UI integration tests | `tests/unit/test_window_smoke.py` builds a real `MainWindow` against a `Mock` controller, gated on `DISPLAY`; CI runs everything under `xvfb-run`. Panel/widget unit tests exist. | No test drives the real `AppController` + services + window together, so wiring bugs (search → cards → detail → queue) are invisible. |
| Preview and metadata | `get_metadata()` fills title, uploader, duration, thumbnail; shown in the detail panel. | No duration row, no estimated size, no format list before downloading. |
| Subtitles and chapters | Fully wired: toggles in the options panel, `--write-subs/--sub-langs/--embed-subs`, `--embed-chapters`, `--split-chapters`. | None. No work planned. |
| Download presets | None. Users pick format + quality + extras by hand. | Whole feature. |
| Retry and resume | yt-dlp's own retry flags inside `YtdlpAdapter.download`. No retry at worker level, no queue persistence across restarts. | Worker-level retry with backoff; persist and restore the pending queue. |
| Tray + notification | `notify()` is called on completion (Linux/macOS/Windows). Closing the window stops all downloads. | Tray icon that keeps the app running; opt-in. |
| Exportable diagnostics | `File > Export Logs...` copies the log file; `environment_service.youtube_environment_status()` reports the YouTube environment. | One combined report: versions, platform, ffmpeg, environment, redacted config, log tail. |

## Decisions

- **Dependencies:** only one new runtime dependency, `pystray>=0.19` (tray).
  Everything else is stdlib + Tk + Pillow + yt-dlp.
- **Single-threaded Tk:** every worker callback reaches the UI through
  `MainWindow._schedule()` (`root.after(0, ...)`), never directly.
- **Optional features degrade:** tray import failures, missing ffmpeg, missing
  log file and corrupted queue files must log and continue, never raise.
- **No re-planning of finished work:** playlists, subtitles, chapters and
  completion notifications stay as they are; the plans only extend them.
- **Channel support is URL recognition only:** yt-dlp already expands a
  channel into a flat playlist; we just have to classify the URL.

## Non-goals

- Code signing, installers (`.dmg`/`.msi`/AppImage), auto-update of the app.
- Per-video format override in the preview panel (preview is informational).
- Resume of partially downloaded bytes; only the pending queue is restored.
- A tray icon on Linux without a status-notifier host: it degrades to
  "feature unavailable" with a log line.

## Plans

1. `docs/superpowers/plans/2026-11-17-full-stack-ui-tests.md`
2. `docs/superpowers/plans/2026-11-17-library-and-preview.md`
3. `docs/superpowers/plans/2026-11-17-resilience-and-diagnostics.md`

## Global constraints (copied into every plan)

- Python 3.10+, `from __future__ import annotations` where the module already
  uses it; line length 100 (ruff).
- Layers only depend upwards: `domain` → `adapters` → `services` → `app` → `ui`.
- All subprocess work happens outside the Tk main thread.
- Tests: `.venv/bin/python -m pytest tests/ -q`; UI tests need a display and
  CI already provides one via `xvfb-run -a`.
- Gates: `ruff format src/ tests/`, `ruff check src/ tests/`, `mypy`,
  `pytest`, then `PYTHONPATH=src .venv/bin/python scripts/smoke_boot.py`.
- Any change under `.github/` must be pushed over SSH
  (`git@github.com:Ghostalex07/YouMuDow.git`): the OAuth token has no
  `workflow` scope.
