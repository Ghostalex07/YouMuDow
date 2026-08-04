# Architecture

## Overview

YouMuDow is a Python 3.10+ desktop application built with **Tkinter**. It wraps
[yt-dlp](https://github.com/yt-dlp/yt-dlp) to search and download music and video
from 1000+ sites. The codebase follows a layered architecture where dependencies
flow one way: `ui → app → services → domain`, with `adapters` providing the
external tooling.

## Layered Architecture

```
┌─────────────────────────────┐
│  ui/   (Tkinter widgets)     │  presentation only
├─────────────────────────────┤
│  app/  (controller, state,   │  coordination, config, events
│        config, event bus)    │
├─────────────────────────────┤
│  services/ (business logic)  │  downloads, search, history
├─────────────────────────────┤
│  domain/ (models, enums,     │  pure data & validation
│        validators, errors)   │
├─────────────────────────────┤
│  adapters/ (yt-dlp, browser) │  external integrations
└─────────────────────────────┘
```

Each layer imports only from the layers below it. `domain` has no imports from
the rest of the application.

## Domain Layer (`domain/`)

Pure data models and validation, no I/O.

- `models.py` — `Video`, `DownloadOptions`, `HistoryEntry` dataclasses and their
  helpers (`from_metadata`, `format_size`, ...).
- `enums.py` — `DownloadStatus`, `DownloadEventType`, quality/format constants.
- `validators.py` — URL validation (`is_valid_youtube_url`, `is_playlist_url`),
  filename sanitization, rate-limit validation.
- `exceptions.py` — exception hierarchy rooted at `YouMuDowError`
  (`InvalidUrlError`, `DownloadError`, `YtDlpError`, `YtDlpNotFoundError`,
  `ConfigurationError`).

## Adapters Layer (`adapters/`)

External tooling behind a stable interface.

- `ytdlp_adapter.py` — runs `yt-dlp` as a subprocess; builds download/search
  argument lists, streams progress via callbacks, resolves the downloaded file,
  and translates raw yt-dlp output into user-friendly error messages
  (`parse_yt_dlp_error`).
- `browser_profiles.py` — detects installed browsers and their profile
  directories per platform (`check_browser_profile`, `get_available_browsers`,
  `get_all_browser_profiles`).

## Services Layer (`services/`)

Business logic that coordinates adapters and domain objects.

- `search_service.py` — search, single-video metadata and playlist fetching.
- `download_service.py` — download queue with configurable concurrency, worker
  threads, cancellation and progress events.
- `history_service.py` — persistent download history stored as JSON.
- `thumbnail_service.py` — URL generation for video thumbnails.
- `notification_service.py` — cross-platform desktop notifications
  (`notify-send` / `osascript` / `plyer`).
- `updater_service.py` — checks and self-updates the yt-dlp binary.

## App Layer (`app/`)

Coordination between the UI and services.

- `controller.py` — the single entry point the UI talks to; wires state, search,
  downloads and history together.
- `state.py` — `StateManager` holds the observable application state
  (`AppState`, search results, error messages).
- `config.py` — `AppConfig` persists user settings as JSON under the OS config
  directory.
- `events.py` — lightweight pub/sub event bus (`EventBus`) used to stream real-time
  download logs to the UI (`emit_log`).

## UI Layer (`ui/`)

Tkinter interface. No business logic lives here; every action is delegated to
`AppController`.

- `window.py` — `MainWindow`: main window, notebook tabs, menu bar, shortcuts.
- `widgets/` — `search_bar`, `results_table`, `detail_panel`, `history_panel`,
  `log_terminal`, `status_bar`.
- `styles/` — theme definitions and ttk styling (`styles.py`, `theme.py`,
  `constants.py`).

## Entry Point

`main.py` loads the config, sets up centralized logging (`logging_config.py`),
instantiates `AppController` and `MainWindow`, and starts the Tkinter main loop.

## Concurrency Model

- Search, metadata, playlist, history, update and notification operations run on
  short-lived background threads and report back through callbacks or the
  state manager.
- Downloads run in worker threads owned by `DownloadService`. Cancellation is
  cooperative: a `threading.Event` is checked by the adapter, which terminates
  the yt-dlp subprocess and marks the video as `CANCELLED`.
- The Tk UI thread is only ever touched via `root.after(...)`.

## Error Handling

- Services raise typed exceptions from `domain/exceptions.py`; the UI layer
  decides how to present them.
- Raw yt-dlp output is turned into friendly messages by
  `parse_yt_dlp_error`.
- All `except Exception: pass` blocks have been replaced with
  `logging.debug/exception` so failures are observable.

## Logging

Centralized in `logging_config.setup_logging()`: a consistent format, an INFO
console handler and an optional file handler (`logs/youmudow.log`). Modules use
`logging.getLogger(__name__)`.
