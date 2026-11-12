# Architecture

## Overview

YouMuDow is a Python 3.10+ desktop application built with **Tkinter**. It wraps
[yt-dlp](https://github.com/yt-dlp/yt-dlp) to search and download music and video
from 1000+ sites. The codebase follows a layered architecture where dependencies
flow one way: `ui → app → services → domain`, with `adapters` providing the
external tooling.

## Layered Architecture

```
┌────────────────────────────────────────────────────┐
│  ui/    (Tkinter widgets)      presentation only   │
├────────────────────────────────────────────────────┤
│  app/   (controller, state,    coordination,       │
│          config, event bus)    config, events      │
├────────────────────────────────────────────────────┤
│  services/  (business logic)   downloads, search,   │
│                                history             │
├────────────────────────────────────────────────────┤
│  domain/  (models, enums,      pure data &          │
│           validators, errors)  validation          │
├────────────────────────────────────────────────────┤
│  adapters/  (yt-dlp, browser)  external tooling    │
├────────────────────────────────────────────────────┤
│  External:  yt-dlp · ffmpeg ·  0 dependencies      │
│             browser profiles   allowed downward    │
└────────────────────────────────────────────────────┘
```

Dependencies flow strictly downward: `ui → app → services → domain`, with
`adapters` sitting at the boundary to the outside world. Each layer imports only
from the layers below it.

## Dependency Rules

| Layer | May import from | Must not import from |
|-------|-----------------|----------------------|
| `ui` | `app`, `services`, `domain`, `adapters` | anything else in the package |
| `app` | `services`, `domain` | `ui` (no Tkinter in controllers) |
| `services` | `domain`, `adapters` | `app`, `ui` |
| `domain` | stdlib only | the rest of the application |
| `adapters` | `domain` | `app`, `services`, `ui` |

These rules are enforced by code review and kept visible by the mypy
configuration (the `ui` layer is type-checked permissively because Tkinter
widgets are deliberately dynamic).

## Domain Layer (`domain/`)

Pure data models and validation, no I/O.

- `models.py` — `Video`, `DownloadOptions`, `HistoryEntry` dataclasses and their
  helpers (`from_metadata`, `format_size`, ...).
- `enums.py` — `DownloadStatus`, the download lifecycle states.
- `validators.py` — URL validation (`is_valid_youtube_url`, `is_playlist_url`),
  filename sanitization, rate-limit validation.
- `exceptions.py` — exception hierarchy rooted at `YouMuDowError`
  (`DownloadError` → `YtDlpError` → `YtDlpNotFoundError`).

## Adapters Layer (`adapters/`)

External tooling behind a stable interface.

- `ytdlp_adapter.py` — `YtdlpAdapter`: orchestration of search, metadata,
  playlist and download. It composes the helpers below and re-exports
  `YtdlpConfig`, `ProgressInfo`, `parse_yt_dlp_error` and
  `parse_cookie_error`, so existing imports keep working.
- `ytdlp_args.py` — pure builders for the yt-dlp argument lists (format,
  quality and subtitle selectors).
- `ytdlp_parsing.py` — pure parsers: progress lines, metadata JSON, flat
  playlist entries, durations and yt-dlp error messages.
- `ytdlp_process.py` — subprocess execution, inactivity timeout, process-group
  signals and cooperative cancellation.
- `ytdlp_files.py` — resolves the file a finished download produced.
- `browser_profiles.py` — detects installed browsers and their profile
  directories per platform (`check_browser_profile`, `get_available_browsers`,
  `get_all_browser_profiles`).

## Services Layer (`services/`)

Business logic that coordinates adapters and domain objects.

- `search_service.py` — search, single-video metadata and playlist fetching.
- `download_service.py` — `DownloadService` owns the worker pool, the
  concurrency limit and the callback fan-out; it re-exports the symbols moved
  to the modules below so existing imports keep working.
- `download_queue.py` — `DownloadQueue`, the single owner of queued videos,
  plus the identity-or-URL matchers (`is_same_video`, `find_video_index`,
  `find_entry_index`).
- `download_worker.py` — `DownloadWorker`: one download from start to finish.
- `download_events.py` — `DownloadEventType`, `DownloadProgress`,
  `DownloadEvent`, the progress/event vocabulary shared with `app/state.py`.
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

- `window.py` — `MainWindow`: composition and wiring of the notebook tabs and
  shortcuts; menus, startup checks and side-effecting commands live in the
  modules below.
- `menubar.py` — builds the menu bar from the callbacks `MainWindow` provides.
- `startup_checks.py` — startup checks (clipboard, yt-dlp, YouTube environment).
- `actions.py` — log export, open download folder, about, yt-dlp update and
  repair.
- `widgets/` — `search_bar`, `results_table`, `detail_panel` (video details and
  thumbnail, composed of `options_panel` and `queue_panel`), `history_panel`,
  `log_terminal`, `status_bar`.
- `styles/` — theme definitions, ttk styling and the repaint rule table
  (`styles.py`, `theme.py`, `theme_apply.py`, `constants.py`).

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
console handler and an optional file handler (`youmudow.log` in the OS config
directory). Modules use `logging.getLogger(__name__)`.
