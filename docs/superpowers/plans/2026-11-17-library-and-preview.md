# Library, Preview and Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** finish playlist/channel support, add a pre-download size preview and download presets, without duplicating the playlist, subtitle or chapter code that already ships.

**Architecture:** URL classification stays in `domain/validators.py`; format parsing and size estimation are pure functions in `domain/formats.py`; the yt-dlp command for formats lives in `adapters/ytdlp_args.py`; the subprocess call in `adapters/ytdlp_adapter.py`; orchestration in `app/controller.py`; rendering in `ui/widgets/detail_panel.py`. Presets are data in `domain/presets.py` applied by `ui/widgets/options_panel.py`.

**Tech Stack:** Python 3.10, yt-dlp CLI (`--dump-single-json`), tkinter/ttk.

**Spec:** `docs/superpowers/specs/2026-11-17-next-features.md`

**Prerequisite:** Task 6 extends `tests/integration/test_search_flow.py`; that
file and its `stack` fixture come from
`docs/superpowers/plans/2026-11-17-full-stack-ui-tests.md`. If that plan has
not been executed yet, skip the integration half of Task 6 Step 4 and run only
the unit half.

## Global Constraints

- Python 3.10+, ruff line length 100, layers only depend upwards.
- Subprocesses never run on the Tk main thread; results come back via
  `MainWindow._schedule`.
- Any new yt-dlp flag goes through `adapters/ytdlp_args.py` as a pure function.
- Tests: `.venv/bin/python -m pytest tests/ -q`; UI tests need `xvfb-run -a`.
- Missing/odd yt-dlp JSON must degrade to "no estimate", never raise.

## Review Focus

- A channel URL with a trailing slash or `?sub_confirmation=1`: must still be
  classified as a playlist.
- A live stream or a video where `duration` is `None`: the estimate must be
  omitted, not crash or show `0 B`.
- Playlists longer than the limit: the flat listing must stop at the limit and
  the UI must say how many entries were loaded.
- A 4K-only video asked for 360p: the estimate must pick a format the selector
  would actually download, or show nothing — never the 4K size.
- A preset that conflicts with the current cookies state: applying a preset
  must not silently enable or disable cookie use.

---

### Task 1: Recognise channel URLs

**Files:**
- Modify: `src/youmudow/domain/validators.py:18-80`
- Test: `tests/unit/test_validators.py`

**Interfaces:**
- Consumes: `is_playlist_url(url: str) -> bool` (existing, used by
  `MainWindow._on_search`).
- Produces: same signature; now also true for
  `youtube.com/@handle`, `youtube.com/@handle/videos`, `/channel/UC…`,
  `/c/Name`, `/user/Name`, with an optional trailing slash or `?query`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/@lofigirl",
        "https://www.youtube.com/@lofigirl/videos",
        "https://www.youtube.com/@lofigirl/videos/",
        "https://www.youtube.com/@lofigirl?sub_confirmation=1",
        "https://youtube.com/channel/UCabc123",
        "https://www.youtube.com/c/SomeName",
        "https://www.youtube.com/user/oldname/videos",
    ],
)
def test_channel_urls_are_playlists(url):
    assert is_playlist_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/",
        "https://www.youtube.com/feed/subscriptions",
        "https://www.youtube.com/watch?v=abc",
        "https://example.com/@notyoutube",
    ],
)
def test_non_channel_urls_are_not_playlists(url):
    assert is_playlist_url(url) is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_validators.py -q -k channel`
Expected: FAIL for the bare `@handle`, `/c/`, `/user/` variants.

- [ ] **Step 3: Extend `is_playlist_url`**

Add a module constant
`CHANNEL_PATTERN = r"(?:https?://)?(?:www\.|m\.)?youtube\.com/(?:@[\w.-]+|channel/[\w-]+|c/[\w-]+|user/[\w-]+)(?:/(?:videos|shorts|streams))?/?(?:[?#].*)?"`
and return `bool(CHANNEL_REGEX.match(url.strip())) or <existing checks>`.
Keep the existing SoundCloud/Bandcamp/`/playlist` rules.

- [ ] **Step 4: Run the validator suite**

Run: `.venv/bin/python -m pytest tests/unit/test_validators.py -q`
Expected: all pass, including the previously passing cases.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/domain/validators.py tests/unit/test_validators.py
git commit -m "feat: recognise YouTube channel URLs as playlists"
```

---

### Task 2: Configurable playlist limit

**Files:**
- Modify: `src/youmudow/app/config.py:20-46` (defaults), `:100-143` (property)
- Modify: `src/youmudow/app/controller.py:201-219` (`search_playlist`)
- Test: `tests/unit/test_config.py`, `tests/unit/test_controller.py`

**Interfaces:**
- Consumes: `AppConfig.get(key, default)`.
- Produces: `AppConfig.playlist_limit -> int` (getter) and setter clamping to
  `1..500`; `AppController.search_playlist(url, limit: int | None = None)`,
  falling back to the config value, then 50.

- [ ] **Step 1: Write the failing tests**

```python
def test_playlist_limit_defaults_to_50(tmp_path, monkeypatch):
    config = _make_config(tmp_path, monkeypatch)  # existing helper in the file
    assert config.playlist_limit == 50


def test_playlist_limit_is_clamped(tmp_path, monkeypatch):
    config = _make_config(tmp_path, monkeypatch)
    config.playlist_limit = 0
    assert config.playlist_limit == 1
    config.playlist_limit = 10_000
    assert config.playlist_limit == 500
    config.playlist_limit = 200
    assert config.playlist_limit == 200
```

In `tests/unit/test_controller.py`:

```python
def test_search_playlist_uses_the_configured_limit():
    config = Mock()
    config.get.side_effect = lambda key, default=None: 120 if key == "playlist_limit" else default
    controller = AppController(search_service=Mock(), download_service=Mock(), config=config)
    controller.search_playlist("https://youtube.com/@x")
    controller._search_service.get_playlist.assert_called_once_with("https://youtube.com/@x", 120)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_config.py tests/unit/test_controller.py -q -k playlist_limit`
Expected: FAIL — `AppConfig` has no `playlist_limit`.

- [ ] **Step 3: Implement**

`DEFAULT_CONFIG["playlist_limit"] = 50`; add the property pair with
`max(1, min(500, int(value)))`. In `search_playlist`, resolve
`limit = limit or (self._config.get("playlist_limit", 50) if self._config else 50)`
and pass it through.

- [ ] **Step 4: Run and commit**

Run: `.venv/bin/python -m pytest tests/unit -q`
Commit `feat: make the playlist limit configurable`.

---

### Task 3: Playlists and channels from the CLI

**Files:**
- Modify: `src/youmudow/cli.py:44-140`
- Test: `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: `is_playlist_url(url)`, `SearchService.get_playlist(url, limit)`,
  `DownloadService.download_now(video, output_dir, progress_callback=...)`.
- Produces: `youmudow-cli download URL [--limit N]`; when the URL is a
  playlist/channel it prints `Found N video(s)`, downloads them one at a time
  and returns 0 only if every download succeeded (else 1).

- [ ] **Step 1: Write the failing tests**

```python
def test_download_expands_playlists(monkeypatch, tmp_path, capsys):
    videos = [Video(title=f"V{i}", url=f"https://example.com/{i}") for i in range(2)]
    search = Mock()
    search.get_playlist.return_value = videos
    service = Mock()
    service.download_now.side_effect = lambda video, path, progress_callback=None: _done(video)
    monkeypatch.setattr("youmudow.cli.SearchService", lambda: search)
    monkeypatch.setattr("youmudow.cli.DownloadService", lambda: service)
    code = main(["download", "https://www.youtube.com/@chan", "--limit", "2", "--output", str(tmp_path)])
    assert code == 0
    search.get_playlist.assert_called_once_with("https://www.youtube.com/@chan", 2)
    assert service.download_now.call_count == 2
    assert "Found 2 video(s)" in captured.out


def test_playlist_with_one_failure_returns_one(monkeypatch, tmp_path):
    # first download DONE, second ERROR
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q -k playlist`
Expected: FAIL — `--limit` is not accepted and the URL goes to `get_metadata`.

- [ ] **Step 3: Implement**

In `_cmd_download`, before fetching single metadata:
```python
if is_playlist_url(args.url):
    videos = SearchService().get_playlist(args.url, args.limit)
    if not videos:
        print(f"No videos found in {args.url}", file=sys.stderr)
        return 1
    print(f"Found {len(videos)} video(s)")
    failures = 0
    for index, video in enumerate(videos, start=1):
        print(f"[{index}/{len(videos)}] {video.title}")
        video.options = options
        result = service.download_now(video, output_dir, progress_callback=on_progress)
        if result.status != DownloadStatus.DONE:
            failures += 1
    return 0 if failures == 0 else 1
```
Add `download.add_argument("--limit", type=_positive_int, default=50, help="maximum playlist entries")`.
Reuse the existing `on_progress` printing and `KeyboardInterrupt` handling.

- [ ] **Step 4: Run and commit**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q`
Commit `feat: download playlists and channels from the CLI`.

---

### Task 4: Parse formats and estimate size (pure functions)

**Files:**
- Create: `src/youmudow/domain/formats.py`
- Create: `src/youmudow/domain/sizes.py`
- Modify: `src/youmudow/domain/models.py:96-115` (`HistoryEntry.format_size`)
- Test: `tests/unit/test_formats.py`, `tests/unit/test_sizes.py`

**Interfaces:**
- Produces:
  - `sizes.format_size(num_bytes: int) -> str` (moved from
    `HistoryEntry.format_size`, same output).
  - `formats.FormatInfo` frozen dataclass with
    `format_id: str, ext: str, height: int, abr: float, tbr: float, filesize: int`.
  - `formats.parse_formats(payload: dict[str, Any]) -> list[FormatInfo]`.
  - `formats.estimate_size(formats: Sequence[FormatInfo], options: DownloadOptions, duration: int) -> int | None`.
- Consumes: `DownloadOptions.quality`, `AUDIO_FORMATS`, video quality names.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_formats_reads_sizes_and_falls_back_to_approx():
    payload = {"formats": [
        {"format_id": "251", "ext": "webm", "abr": 160.0, "filesize": 1000},
        {"format_id": "140", "ext": "m4a", "abr": 128.0, "filesize_approx": 2000},
        {"ext": "mp4", "vcodec": "none"},
    ]}
    result = parse_formats(payload)
    assert [f.format_id for f in result] == ["251", "140"]
    assert result[1].filesize == 2000


def test_parse_formats_tolerates_garbage():
    assert parse_formats({}) == []
    assert parse_formats({"formats": "nope"}) == []


def test_audio_estimate_uses_the_requested_bitrate():
    options = DownloadOptions(file_format="mp3", quality="320kbps")
    assert estimate_size([], options, duration=60) == 60 * 320_000 // 8


def test_audio_estimate_best_uses_the_highest_bitrate():
    options = DownloadOptions(file_format="mp3", quality="best")
    formats = [FormatInfo("1", "m4a", 0, 128.0, 0.0, 0), FormatInfo("2", "m4a", 0, 256.0, 0.0, 0)]
    assert estimate_size(formats, options, 60) == 60 * 256_000 // 8


def test_video_estimate_picks_the_best_format_at_or_below_the_target():
    options = DownloadOptions(file_format="mp4", quality="720p")
    formats = [
        FormatInfo("137", "mp4", 1080, 0.0, 0.0, 50_000_000),
        FormatInfo("136", "mp4", 720, 0.0, 0.0, 20_000_000),
        FormatInfo("135", "mp4", 480, 0.0, 0.0, 8_000_000),
    ]
    assert estimate_size(formats, options, 60) == 20_000_000


def test_video_estimate_says_nothing_when_only_larger_formats_exist():
    options = DownloadOptions(file_format="mp4", quality="360p")
    formats = [FormatInfo("313", "mp4", 2160, 0.0, 0.0, 900_000_000)]
    assert estimate_size(formats, options, 60) is None


def test_estimate_is_none_without_duration_or_formats():
    assert estimate_size([], DownloadOptions(), 0) is None
    assert estimate_size([], DownloadOptions(file_format="mp4", quality="720p"), 60) is None


@pytest.mark.parametrize("value,expected", [(0, ""), (999, "999.0 B"), (1024, "1.0 KB"), (5 * 1024**2, "5.0 MB")])
def test_format_size(value, expected):
    assert format_size(value) == expected
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_formats.py tests/unit/test_sizes.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

- `sizes.format_size`: copy the loop from `HistoryEntry.format_size`; make
  `HistoryEntry.format_size` return `format_size(self.file_size_bytes)`.
- `parse_formats`: iterate `payload.get("formats")`, `isinstance(list)` guard,
  require a non-empty `format_id`, coerce with `int(float(x))` guarded by
  `try/except (TypeError, ValueError)`, `filesize = filesize or filesize_approx or 0`.
- `estimate_size`: audio → bitrate from the quality string
  (`int(quality.removesuffix("kbps"))`, `best` → max `abr`), bytes =
  `duration * bitrate * 1000 // 8`; video → target height from
  `{"360p": 360, "480p": 480, "720p": 720, "1080p": 1080}`, pick candidates with
  `0 < height <= target`, prefer the largest `height`, then the largest
  `filesize`; if none has a size, use `tbr * 1000 / 8 * duration`.

- [ ] **Step 4: Run and commit**

Run: `.venv/bin/python -m pytest tests/unit/test_formats.py tests/unit/test_sizes.py tests/unit/test_models.py -q`
Commit `feat: parse yt-dlp formats and estimate download size`.

---

### Task 5: Fetch formats through the adapter and the service

**Files:**
- Modify: `src/youmudow/adapters/ytdlp_args.py` (new builder)
- Modify: `src/youmudow/adapters/ytdlp_adapter.py` (new method, after `get_metadata`)
- Modify: `src/youmudow/services/search_service.py` (protocol + method)
- Test: `tests/unit/test_ytdlp_args.py` if it exists, else `tests/unit/test_ytdlp_adapter.py`, `tests/unit/test_search_service.py`

**Interfaces:**
- Produces:
  - `ytdlp_args.build_formats_args(config: YtdlpConfig, url: str, log: Callable[[str], None] | None = None) -> list[str]`.
  - `YtdlpAdapter.get_formats(url: str) -> list[FormatInfo]`.
  - `SearchService.get_formats(url: str) -> list[FormatInfo]` and the same in
    `YtdlpAdapterProtocol`.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_formats_args_dumps_a_single_json(monkeypatch):
    monkeypatch.setattr(ytdlp_args, "_has_explicit_profile", lambda profile: False)
    args = build_formats_args(YtdlpConfig(output_template="{title}"), "https://x.test/v")
    assert args[-4:] == ["--dump-single-json", "--no-playlist", "--skip-download", "https://x.test/v"]


def test_get_formats_parses_the_payload(monkeypatch):
    adapter = YtdlpAdapter(YtdlpConfig())
    monkeypatch.setattr(
        "youmudow.adapters.ytdlp_adapter.run_capture",
        lambda args, timeout: CompletedProcess(args, 0, '{"formats":[{"format_id":"251","abr":160}]}', ""),
    )
    assert [f.format_id for f in adapter.get_formats("https://x.test/v")] == ["251"]


def test_get_formats_returns_empty_on_bad_json(monkeypatch):
    ...  # returncode 0 with stdout "not json"
    assert adapter.get_formats("https://x.test/v") == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_ytdlp_adapter.py -q -k formats`
Expected: FAIL — `build_formats_args` / `get_formats` missing.

- [ ] **Step 3: Implement**

`build_formats_args` = `build_base_args(config, None, False, log)` +
`["--dump-single-json", "--no-playlist", "--skip-download", url]`.
`get_formats` mirrors `get_metadata`'s error handling, catches
`json.JSONDecodeError`/`ValueError`, logs `[FORMATS] ...`, returns `[]`.
`SearchService.get_formats` delegates, with the protocol updated.

- [ ] **Step 4: Run and commit**

Run: `.venv/bin/python -m pytest tests/unit -q`
Commit `feat: expose a formats lookup through the adapter and search service`.

---

### Task 6: Show duration and estimated size in the detail panel

**Files:**
- Modify: `src/youmudow/ui/widgets/detail_panel.py:70-115` (info rows), `:227-232` (`update_detail_panel`)
- Modify: `src/youmudow/app/controller.py` (new `on_formats_ready`, `load_formats`)
- Modify: `src/youmudow/ui/window.py:440-460` (`_on_result_select`), callback setup
- Test: `tests/unit/test_detail_panel.py` (create if absent), `tests/unit/test_controller.py`, `tests/integration/test_search_flow.py`

**Interfaces:**
- Produces:
  - `DetailPanel.update_detail_panel(video)` renders a meta line
    `"{duration} · ~{size}"` (duration `"-"` when unknown, size segment omitted
    when unknown).
  - `DetailPanel.set_estimate(size_bytes: int | None) -> None`.
  - `AppController.load_formats(video: Video) -> None` (background thread) and
    `AppController.on_formats_ready(callback: Callable[[Video, int | None], None]) -> None`.
- Consumes: `SearchService.get_formats`, `estimate_size`, `format_size`.

- [ ] **Step 1: Write the failing tests**

```python
def test_detail_panel_shows_duration_and_size():
    # build DetailPanel against the shared fake main window from tests/unit/test_options_panel.py
    panel.update_detail_panel(Video(title="T", url="u", duration=125))
    assert panel._detail_meta.cget("text") == "2:05"
    panel.set_estimate(5 * 1024**2)
    assert panel._detail_meta.cget("text") == "2:05 · ~5.0 MB"


def test_controller_reports_the_estimate_for_the_requested_options():
    service = Mock()
    service.get_formats.return_value = [FormatInfo("251", "m4a", 0, 256.0, 0.0, 0)]
    controller = AppController(search_service=service, download_service=Mock())
    got = []
    controller.on_formats_ready(lambda video, size: got.append((video, size)))
    video = Video(title="T", url="u", duration=60, options=DownloadOptions(file_format="mp3", quality="best"))
    controller.load_formats(video)
    _wait_until(lambda: got)
    assert got[0][1] == 60 * 256_000 // 8
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit -q -k "detail_panel or formats_ready"`
Expected: FAIL — no `_detail_meta`, no `set_estimate`, no `load_formats`.

- [ ] **Step 3: Implement**

- `DetailPanel`: add `self._detail_meta = tk.Label(...)` right under the
  uploader, styled with `FONT["small"]` and the muted colour; keep
  `self._estimate_bytes: int | None = None`; a `_render_meta()` helper used by
  both `update_detail_panel` and `set_estimate`.
- `AppController.load_formats`: capture `video.url` and the estimate inputs
  (options are read from the video), run `self._search_service.get_formats(url)`
  in a `threading.Thread(daemon=True)`, compute `estimate_size(formats, video.options, video.duration)`,
  schedule `callback(video, size)` for each registered callback, swallowing
  exceptions with a log line.
- `MainWindow`: register `self._controller.on_formats_ready(self._on_formats_ready)`
  in `_setup_controller_callbacks`; `_on_formats_ready(video, size)` ignores
  the result unless `video is self._selected_video`, then calls
  `detail_panel.set_estimate(size)` through `_schedule`. In `_on_result_select`
  call `self._controller.load_formats(selected[0])` after
  `update_detail_panel`.

- [ ] **Step 4: Run the unit tests and the integration suite**

Run: `.venv/bin/python -m pytest tests/unit -q` then
`xvfb-run -a .venv/bin/python -m pytest tests/integration -q`
Expected: all pass; the search-flow test still passes with the extra callback.

- [ ] **Step 5: Commit**

Commit `feat: preview duration and estimated size in the detail panel`.

---

### Task 7: Download presets

**Files:**
- Create: `src/youmudow/domain/presets.py`
- Modify: `src/youmudow/ui/widgets/options_panel.py:250-290` (rows), `:355-370` (`get_options`)
- Test: `tests/unit/test_presets.py`, `tests/unit/test_options_panel.py`

**Interfaces:**
- Produces:
  - `presets.Preset` frozen dataclass `(name: str, options: DownloadOptions)`.
  - `presets.PRESETS: tuple[Preset, ...]` with exactly
    `"Music 320"` (mp3/320kbps), `"Video 1080"` (mp4/1080p),
    `"Archive FLAC"` (flac/best).
  - `presets.find_preset(name: str) -> Preset | None`.
  - `OptionsPanel.apply_preset(name: str) -> None` and a readonly
    `ttk.Combobox` labelled `Preset` whose values are
    `["Custom", "Music 320", "Video 1080", "Archive FLAC"]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_presets_are_valid():
    for preset in PRESETS:
        assert is_valid_format(preset.options.file_format)
        assert is_valid_quality(preset.options.quality)


def test_find_preset():
    assert find_preset("Music 320").options.quality == "320kbps"
    assert find_preset("nope") is None


def test_applying_a_preset_updates_the_controls(panel):
    panel.apply_preset("Video 1080")
    assert panel._format_var.get() == "mp4"
    assert panel._quality_var.get() == "1080p"
    assert panel._preset_var.get() == "Video 1080"


def test_applying_a_preset_keeps_cookie_settings(panel):
    panel._use_cookies_var.set(True)
    panel.apply_preset("Archive FLAC")
    assert panel._use_cookies_var.get() is True
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_presets.py tests/unit/test_options_panel.py -q -k preset`
Expected: FAIL — no module `youmudow.domain.presets`.

- [ ] **Step 3: Implement**

`presets.py` holds the data and the lookup. In the options panel, add the
combobox as the first row of the download-options group; `apply_preset` sets
`_format_var`, `_quality_var`, `_subtitles_var=False`, `_embed_subs_var=False`,
`_split_chapters_var=False`, calls `_on_subtitles_toggle()` and sets
`_preset_var` to the preset name. Bind `<<ComboboxSelected>>` on the format and
quality comboboxes to `lambda _event: self._preset_var.set("Custom")` so a
manual edit is reflected. Cookies, output path and rate limit are never touched.

- [ ] **Step 4: Run, then gates and commit**

```bash
.venv/bin/python -m pytest tests/ -q
ruff format src/ tests/ && ruff check src/ tests/ && .venv/bin/python -m mypy
PYTHONPATH=src .venv/bin/python scripts/smoke_boot.py
git add -A && git commit -m "feat: add download presets to the options panel"
```

---

## Self-review notes

- Spec coverage: playlist/channel row (Tasks 1–3), preview row (Tasks 4–6),
  presets row (Task 7). Subtitles/chapters are explicitly untouched.
- `estimate_size` returns `int | None` everywhere, so the UI has one rule:
  `None` means "omit the size".
- The controller reads options from the `Video` it is given, which is the same
  object the detail panel mutates, so the estimate matches the current
  selection without extra plumbing.
