# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2026-09-10

### Added

- **CLI**: `youmudow-cli` with `download` (--format, --quality, --output,
  --skip-metadata) and `search` (--limit) subcommands, reusing the same
  services as the GUI
- `DownloadQueue.has_url()` short-circuits the duplicate check without copying
  the whole queue on every `add` call
- `StateManager.get_snapshot()` uses shallow copies instead of `copy.deepcopy`
  (~5.6x faster on queue-sized snapshots)
- `DownloadService` wakes its queue dispatcher immediately when a worker
  finishes, on `clear_queue()` and on `stop()`, instead of relying solely on
  poll timeouts
- Log terminal buffer is now bounded (`max(5 * max_lines, 1000)`); long
  sessions cannot grow it unbounded
- Packaged app icon (`ui/icon.py`) — previously in an unpackaged `assets/`
  directory and never loaded
- Makefile: `make install/run/test/coverage/lint/format/typecheck/check`
- Pre-commit hooks (ruff lint + format, trailing whitespace, YAML checks)
- Architecture documentation (`docs/architecture.md`)
- Screenshots in `docs/screenshots/`

### Changed

- `DownloadService.start()`/`stop()` serialized by a dedicated `_lifecycle_lock`
  — a `start()` racing a `stop()` either wins completely or loses completely,
  so worker threads are never orphaned
- Download activation is now event-driven: a video moves to active only when
  the service reports it started, keeping `StateManager` consistent with the
  service queue
- `DownloadService.stop()` is thread-safe, idempotent and reports workers that
  refuse to stop; downloads restart cleanly after stop
- Duplicate queue entries (same URL already queued/active) are silently
  ignored; finished downloads can still be re-queued for retry
- Cancelling a queued video now closes its lifecycle: removed, marked
  `CANCELLED`, emits one idempotent `CANCELLED` event
- `StateManager.add_to_queue` mirrors the service's duplicate-URL guard
- Centralized format/quality sets (`SUPPORTED_FORMATS`, `SUPPORTED_QUALITIES`)
  in `domain/validators.py`, reused by the CLI, the GUI detail panel and the
  adapter
- `DownloadService` worker events are gated on `run_event` — lingering workers
  cannot paint progress after `stop()`
- Terminal events matched by object identity, so a stale same-URL event from a
  previous run cannot corrupt a new download
- `--no-check-certificate` is no longer hardcoded; `YtdlpConfig.verify_certificates`
  defaults to `True` and is configurable
- PyInstaller bundle: hidden imports trimmed, Pillow reduced to JPEG/PNG/GIF/WebP
  plugins via `hook-PIL.Image.py`, `--strip` on non-Windows, lazy module
  exclusions. Linux onefile: ~44 MB → ~14.5 MB, startup ~0.32 s
- CI split into parallel `lint` / `typecheck` / `test` (Python 3.10–3.12) /
  `build` jobs
- Centralized logging with console + optional file handler
- EventBus trimmed to log events only (`LOG_OUTPUT`, `LOG_CLEAR`) with typed
  `LogEvent`
- History stores the real output file path (with extension)
- Playlist fetching applies the limit before enumerating the full playlist
- `AppConfig.get`/`get_search_history` typed; `get_str` helper added
- `AppController.reset()` preserves configured concurrency, output path and log
  callback across the fresh service instance
- yt-dlp success with no attributable output file now reports `ERROR` instead of
  a bare `DONE`

### Fixed

- `DownloadService.download_now` no longer leaks adapter exceptions as phantom
  active downloads — failures map to `ERROR` and emit an `ERROR` event
- Deadlock when a download event callback called `stop()`/`add_to_queue`
  (STARTED was broadcast while holding the service lock)
- Late worker events after `stop()` are now dropped once the service is stopped
- A terminal `COMPLETED` was emitted even when a download did not end in `DONE`
  — unknown/partial statuses now map to `ERROR`
- Terminal events for videos no longer active (duplicates or leftovers from a
  previous run after restart) are dropped instead of corrupting the state
- Output resolution could mistake a pre-existing file for the new download;
  only files created during the run are considered
- Reader thread could stay alive if the subprocess died without closing stdout
- Huge playlists were fully enumerated even with a small limit
- CLI accepted invalid formats/qualities and unauthenticated-scheme URLs;
  now validates and returns 130 on Ctrl+C
- `max_retries=0` produced zero attempts (now treated as one attempt)
- App icon never displayed because `assets/` was outside the package
- Cancellation could leave a download stuck in ERROR instead of CANCELLED

### Removed

- Dead `InvalidUrlError` and `ConfigurationError` exceptions (never raised or
  caught; hierarchy is now `YouMuDowError` → `DownloadError` → `YtDlpError` →
  `YtDlpNotFoundError`)
- Unused `LogTerminal.append_separator()`/`set_auto_scroll()` methods
- `scripts/run_dev.py` (not referenced by Makefile, CI or docs; `make run`
  provides the same command and works in a fresh clone)
- Redundant `tests/unit/.gitkeep` and unused `error_video` pytest fixture

## [1.1.0] - 2026-05-21

### Added
- **Multi-site support**: Now accepts any URL (YouTube, SoundCloud, Vimeo, Twitter, 1000+ sites)
- **Light/Dark theme toggle**: Ctrl+T toggles between themes; preference saved to config
- **App icon**: Base64-encoded PNG icon with download arrow
- **GitHub Pages**: Project website at docs/index.html
- **Dependabot**: Weekly updates for pip and GitHub Actions
- **Bump version script**: scripts/bump_version.py for automated versioning
- **CI badge**: Dynamic badge in README

### Changed
- **Widget architecture restored**: search_bar.py, results_table.py, detail_panel.py, status_bar.py extracted from window.py (623 lines vs 1666)
- Updated placeholder text: "Search or paste URL (YouTube, SoundCloud, Vimeo...)"
- Updated About dialog with multi-site description
- Updated app description to "Music & Video Downloader"
- `check_browser_profile`/`get_fallback_browser` restored in ytdlp adapter

### Fixed
- `is_supported_url` replaces `is_valid_youtube_url` for clipboard detection on startup
- Search now validates URLs using multi-site validator

## [1.0.0] - 2026-05-20

### Added
- Real-time download progress (fixed: progress was shown only after completion)
- Queue panel visible in UI with status, title and progress columns
- Right-click context menu on queue items (Remove, Open in browser)
- Thumbnail preview in detail panel using Pillow
- Persistent configuration saved to ~/.config/youmudow/config.json
  (output folder, format, quality, cookies, window geometry)
- System notifications on download completion (Linux/macOS/Windows)
- "Open Folder" button to open output directory after download
- "Add All to Queue" button for playlist results
- Clipboard URL detection on app startup
- Rate limit validation before download
- Retry button for failed downloads
- yt-dlp auto-updater (Help > Update yt-dlp)
- yt-dlp version check on startup with warning if not found
- Export logs to .txt file (File > Export Logs)
- About dialog with app version and yt-dlp version
- App version shown in window title
- PyInstaller build scripts (scripts/build.py, scripts/package.py)
- GitHub Actions CI and release workflows

### Fixed
- download_now() was blocking the UI thread during downloads
- COMPLETED event never emitted when using queue mode
- Progress callbacks fired after download finished instead of in real-time
- cancel_video() was accessing private queue internals directly
- Busy-wait loop using threading.Event() instead of time.sleep()
- --add-metadata deprecated flag replaced with --embed-metadata
- Unreachable code in get_unique_filename()
- Type hint callable -> Callable in window.py
- Duplicate pathlib import in ytdlp_adapter.py
- Default output path used Desktop which doesn't exist on Linux
- StateManager callbacks fired while holding the RLock
- Exceptions in EventBus handlers were silently swallowed
- Unused imports removed across multiple modules
- Window geometry restoration could place window off-screen
- Browser saved in config might not be installed on restore

### Changed
- Default output path: ~/Music/YouMuDow (Linux/macOS), ~/Desktop/YouMuDow (Windows)
- DownloadQueue now has a proper remove() method
- Notifications fuera del lock en StateManager

## [0.2.1] - 2026-04-01

### Added
- **URL Search Improvements**:
  - Search by YouTube URL now works correctly
  - URL parameter handling fixed (extracts base URL when additional params present)
  - Cancel button for long-running URL searches
- **Keyboard Shortcuts**:
  - `Ctrl+Enter` - Search
  - `Ctrl+D` - Download selected video
  - `Ctrl+Q` - Add to queue
  - `Ctrl+L` - Focus search field
  - `Ctrl+N` - Clear search field
  - `Escape` - Cancel current operation
- **Auto-replace URL on Paste**:
  - When pasting a YouTube URL, previous content is cleared automatically

### Fixed
- Search by URL returning None due to extra parameters in URL
- Video not auto-selected after URL search (Download/Queue buttons now work)
- Terminal not showing all logs without Debug Mode enabled

## [0.2.0] - 2026-04-01

### Added
- **Cookie Authentication**:
  - Browser cookies support (Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Chromium)
  - Multi-profile detection and selection (`browser:profile` syntax)
  - Cookies file import (.txt Netscape format)
  - Automatic fallback browser detection
  - Retry without cookies on authentication failure
- **Download Options**:
  - Rate limiting (`--limit-rate`, e.g., 1M, 500K)
  - Chapter splitting (`--split-chapters`)
  - Multi-language subtitles support
- **UI Improvements**:
  - Show only installed browsers in dropdown
  - Profile dropdown auto-updates on browser change
  - Rate limit input with validation
- **Testing**:
  - 111 unit tests (previously 74)
  - New test suite for ytdlp_adapter
  - Browser and profile functionality tests

### Fixed
- Profile dropdown not populating when restoring saved video
- Thread safety in output handling
- Hardcoded browser list (now uses constant)
- Configurable max_retries and download_timeout
- Path logging security (now logs filename only)

## [0.1.0] - 2024-01-01

### Added
- Initial project structure
- Basic application skeleton
