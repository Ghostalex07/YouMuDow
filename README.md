# YouMuDow

A modern YouTube music downloader with real-time progress, embedded metadata, and a clean desktop interface.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

- **Multi-format downloads**: MP3, MP4, WAV, M4A, FLAC, AAC, OGG
- **Embedded metadata**: Title, artist, thumbnails automatically added to files
- **Real-time terminal**: View download progress and logs as they happen
- **Queue system**: Download multiple videos sequentially
- **Clean GUI**: Simple and intuitive interface built with Tkinter
- **Cross-platform**: Works on Linux, Windows, and macOS
- **Cookie authentication**: 
  - Browser cookies (Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Chromium)
  - Multi-profile support (select specific browser profile)
  - Cookies file import (.txt Netscape format)
- **Download options**:
  - Rate limiting (e.g., 1M, 500K)
  - Chapter splitting (split video into chapters)
  - Multi-language subtitles
  - Advanced quality selection (1080p, 720p, 480p)
  - Audio quality (320kbps, 256kbps, 192kbps, etc.)
- **Error handling**: Automatic retry without cookies on failure, fallback browser detection
- **Comprehensive tests**: 111 unit tests

## Screenshots

```
┌─────────────────────────────────────────────────────────┐
│ YouMuDow                                    [Debug Mode] │
├─────────────────────────────────────────────────────────┤
│ [Search...                              ] [Search]       │
├───────────────────────────────────┬─────────────────────┤
│ Title        │ Uploader  │ Dur.  │ Details             │
│──────────────┼───────────┼───────│────────────────────│
│ Song 1       │ Artist    │ 3:45  │ Title: Song 1      │
│ Song 2       │ Artist    │ 4:12  │ Uploader: Artist   │
│                                 │ Format: [MP3 ▼]    │
│                                 │ [Add to Queue]     │
├─────────────────────────────────────────────────────────┤
│ Output Log                                               │
│─────────────────────────────────────────────────────────│
│ [12:00:00] [DOWNLOAD] Starting: Song 1                 │
│ [12:00:05] [download] 45.5% at 1.2MiB/s ETA 00:30   │
│ [12:00:30] [DONE] Song 1                              │
├─────────────────────────────────────────────────────────┤
│ Downloading: 45.5%                          ███████░░░ │
└─────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.10+
- yt-dlp
- ffmpeg
- tkinter (usually included with Python)

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install python3-tk ffmpeg
pip install yt-dlp
```

### Windows

1. Install Python 3.10+ from [python.org](https://python.org)
2. Install ffmpeg and add to PATH
3. Run: `pip install yt-dlp`

### Browser Cookies (Optional)

For cookie authentication, ensure one of these browsers is installed:
- Chrome / Chromium
- Firefox
- Edge
- Brave
- Opera
- Vivaldi

The app will automatically detect installed browsers and show them in the dropdown.

## Installation

### Option 1: Clone and install

```bash
git clone https://github.com/YourUsername/YouMuDow.git
cd YouMuDow
pip install -e .
```

### Option 2: Run directly

```bash
git clone https://github.com/YourUsername/YouMuDow.git
cd YouMuDow
PYTHONPATH=src python3 -m youmudow.main
```

## Usage

1. **Search**: Enter a song name or paste a YouTube URL
2. **Select**: Click on a result
3. **Choose format**: Select MP3, MP4, WAV, or M4A
4. **Download options** (optional):
   - **Cookies**: Enable and select browser (Firefox, Chrome, etc.) or import cookies file
   - **Profile**: Choose browser profile for authentication
   - **Rate limit**: Limit download speed (e.g., 1M, 500K)
   - **Split chapters**: Split video into separate files per chapter
   - **Subtitles**: Download and embed subtitles (multiple languages supported)
5. **Download**: Click "Download Now" or add to queue
6. **Debug Mode**: Enable via View → Debug Mode to see real-time logs

## Project Structure

```
youmudow/
├── src/youmudow/
│   ├── main.py              # Entry point
│   ├── domain/              # Data models
│   │   ├── models.py       # Video model
│   │   ├── enums.py        # DownloadStatus
│   │   └── validators.py   # URL validation
│   ├── adapters/           # External tools
│   │   └── ytdlp_adapter.py
│   ├── services/           # Business logic
│   │   ├── search_service.py
│   │   ├── download_service.py
│   │   ├── metadata_service.py
│   │   └── thumbnail_service.py
│   ├── app/                # Application layer
│   │   ├── controller.py   # Main controller
│   │   ├── state.py       # State management
│   │   └── events.py      # Event system
│   └── ui/                # Interface layer
│       ├── window.py       # Main window
│       ├── styles/         # Theme system
│       └── widgets/       # Reusable widgets
├── tests/
│   └── unit/              # Unit tests
├── docs/                  # Documentation
└── scripts/               # Build scripts
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Format code
ruff check src/
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    UI Layer (Tkinter)               │
│  MainWindow → Controllers → Widgets                │
└─────────────────────────┬────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────┐
│              App Layer (Controller)                  │
│  State Management ← Events ← Business Logic         │
└─────────────────────────┬────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────┐
│              Services Layer                           │
│  SearchService → DownloadService → MetadataService    │
└─────────────────────────┬────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────┐
│              Adapter Layer (yt-dlp)                  │
│  YtdlpAdapter → subprocess → yt-dlp binary          │
└──────────────────────────────────────────────────────┘
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

See [docs/contributing.md](docs/contributing.md) for development guidelines.
