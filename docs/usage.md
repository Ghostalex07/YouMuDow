# Usage

## Basic Usage

1. Launch the application (`python -m youmudow.main` or the `youmudow` entry point).
2. Paste a URL or search for content in the search bar.
3. Select a result and choose format/quality.
4. Optionally enable cookies, rate limiting, chapter splitting or subtitles.
5. Click **Download** (or add to queue) and watch progress in the queue panel.

## Configuration

Settings are persisted automatically to a JSON file under the OS config
directory (e.g. `~/.config/youmudow/config.json` on Linux). This includes the
output folder, default format/quality, cookie options and window geometry.

## Output Formats

- Audio: MP3, M4A, OPUS, OGG, FLAC, WAV, AAC
- Video: MP4 (quality 360p/480p/720p/1080p/best)

## yt-dlp

YouMuDow requires the `yt-dlp` binary. Install it with `pip install yt-dlp` or
use **Help → Update yt-dlp** from within the app. ffmpeg must also be installed
for audio conversion and format merging.
