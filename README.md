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
- Playlists and channels: paste a playlist, `@handle` or channel URL and queue
  every entry, loading them in pages of `playlist_limit` (1-500) with
  **Load more** for long playlists
- Download as MP3, M4A, FLAC, WAV, OGG, OPUS, AAC, or MP4
- Download presets ("Music 320", "Video 1080", "Archive FLAC") plus per-format
  options
- Duration and estimated size preview in the detail panel before downloading
- A first-run panel that explains what to do, with a "Paste from clipboard"
  button
- Sort results by relevance or duration, export a loaded playlist as `.m3u`,
  and pick several subtitle languages at once (`es,en`)
- **Add New** queues only the playlist entries the library has not downloaded
  yet, and the Library tab can scan the output folder to import files it does
  not know about
- Downloads stop with a clear message when the estimate does not fit in the
  free space left on the output volume
- Real-time progress bar and download log
- Cookie authentication (Chrome, Firefox, Edge, Brave, Opera, Vivaldi)
- Rate limiting, chapter splitting, subtitles
- Failed downloads retry automatically with backoff; the pending queue is
  restored on the next start
- Failures are grouped by cause ("2 private, 1 needs cookies, 1 network
  error") with a one-click **Retry failed**
- Optional system tray: closing the window can keep the queue running (needs a
  status-notifier host on Linux)
- `Help > Export Diagnostics...` writes version, ffmpeg, environment and a
  redacted config into one file for support
- English and Spanish interface, switchable in `View > Language` (automatic by
  default, following your system language); the in-app guide is translated too
- Checks GitHub for a newer release on startup and points you at it
  (`Help > Download Update...`); switch it off with `"check_for_updates": false`
- Built-in user guide: `View > User Guide` (or `F1`) opens a closable tab that
  documents search, playlists, formats, queue, tray and diagnostics
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
youmudow-cli search "lofi beats" --limit 10 --json
youmudow-cli history --limit 20 --json
youmudow-cli queue
youmudow-cli queue --clear
youmudow-cli doctor          # check ffmpeg, yt-dlp, folders and the database
youmudow-cli download "https://www.youtube.com/playlist?list=..." --limit 25
youmudow-cli download --from-file urls.txt --format mp3 --json
```

`--from-file` takes one URL per line (`#` comments and CSV columns work too)
and skips anything already in the download history, so a half-finished list
can be re-run safely. `--json` prints a machine-readable summary instead of
progress lines: `{"requested", "downloaded", "skipped", "failed", "results"}`.

Options: `--format`, `--quality`, `--output DIR`, `--skip-metadata`.

For a playlist or channel, `--limit N` sets how many entries to fetch (1-500,
defaulting to `playlist_limit`); the CLI prints `Found N video(s)` and a
`[i/N]` line per entry. Run `youmudow-cli --version` for the version.

### Headless server

`youmudow-cli serve` runs the queue with no window, using the same SQLite
library as the app, so downloads started from another device appear in the
desktop window:

```bash
youmudow-cli serve --port 8765 --token SECRET --output ~/Music

curl -s -H "Authorization: Bearer SECRET" -H "Content-Type: application/json" \
     -d '{"url":"https://youtu.be/xxxx","format":"mp3","quality":"320kbps"}' \
     http://127.0.0.1:8765/api/downloads
```

| Route | What it does |
|-------|--------------|
| `POST /api/downloads` | Queue `{"url", "format"?, "quality"?}` |
| `POST /api/downloads/batch` | Queue `{"urls": [...]}`, skipping duplicates; answers `{queued, skipped, rejected}` |
| `GET /api/downloads` | Queue, active downloads, paused flag |
| `POST /api/queue/pause` / `resume` | Pause or resume the queue |
| `DELETE /api/queue/{id}` | Drop a queued entry |
| `GET /api/health` | Version, queue size, active count |
| `GET /api/events` | Server-sent events with live progress |

Watch the queue live:

```bash
curl -N -H "Authorization: Bearer SECRET" http://127.0.0.1:8765/api/events
# : ready
# data: {"event": "QUEUED", "title": "...", "url": "...", "progress": 0.0}
```

It listens on `127.0.0.1` by default. Listening beyond localhost requires
`--token`, otherwise it refuses to start. Ctrl-C cancels the download in
flight and leaves it queued for the next run.

## Configuration

Settings live in the OS config directory as JSON:

| File | Contents |
|---|---|
| `config.json` | format, quality, output folder, `playlist_limit`, `max_retries`, `minimize_to_tray`, theme, cookies, search history |
| `queue.json` | the pending queue, restored on the next start |
| `history.json` | download history |
| `youmudow.db` | SQLite library: history, pending queue, subscriptions |
| `youmudow.log` | application log (rotates at 5 MB, three backups) |

On Linux that is `~/.config/youmudow`, on Windows `%APPDATA%\YouMuDow`, on
macOS `~/Library/Application Support/youmudow`. Cookie paths and browser
profiles are never written to `queue.json`.

## Troubleshooting

- **Gatekeeper / SmartScreen warning** — the binaries are not code-signed, so
  macOS and Windows show a first-run prompt. On macOS, right-click the app and
  choose Open once; on Windows, "More info" then "Run anyway".
- **No tray icon on Linux** — the tray needs a status-notifier host (most
  desktops have one; GNOME needs the AppIndicator extension). Without it the
  app logs a line and keeps working normally.
- **Something failed** — `Help > Export Diagnostics...` writes version,
  platform, yt-dlp, ffmpeg, the YouTube environment, a redacted config and the
  last 256 KB of the log into one file you can attach to a report.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Search |
| `Ctrl+D` | Download selected |
| `Ctrl+Q` | Add to queue |
| `Ctrl+L` | Focus search |
| `Escape` | Cancel |
| `Ctrl+T` | Toggle theme |
| `Ctrl+Shift+S` | Start the queue |
| `Delete` | Remove the selected row from the queue |
| `F1` | Open the user guide |

You can also drag a link from your browser onto the window to search it.

## Development

```bash
make install     # pip install -e ".[dev]"
make run         # launch the desktop app
make test        # run tests
make test-ui     # full-stack UI tests (needs a display; uses xvfb-run if present)
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

See [docs/contributing.md](docs/contributing.md) for development setup and how to submit changes.

## License

[MIT](LICENSE)
