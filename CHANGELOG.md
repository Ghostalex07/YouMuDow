# Changelog

All notable changes to this project will be documented in this file.

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
