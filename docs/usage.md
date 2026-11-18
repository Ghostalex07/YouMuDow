# Usage

## Basic Usage

1. Launch the application (`python -m youmudow`, `python -m youmudow.main` or the `youmudow` entry point).
2. Paste a URL or search for content in the search bar.
3. Select a result: the detail panel shows its duration and an estimated size.
4. Pick a preset ("Music 320", "Video 1080", "Archive FLAC") or set format,
   quality, cookies, rate limiting, chapter splitting and subtitles by hand.
   Editing any field switches the preset back to "Custom".
5. Click **Download** (or add to queue) and watch progress in the queue panel.

`View > User Guide` (or `F1`) opens the same information inside the app as a
closable tab.

## Playlists and Channels

Paste a playlist URL, an `@handle`, or a `/channel/`, `/c/`, `/user/` URL (with
or without `/videos`, `/shorts` or `/streams`). The first page loads
immediately; **Load more** in the detail panel appends the next page without
duplicating entries. A page shorter than `playlist_limit` means the playlist is
exhausted, and the button disables itself.

## Queue, Retries and Tray

- Failed downloads retry with a growing wait (`max_retries`, default 2, range
  0-5). Cancelling during a retry stops immediately.
- The pending queue is written to `queue.json` and restored on the next start;
  a download interrupted by quitting is queued again.
- `View > Keep Running in Tray` makes the close button hide the window instead
  of quitting, so the queue keeps going. The tray menu offers Show, Start
  downloads and Quit; Quit runs the same shutdown as `File > Exit`.

## Command-Line Interface

The `youmudow-cli` entry point provides a headless alternative that reuses the
same services as the GUI:

```bash
youmudow-cli download "URL" --format mp3 --quality 320kbps --output ~/Downloads
youmudow-cli download "SEARCH QUERY" --skip-metadata
youmudow-cli download "https://www.youtube.com/playlist?list=..." --limit 25
youmudow-cli search "lofi beats" --limit 10
youmudow-cli --version
```

- `download` options: `--format` (mp3, m4a, flac, wav, ogg, opus, aac, mp4, ...),
  `--quality` (bitrate or resolution), `--output DIR`, `--skip-metadata`
  (skip title resolution and download the URL directly), `--limit N` for
  playlists and channels (1-500).
- `search` options: `--limit N` (default 10).

## Configuration

Settings are persisted automatically to a JSON file under the OS config
directory (e.g. `~/.config/youmudow/config.json` on Linux). This includes the
output folder, default format/quality, cookie options, window geometry,
`playlist_limit`, `max_retries` and `minimize_to_tray`.

Besides `config.json` the app keeps `queue.json` (pending queue), `history.json`
(download history) and `youmudow.log`.

## Diagnostics

`Help > Export Diagnostics...` writes a single text file with the app version,
platform, Python, yt-dlp, ffmpeg, the YouTube environment probe, a redacted copy
of the config and the tail of the log. It runs off the UI thread, so the window
stays responsive.

## Output Formats

- Audio: MP3, M4A, OPUS, OGG, FLAC, WAV, AAC
- Video: MP4 (quality 360p/480p/720p/1080p/best)

## yt-dlp

YouMuDow requires the `yt-dlp` binary. Install it with `pip install yt-dlp` or
use **Help → Update yt-dlp** from within the app. ffmpeg must also be installed
for audio conversion and format merging.
