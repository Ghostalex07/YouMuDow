# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `DownloadQueue.has_url()` short-circuits the duplicate check in
  `DownloadService._is_known()` without copying the whole queue per `add`
  (previously `peek()` rebuilt a full list on every queued URL)
- Regression test proving event callbacks run outside `_callbacks_lock`: a
  blocked/slow callback no longer stalls `_emit_event()` for other emitters
- `StateManager.get_snapshot()` copies are now built from cheap shallow video
  copies instead of `copy.deepcopy`: every `Video`/`DownloadOptions` field is a
  value type, so isolation is identical at a fraction of the cost (~5.6x faster
  on queue-sized snapshots, measured over 2000 videos)
- `DownloadService` wakes its queue dispatcher immediately when a worker
  finishes a video, on `clear_queue()` and on `stop()` instead of relying on the
  poll timeouts (the waits remain as a safety net)
- Log terminal `_log_buffer` is now bounded (`max(5 * max_lines, 1000)`), so
  long sessions cannot grow it unbounded; `export_to_file()`/`get_logs()` return
  only the most recent lines that fit within the cap
- Removed unused `LogTerminal.append_separator()`/`set_auto_scroll()` (no
  callers in source or tests)
- PyInstaller build (`scripts/build.py`): dropped the redundant `--add-data`
  copy of `src/youmudow` (the compiled modules already live in the PYZ), hidden
  imports for the lazy `youmudow.ui.icon` and
  `youmudow.services.notification_service` modules, reduced Pillow to the
  plugins YouMuDow actually uses (JPEG/PNG/GIF/WebP via a
  `scripts/hooks/hook-PIL.Image.py` override), `--strip` on non-Windows and
  excludes for analysis-time-only environment modules (gi->GTK, keyring,
  pkg_resources/setuptools, matplotlib, numpy, ...). The Linux onefile bundle
  dropped from ~44.7 MB to ~17.3 MB (~61%) and starts in ~0.32 s instead of
  ~0.75 s
- Fixed a latent build bug: `PIL._imagingtk`/`PIL._tkinter_finder` are now
  bundled so thumbnails actually render through `ImageTk` in the frozen app
  (`hook-PIL.py` excludes `_tkinter_finder` because it imports `tkinter`)
- PyInstaller build: excluded the Ubuntu `apport_python_hook` chain
  (`apt`, `apt_pkg`) that analysis was pulling in, dropping
  `libapt-pkg.so`/`libsystemd.so`/`libgcrypt.so` from the bundle; hidden
  imports were reduced to the genuinely lazy modules (`youmudow.ui.icon`,
  `youmudow.services.notification_service`, `PIL.Image`/`PIL.ImageTk`,
  `PIL._imagingtk`/`PIL._tkinter_finder`) since the whole youmudow package
  graph is already reached statically from `main.py`. The Linux onefile bundle
  shrunk from ~17.3 MB to ~14.5 MB (~16%)
- `_handle_worker_event` now gates *every* worker event (including `PROGRESS`)
  on the `run_event`, so a lingering worker can no longer keep painting
  progress after `stop()` — coincidentally also hardening the restart path;
  and terminal events are matched against `active_downloads` by object
  identity instead of `url`, so a stale same-URL event from an earlier run can
  never delete or finalise a brand-new download of that URL

### Removed
- Dead `InvalidUrlError` and `ConfigurationError` exceptions (never raised or
  caught anywhere; zero references in source, tests or scripts); the hierarchy
  is now `YouMuDowError` → `DownloadError` → `YtDlpError` →
  `YtDlpNotFoundError`, and `docs/architecture.md` was updated to match
- Redundant empty `tests/unit/.gitkeep` (the directory holds real test files)

### Fixed
- `scripts/package.py` docstring claimed ffmpeg/yt-dlp were "bundled
  (Windows only for now)"; nothing is bundled — the deliverable is the
  executable plus a README that lists them as external requirements
- `AGENTS.md` pointed `COLORS` at `ui/window.py`; the palette lives in
  `ui/styles/colors.py`

### Changed
- Centralized format/quality sets (`SUPPORTED_FORMATS`, `SUPPORTED_QUALITIES`) in
  `domain/validators.py`, reused by the CLI, the GUI detail panel and the adapter
- `is_valid_format`/`is_valid_quality` validators for a single source of truth
- `DownloadService.start()`/`stop()` are now serialized by a dedicated
  `_lifecycle_lock`: a `start()` racing a `stop()` either wins completely or
  loses completely, so worker threads are never orphaned ("ghost workers")
- Download lifecycle: activation is now event-driven — a video moves to active
  only when the service reports it started, keeping `StateManager` and the
  service queue/active state consistent; `StateManager.start_download` is
  idempotent
- `DownloadService.stop()` is thread-safe, idempotent and reports workers that
  refuse to stop; downloads can restart cleanly after stop
- Duplicate queue entries (same URL already queued/active) are ignored, while a
  finished download can still be re-queued for retry
- Cancelling a queued video now closes its lifecycle: it is removed, marked
  `CANCELLED` and emits one `CANCELLED` event (idempotent across double-cancel)
- `StateManager.add_to_queue` mirrors the service's duplicate-URL guard, so the
  observable queue stays consistent with what the service actually processes
- `controller.reset()` preserves the configured concurrency and output path and
  re-attaches the log callback to the fresh service
- yt-dlp success with no attributable output file is now `ERROR` (previously it
  reported a bare `DONE` with no path); a file explicitly confirmed by yt-dlp's
  "already been downloaded" line is a valid result

### Fixed
- A terminal `COMPLETED` was emitted even when a download did not end in `DONE`
  (unknown/partial statuses now map to `ERROR`; only `DONE` maps to `COMPLETED`)
- Terminal events for videos no longer active (duplicates or leftovers from a
  previous run after restart) are dropped instead of corrupting the state
- Deadlock when a download event callback called `stop()`/`add_to_queue` (the
  STARTED event was broadcast while holding the service lock)
- Late worker events could still fire after stop(); they are now dropped once
  the service is stopped
- `max_retries=0` produced zero attempts (now treated as one attempt)
- Output resolution could mistake a pre-existing file for the new download;
  only files created during the run are considered
- Reader thread could stay alive if the subprocess died without closing stdout
  (stdout is now closed on the main thread before joining the reader)
- Huge playlists were fully enumerated even with a small limit (`--playlist-end`)
- CLI accepted invalid formats/qualities and unauthenticated-scheme URLs; it now
  validates URL/format/quality and returns 130 on Ctrl+C
- `DownloadService.download_now` no longer leaks adapter exceptions as phantom
  active downloads: failures map to `ERROR` and emit an `ERROR` event

## [5.0.0] - 2026-08-04

### Added
- **Command-line interface**: `youmudow-cli` with `download` (--format, --quality,
  --output, --skip-metadata) and `search` (--limit) subcommands, reusing the same
  services as the GUI
- **Packaged app icon**: icon moved into the package as `ui/icon.py` (previously
  in an unpackaged `assets/` directory, so the icon never loaded in the GUI)
- **Makefile**: `make install/run/test/coverage/lint/format/typecheck/check`
- **Pre-commit hooks**: `.pre-commit-config.yaml` (ruff lint + format, trailing
  whitespace, YAML checks)
- **CI build job**: PyInstaller build artifact uploaded from CI
- **Architecture documentation**: dependency rules table in `docs/architecture.md`
- **Screenshots**: real app screenshots added to `docs/screenshots/`

### Changed
- `--no-check-certificate` (TLS verification disabled) is no longer hardcoded;
  `YtdlpConfig.verify_certificates=True` by default and is configurable
- CI split into parallel `lint` / `typecheck` / `test` (Python 3.10–3.12) /
  `build` jobs with concurrency cancellation
- README rewritten with screenshots, CLI docs and Makefile-based development guide

### Fixed
- App icon never displayed because `assets/` was outside the package
- `docs/index.html` referenced a deleted `requirements.txt`

## [1.2.0] - 2026-08-04

### Added
- Centralized logging (`logging_config.setup_logging`) with console + optional file handler
- Custom exception hierarchy in `domain/exceptions.py` (`YouMuDowError`, `DownloadError`, `YtDlpError`, `YtDlpNotFoundError`, ...)
- `DownloadStatus.CANCELLED` — cancelled downloads now report `cancelled` instead of `error`
- Browser profile detection extracted to `adapters/browser_profiles.py`
- yt-dlp error parsing moved into `adapters/ytdlp_adapter.py` (`parse_yt_dlp_error`, `parse_cookie_error`)
- mypy type checking (strict on core layers) and ruff formatting added to quality gates
- pytest/coverage configuration in `pyproject.toml`

### Changed
- EventBus trimmed to log events only (`LOG_OUTPUT`, `LOG_CLEAR`) with typed `LogEvent`
- Removed dead code: `SearchService.search_by_url`, `get_unique_filename`, dead download events
- History now stores the real output file path (with extension) instead of `output/title`
- Playlist fetching no longer downloads the full playlist before applying the limit
- Adapter raises `YtDlpNotFoundError` when the yt-dlp binary is missing
- All `print`/`except Exception: pass` sites replaced with proper `logging`
- `AppConfig.get`/`get_search_history` typed; `get_str` helper added
- CI now runs mypy, ruff format check and coverage

### Fixed
- Cancellation could leave a download stuck in ERROR instead of CANCELLED
- Downloaded file resolution (`_resolve_output_file`) picks the real file by mtime

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
