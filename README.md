# YouMuDow

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.1.0-green.svg)
[![CI](https://github.com/Ghostalex07/YouMuDow/actions/workflows/ci.yml/badge.svg)](https://github.com/Ghostalex07/YouMuDow/actions/workflows/ci.yml)

A modern music & video downloader with real-time progress, embedded metadata, and a clean desktop interface.

## Features

- **Multi-site support**: YouTube, SoundCloud, Vimeo, Twitter and 1000+ sites via yt-dlp
- **Multi-format downloads**: MP3, MP4, WAV, M4A, FLAC, AAC, OGG
- **Embedded metadata and thumbnails**: Title, artist, thumbnail automatically added to files
- **Real-time progress bar and download log**: See progress as it happens
- **Queue system with visible queue panel**: Manage queued, active, and completed downloads
- **Thumbnail preview in detail panel**: See video thumbnails using Pillow
- **Persistent configuration**: Remembers output folder, format, cookies, window geometry
- **System notifications on completion**: Desktop notification when download finishes
- **Light/Dark theme**: Toggle between light and dark themes (Ctrl+T)
- **Cookie authentication**: Chrome, Firefox, Edge, Brave, Opera, Vivaldi, multi-profile support
- **Rate limiting, chapter splitting, subtitle download**: Advanced download options
- **yt-dlp auto-updater built in**: Help > Update yt-dlp keeps it current
- **Export download logs to file**: File > Export Logs saves session logs
- **Retry failed downloads**: One-click retry for errored downloads
- **Clipboard URL detection on startup**: Automatically detects URLs in clipboard
- **Cross-platform**: Linux, macOS, Windows
- **Keyboard shortcuts**: Ctrl+D to download, Ctrl+Q to queue, and more

## Requirements

- Python 3.10+
- ffmpeg (required by yt-dlp)
- tkinter (included with Python on Windows/macOS; needs separate install on Linux)

## Installation

### Option 1: Run from source

```bash
git clone https://github.com/Ghostalex07/YouMuDow.git
cd YouMuDow
pip install -e ".[dev]"
youmudow
```

### Option 2: Download executable

Download the latest release from the [Releases page](https://github.com/Ghostalex07/YouMuDow/releases).
ffmpeg must still be installed separately.

## ffmpeg Installation

### Linux

```bash
sudo apt install ffmpeg       # Debian/Ubuntu
sudo dnf install ffmpeg       # Fedora
```

### macOS

```bash
brew install ffmpeg
```

### Windows

Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

## Usage

1. **Search**: Enter a song name or paste a URL (YouTube, SoundCloud, etc.)
2. **Select**: Click on a result
3. **Choose format**: Select MP3, MP4, WAV, or M4A
4. **Download options** (optional):
   - **Cookies**: Enable and select browser or import cookies file
   - **Rate limit**: Limit download speed (e.g., `1M`, `500K`)
   - **Split chapters**: Split video into separate files per chapter
   - **Subtitles**: Download and embed subtitles
5. **Download**: Click Download or add to queue
6. **Monitor**: Watch progress in the queue panel and status bar

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Search |
| `Ctrl+D` | Download selected |
| `Ctrl+Q` | Add to queue |
| `Ctrl+L` | Focus search field |
| `Ctrl+N` | Clear search field |
| `Escape` | Cancel operation |
| `Ctrl+V` | Paste URL (auto-replaces field) |
| `Ctrl+T` | Toggle light/dark theme |

## Building from source

```bash
pip install pyinstaller
python scripts/build.py       # generates executable in dist/
python scripts/package.py     # generates distributable ZIP
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/
```

## Project Structure

```
youmudow/
├── src/youmudow/
│   ├── __init__.py            # App version
│   ├── main.py                # Entry point
│   ├── domain/                # Data models, validators
│   │   ├── models.py
│   │   ├── enums.py
│   │   └── validators.py
│   ├── adapters/              # yt-dlp integration
│   │   └── ytdlp_adapter.py
│   ├── services/              # Business logic
│   │   ├── download_service.py
│   │   ├── search_service.py
│   │   ├── metadata_service.py
│   │   ├── notification_service.py
│   │   └── updater_service.py
│   ├── app/                   # Application layer
│   │   ├── controller.py
│   │   ├── state.py
│   │   ├── config.py
│   │   └── events.py
│   └── ui/                    # Interface layer
│       ├── window.py
│       ├── styles/
│       └── widgets/
│           └── log_terminal.py
├── tests/
│   └── unit/
├── scripts/
│   ├── build.py               # PyInstaller build
│   └── package.py             # Distribution packaging
├── .github/workflows/
│   ├── ci.yml                 # CI pipeline
│   └── release.yml            # Automated release
├── CHANGELOG.md
├── README.md
└── pyproject.toml
```

## License

MIT License - See [LICENSE](LICENSE) for details.
