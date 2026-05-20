# Changelog

All notable changes to this project will be documented in this file.

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
