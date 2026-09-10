# YouMuDow

[![CI](https://github.com/Ghostalex07/YouMuDow/actions/workflows/ci.yml/badge.svg)](https://github.com/Ghostalex07/YouMuDow/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Ghostalex07/YouMuDow)](https://github.com/Ghostalex07/YouMuDow/releases)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A modern music & video downloader with real-time progress, persistent configuration, and a clean desktop interface. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) for support across 1000+ sites.

| Main window | Queue & progress |
|---|---|
| ![Main window](docs/screenshots/main.png) | ![Queue panel](docs/screenshots/queue.png) |

## Features

- Search by name or paste any URL (YouTube, SoundCloud, Vimeo, Twitter, ...)
- Download as MP3, M4A, FLAC, WAV, OGG, OPUS, AAC, or MP4
- Real-time progress bar and download log
- Cookie authentication (Chrome, Firefox, Edge, Brave, Opera, Vivaldi)
- Rate limiting, chapter splitting, subtitles
- Light/Dark theme, persistent configuration
- System notifications on completion
- Clipboard URL detection on startup
- `youmudow-cli` for headless downloads and searches
- Cross-platform: Linux, macOS, Windows

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) (required by yt-dlp for audio conversion)
- tkinter (included with Python on Windows/macOS; install `python3-tk` on Linux)

## Installation

### From source

```bash
git clone https://github.com/Ghostalex07/YouMuDow.git
cd YouMuDow
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
youmudow
```

Linux: `sudo apt install python3-tk` (Debian/Ubuntu) or `sudo dnf install python3-tkinter` (Fedora).

### Download executable

Download the latest release from the [Releases page](https://github.com/Ghostalex07/YouMuDow/releases). ffmpeg must be installed separately.

### ffmpeg

| Platform | Install |
|----------|---------|
| Debian/Ubuntu | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` |
| macOS | `brew install ffmpeg` |
| Windows | Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH |

## Usage

1. Enter a song name or paste a URL
2. Click a result to select it
3. Choose format and quality
4. Click **Download** (or add to queue)
5. Monitor progress in the queue panel

Advanced options: cookies, rate limiting, chapter splitting, and subtitles are available in the detail panel.

## CLI

`youmudow-cli` reuses the same services as the desktop app:

```bash
youmudow-cli download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format mp3
youmudow-cli download "bohemian rhapsody" --format mp3 --quality 320kbps
youmudow-cli download "https://..." --output ~/Downloads --skip-metadata
youmudow-cli search "lofi beats" --limit 10
```

Options: `--format`, `--quality`, `--output DIR`, `--skip-metadata`. Run `youmudow-cli --version`.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Search |
| `Ctrl+D` | Download selected |
| `Ctrl+Q` | Add to queue |
| `Ctrl+L` | Focus search |
| `Escape` | Cancel |
| `Ctrl+T` | Toggle theme |

## Development

```bash
make install     # pip install -e ".[dev]"
make run         # launch the desktop app
make test        # run tests
make check       # lint + format + typecheck + tests
```

Without `make`:

```bash
pip install -e ".[dev]"
PYTHONPATH=src python3 -m pytest
ruff check src/ tests/
PYTHONPATH=src mypy src/
```

## Building

```bash
pip install pyinstaller
python scripts/build.py          # → dist/YouMuDow
python scripts/package.py        # → dist/YouMuDow-<platform>.zip
python scripts/package.py --version 1.2.0  # → dist/YouMuDow-1.2.0-<platform>.zip
```

The release workflow builds for Linux, Windows, and macOS automatically when you push a version tag.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and how to submit changes.

## License

[MIT](LICENSE)

## AI/ML Use Restriction

This project publishes [`robots.txt`](robots.txt) and [`ai.txt`](ai.txt) to explicitly prohibit the use of its contents for AI/ML training, dataset creation, evaluation, or model development. See [`ai.txt`](ai.txt) for full details.
