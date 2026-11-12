# YouMuDow Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize YouMuDow's UI and streamline its code without losing any functionality, on the `feature/modernize-optimize` branch.

**Architecture:** Keep the existing layered architecture (domain → adapters → services → app → ui). Unify the three theming mechanisms into one, introduce a small canvas-based component library, replace the results table with a thumbnail card list, add an async thumbnail pipeline with disk cache, and de-duplicate persistence/thumbnail code.

**Tech Stack:** Python ≥3.10, Tkinter (ttk + canvas), Pillow, yt-dlp. No new runtime dependencies. Tests: pytest + pytest-cov; lint: ruff (line 100); types: mypy.

**Spec:** `docs/superpowers/specs/2026-11-12-modernize-design.md`

## Global Constraints

- No new runtime dependencies (only `yt-dlp` and `Pillow` stay).
- Preserve every existing feature, flow, shortcut, menu entry and download option.
- Persistence files (`config.json`, `history.json`) keep their format and location; read/write stays compatible.
- `ruff check` and `ruff format --check` and `mypy` and `pytest` must all be green at the end of every task.
- Coverage must not fall below the current 87 %.
- GUI tests run against the real X display (`DISPLAY=:0`); follow the existing root-fixture pattern in `tests/unit/`.
- FONT tokens must keep every existing key (`h1 h2 h3 body small label mono`) so existing references don't break.
- `youmudow.ui.*` stays ignored by mypy (`ignore_errors` already configured).

## Review Focus

The five failure modes most likely to bite a real user, each pinned by a test in the owning task:

1. **Theme toggle in light mode leaves stale dark colors** on some widget. → Task 2 test: `apply_theme` with `LIGHT_COLORS` then `DARK_COLORS` repaints both a `tk.Button` and a `ttk` style, and a `tk.Button`'s `bg` matches the current theme.
2. **Thumbnail cache grows without bound.** → Task 8 test: inserting `max_entries + 10` entries evicts the oldest and keeps ≤ `max_entries`.
3. **A stale thumbnail overwrites a newer selection** (out-of-order fetch). → Task 9 test: two `request()` calls; the first resolves after the second; only the second's `on_ready` is delivered.
4. **Keyboard navigation on the results list fires download with no selection.** → Task 10 test: `Enter` with no selected card invokes no command; `Down`/`Up` moves selection within bounds.
5. **A crash during save corrupts config/history.** → Task 13 test: `write_atomic` leaves no `.tmp` file and the original content intact when the write raises, and `backup_corrupt` renames to `.corrupt`.

---

### Task 0: Baseline and verification harness

**Files:**
- Create: `scripts/measure_startup.py`
- Create: `scripts/smoke_boot.py`
- Modify: `CHANGELOG.md` (add "Unreleased" modernization entry)

**Interfaces:**
- Produces: `scripts/smoke_boot.py` builds `MainWindow` headlessly on X and exits 0; `scripts/measure_startup.py` prints wall-clock time to build `MainWindow`.

- [ ] **Step 1: Write the smoke script**

`scripts/smoke_boot.py` constructs `AppConfig`, `AppController`, `MainWindow(controller, debug_mode=False, config=config)`, pumps `update()`, toggles theme once, then destroys the root and prints `BOOT OK`.

- [ ] **Step 2: Write the startup timer**

`scripts/measure_startup.py` times `AppConfig()` + `AppController(config)` + `MainWindow(...)` construction with `time.perf_counter()` and prints milliseconds.

- [ ] **Step 3: Run both and record the baseline**

Run: `PYTHONPATH=src python3 scripts/smoke_boot.py` and `PYTHONPATH=src python3 scripts/measure_startup.py`
Expected: `BOOT OK` exit 0; a startup time in ms is printed. Record the time in the task notes for the Phase 6 comparison.

- [ ] **Step 4: Run full suite and record coverage baseline**

Run: `PYTHONPATH=src python3 -m pytest --cov=src/youmudow -q | tail -3`
Expected: all green; note the coverage % and test count.

- [ ] **Step 5: Commit**

```bash
git add scripts/ CHANGELOG.md
git commit -m "chore: baseline smoke and startup measurement scripts"
```

---

### Task 1: Design tokens — larger, explicit type scale

**Files:**
- Modify: `src/youmudow/ui/styles/constants.py` (FONT dict, lines 29-37)
- Test: `tests/unit/test_tokens.py`

**Interfaces:**
- Produces: `FONT` dict with keys `display h1 h2 h3 body small label mono`; `SPACING` unchanged.

- [ ] **Step 1: Write the failing test**

```python
def test_type_scale_sizes():
    assert FONT["display"][1] == 18
    assert FONT["h1"][1] == 15
    assert FONT["h2"][1] == 13
    assert FONT["h3"][1] == 12
    assert FONT["body"][1] == 11
    assert FONT["small"][1] == 10
    assert FONT["label"][1] == 10

def test_type_scale_keys_preserved():
    assert {"h1","h2","h3","body","small","label","mono"} <= set(FONT)
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_tokens.py -v`
Expected: FAIL (current sizes are 14/12/11/10/9/9).

- [ ] **Step 3: Implement the new `FONT` values**

Replace the `FONT` dict values: `display` (`_SANS`, 18, "bold"), `h1` (`_SANS`, 15, "bold"), `h2` (`_SANS`, 13, "bold"), `h3` (`_SANS`, 12, "bold"), `body` (`_SANS`, 11), `small` (`_SANS`, 10), `label` (`_SANS`, 10, "bold"), `mono` (`_MONO`, 10).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_tokens.py -v && PYTHONPATH=src python3 -m pytest -q`
Expected: PASS; full suite still green (existing UI tests may assert old sizes — update only those assertions to the new scale if they exist).

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/styles/constants.py tests/unit/test_tokens.py
git commit -m "feat(ui): larger explicit type scale"
```

---

### Task 2: Single theme system

**Files:**
- Modify: `src/youmudow/ui/styles/styles.py` (add `apply_theme`, absorb Treeview styling)
- Modify: `src/youmudow/ui/widgets/results_table.py` (delete `_style_treeview` and its call)
- Modify: `src/youmudow/ui/window.py` (`__init__` and `_on_toggle_theme` use `apply_theme`)
- Test: `tests/unit/test_theme_apply.py`

**Interfaces:**
- Consumes: `Colors`, `StyleManager.configure_styles`, `theme_apply.apply_theme_colors`.
- Produces: `apply_theme(root: tk.Misc, colors: Colors) -> None` in `styles.py`; `Modern.Treeview` and `Modern.Treeview.Heading` styled by `StyleManager`.

- [ ] **Step 1: Write the failing tests**

```python
def test_apply_theme_paints_ttk_and_tk(root):
    apply_theme(root, LIGHT_COLORS)
    btn = tk.Button(root); btn.pack()
    apply_theme(root, DARK_COLORS)
    assert btn.cget("bg").lower() == DARK_COLORS.background.lower()

def test_treeview_styled_by_manager():
    mgr = StyleManager(); mgr.configure(DARK_COLORS)
    assert mgr.style.lookup("Modern.Treeview", "background")
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_theme_apply.py -v`
Expected: FAIL (`apply_theme` undefined).

- [ ] **Step 3: Implement `apply_theme` and absorb Treeview style**

In `styles.py`, add `apply_theme(root, colors)` that calls `configure_styles(colors)` then `apply_theme_colors(root, colors)`. Move the `Modern.Treeview` + heading configuration from `results_table._style_treeview` into `StyleManager.configure`. Delete `_style_treeview` from `results_table.py` and replace both `configure_styles(...)` calls in `window.py` with `apply_theme(...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_theme_apply.py -v && PYTHONPATH=src python3 -m pytest -q`
Expected: PASS; smoke boot still `BOOT OK`.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/styles/styles.py src/youmudow/ui/widgets/results_table.py src/youmudow/ui/window.py tests/unit/test_theme_apply.py
git commit -m "refactor(ui): unify theming into single apply_theme"
```

---

### Task 3: `RoundedButton` component

**Files:**
- Create: `src/youmudow/ui/widgets/components/__init__.py`
- Create: `src/youmudow/ui/widgets/components/rounded_button.py`
- Test: `tests/unit/test_rounded_button.py`

**Interfaces:**
- Consumes: `_c` color resolver, `FONT`.
- Produces: `RoundedButton(tk.Canvas)` with `__init__(master, text, *, command=None, variant="primary", width=None, height=34, font=None)`, `set_text(text)`, `set_enabled(enabled)`, `invoke()`. Variants: `primary secondary danger ghost`.

- [ ] **Step 1: Write the failing tests**

```python
def test_button_invokes_command(root):
    calls = []
    b = RoundedButton(root, "Go", command=lambda: calls.append(1))
    b.invoke()
    assert calls == [1]

def test_button_disable_blocks_command(root):
    calls = []
    b = RoundedButton(root, "Go", command=lambda: calls.append(1))
    b.set_enabled(False)
    b.invoke()
    assert calls == []

def test_button_set_text(root):
    b = RoundedButton(root, "A"); b.set_text("B")
    assert b._label_text == "B"
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_rounded_button.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `RoundedButton`**

A `tk.Canvas` drawing a rounded rectangle (radius 8) filled by variant color (primary/secondary/danger/ghost from `_c`), with centered text via `create_text`. Bind `<Button-1>` to `invoke`, `<Enter>`/`<Leave>` for hover fill. Disabled state grays fill and ignores clicks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_rounded_button.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/components/
git commit -m "feat(ui): add RoundedButton canvas component"
```

---

### Task 4: `Card` component

**Files:**
- Create: `src/youmudow/ui/widgets/components/card.py`
- Test: `tests/unit/test_card.py`

**Interfaces:**
- Consumes: `_c`, `SPACING`.
- Produces: `Card(tk.Frame)` with `__init__(master, *, padding=SPACING["md"], **kwargs)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_card_background_is_surface(root):
    c = Card(root)
    assert c.cget("background").lower() == _c("surface").lower()

def test_card_padding_default(root):
    assert Card(root) is not None
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_card.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `Card`**

A `tk.Frame` with `background=_c("surface")`, a subtle 1px `highlightbackground=_c("border")` border, and internal `padx/pady=padding`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_card.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/components/card.py tests/unit/test_card.py
git commit -m "feat(ui): add Card component"
```

---

### Task 5: `SearchEntry` component

**Files:**
- Create: `src/youmudow/ui/widgets/components/search_entry.py`
- Test: `tests/unit/test_search_entry.py`

**Interfaces:**
- Consumes: `_c`, `FONT`.
- Produces: `SearchEntry(tk.Frame)` with `__init__(master, *, placeholder="", textvariable=None, command=None)`, `get() -> str`, `set(value)`, `clear()`, `focus_set()`. Shows placeholder when empty; binds `<Return>` to `command`.

- [ ] **Step 1: Write the failing tests**

```python
def test_placeholder_shown_when_empty(root):
    e = SearchEntry(root, placeholder="Search…")
    assert e.get() == ""

def test_return_fires_command(root):
    calls = []
    e = SearchEntry(root, command=lambda: calls.append(1))
    e.event_generate("<Return>")
    assert calls == [1]

def test_set_and_clear(root):
    e = SearchEntry(root); e.set("abc"); assert e.get() == "abc"
    e.clear(); assert e.get() == ""
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_search_entry.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `SearchEntry`**

A `tk.Frame` wrapping a `tk.Entry`; placeholder drawn in gray when the var is empty and cleared on focus; a focus ring via border color on `<FocusIn>`/`<FocusOut>`. `get()` returns the real text (empty when only placeholder is shown).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_search_entry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/components/search_entry.py tests/unit/test_search_entry.py
git commit -m "feat(ui): add SearchEntry component"
```

---

### Task 6: `Spinner` component

**Files:**
- Create: `src/youmudow/ui/widgets/components/spinner.py`
- Test: `tests/unit/test_spinner.py`

**Interfaces:**
- Consumes: `_c`.
- Produces: `Spinner(tk.Canvas)` with `__init__(master, *, size=16, color=None)`, `start()`, `stop()`, `is_running() -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
def test_spinner_start_stop(root):
    s = Spinner(root)
    assert not s.is_running()
    s.start(); assert s.is_running()
    s.stop(); assert not s.is_running()
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_spinner.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `Spinner`**

A `tk.Canvas` drawing a partial arc; `start()` begins an `after()` animation loop, `stop()` cancels it. Color defaults to `_c("primary")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_spinner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/components/spinner.py tests/unit/test_spinner.py
git commit -m "feat(ui): add Spinner component"
```

---

### Task 7: `EmptyState` component

**Files:**
- Create: `src/youmudow/ui/widgets/components/empty_state.py`
- Test: `tests/unit/test_empty_state.py`

**Interfaces:**
- Consumes: `_c`, `FONT`, `RoundedButton`.
- Produces: `EmptyState(tk.Frame)` with `__init__(master, *, icon="", message="", action_text=None, action_command=None)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_empty_state_message_and_action(root):
    calls = []
    e = EmptyState(root, message="No results", action_text="Retry", action_command=lambda: calls.append(1))
    e._action_button.invoke()
    assert calls == [1]
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_empty_state.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `EmptyState`**

A centered `tk.Frame` with an icon label, a message label (`FONT["body"]`, `_c("text_secondary")`), and an optional `RoundedButton` (secondary) for the action.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_empty_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/components/empty_state.py tests/unit/test_empty_state.py
git commit -m "feat(ui): add EmptyState component"
```

---

### Task 8: `cache_dir` + `ThumbnailCache`

**Files:**
- Modify: `src/youmudow/paths.py` (add `cache_dir`)
- Create: `src/youmudow/services/thumbnail_cache.py`
- Test: `tests/unit/test_thumbnail_cache.py`, `tests/unit/test_paths.py` (extend)

**Interfaces:**
- Produces: `cache_dir() -> Path` (`~/.cache/youmudow` on Linux/macOS honoring `XDG_CACHE_HOME`, `%LOCALAPPDATA%/YouMuDow/cache` on Windows). `ThumbnailCache` with `__init__(cache_dir: Path, max_entries: int = 200)`, `get(video_id: str) -> bytes | None`, `put(video_id: str, data: bytes) -> None`, `get_path(video_id: str) -> Path`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cache_roundtrip(tmp_path):
    c = ThumbnailCache(tmp_path)
    c.put("abc12345678", b"data")
    assert c.get("abc12345678") == b"data"

def test_cache_miss_returns_none(tmp_path):
    assert ThumbnailCache(tmp_path).get("missing") is None

def test_lru_eviction(tmp_path):
    c = ThumbnailCache(tmp_path, max_entries=3)
    for i in range(6):
        c.put(f"vid{i}", bytes([i]))
    assert len(list(tmp_path.glob("*.jpg"))) <= 3
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_thumbnail_cache.py tests/unit/test_paths.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `cache_dir()` and `ThumbnailCache`**

Add `cache_dir()` to `paths.py`. Implement `ThumbnailCache` writing bytes to `get_path(video_id)` (a `.jpg` file), an in-memory `OrderedDict` LRU for `max_entries`, and `get()` that checks memory then disk.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_thumbnail_cache.py tests/unit/test_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/paths.py src/youmudow/services/thumbnail_cache.py tests/unit/test_thumbnail_cache.py tests/unit/test_paths.py
git commit -m "feat: add thumbnail cache and cache_dir"
```

---

### Task 9: Async `ThumbnailLoader` + migrate detail panel

**Files:**
- Create: `src/youmudow/services/thumbnail_loader.py`
- Create: `src/youmudow/ui/widgets/components/thumbnail.py` (`photoimage_from_bytes`)
- Modify: `src/youmudow/ui/widgets/detail_panel.py` (`_load_thumbnail`)
- Test: `tests/unit/test_thumbnail_loader.py`

**Interfaces:**
- Consumes: `ThumbnailCache`, `ThumbnailService`, `cache_dir()`.
- Produces: `ThumbnailLoader` with `__init__(root: tk.Misc, cache: ThumbnailCache, service: ThumbnailService)`, `request(video_url: str, on_ready: Callable[[str, bytes | None], None]) -> None`, `shutdown() -> None`. `photoimage_from_bytes(data: bytes, width: int, height: int) -> ImageTk.PhotoImage | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_loader_uses_cache_when_present(root, tmp_path):
    cache = ThumbnailCache(tmp_path)
    cache.put("vid12345678", b"jpgdata")
    results = {}
    loader = ThumbnailLoader(root, cache, ThumbnailService())
    loader.request("https://youtu.be/vid12345678", lambda url, b: results.setdefault(url, b))
    root.update()  # let after() dispatch
    assert results["https://youtu.be/vid12345678"] == b"jpgdata"

def test_stale_request_does_not_overwrite(root, tmp_path):
    # first request resolves after second; only second's callback fires
    ...
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_thumbnail_loader.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `ThumbnailLoader` and `photoimage_from_bytes`**

`ThumbnailLoader` keeps a daemon thread draining a request queue: extract `video_id` via `service.extract_video_id`, serve from `cache`, else download via `urllib.request.urlopen`, `cache.put`, then schedule `on_ready(url, bytes)` on the main thread with `root.after`. Guard against stale results by tracking the latest `video_id` per request token. `photoimage_from_bytes` decodes with `PIL.Image`, `thumbnail(width, height)`, and returns `ImageTk.PhotoImage`. Migrate `detail_panel._load_thumbnail` to use the loader instead of its inline `urlopen`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_thumbnail_loader.py -v && PYTHONPATH=src python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/services/thumbnail_loader.py src/youmudow/ui/widgets/components/thumbnail.py src/youmudow/ui/widgets/detail_panel.py tests/unit/test_thumbnail_loader.py
git commit -m "feat: async thumbnail loader with disk cache"
```

---

### Task 10: `ResultsCards` replaces the results table

**Files:**
- Create: `src/youmudow/ui/widgets/results_cards.py`
- Modify: `src/youmudow/ui/window.py` (use `ResultsCards`, keep callbacks/state wiring)
- Delete: `src/youmudow/ui/widgets/results_table.py`
- Modify: `tests/unit/test_window_smoke.py` (adjust import)
- Test: `tests/unit/test_results_cards.py`

**Interfaces:**
- Consumes: `StateManager.get_search_results`, `ThumbnailLoader`, `ThumbnailService`, `Card`, `photoimage_from_bytes`, `get_theme_manager`.
- Produces: `ResultsCards(tk.Frame)` with `__init__(master, state, thumbnail_loader, *, on_select=None, on_double_click=None, on_open_in_browser=None)`, `update_results(videos: list[Video]) -> None`, `clear_results() -> None`, `get_selected() -> list[int]`, `is_playlist: bool`, `playlist_videos: list[Video]`. Preserves double-click → download, right-click → open in browser, and keyboard ↑/↓/`Enter`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cards_count(root):
    w = ResultsCards(root, state, loader)
    w.update_results([Video(...), Video(...), Video(...)])
    assert w.card_count() == 3

def test_selection_bounds_and_enter_noop(root):
    w = ResultsCards(root, state, loader)
    w.update_results([Video(...)])
    w.select(-1); w.select(5)  # clamp, no error
    assert w.get_selected() == [0]

def test_get_selected_returns_indices(root):
    w = ResultsCards(root, state, loader)
    w.update_results([Video(...), Video(...)])
    w.select(1)
    assert w.get_selected() == [1]
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_results_cards.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `ResultsCards`**

A scrollable canvas list of `Card`s, each with a thumbnail (`photoimage_from_bytes`, lazy-loaded via `ThumbnailLoader` as cards scroll into view) plus title/uploader/duration labels. Selection via click (single and Ctrl/Shift multi-select), `<Double-Button-1>` → `on_double_click`, `<Button-3>` menu → `on_open_in_browser`, and `Up`/`Down`/`Return` keyboard bindings. `get_selected()` returns indices into the current video list. Wire it into `window.py` replacing `ResultsTable` while keeping the existing state observer, download, and playlist flows.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_results_cards.py tests/unit/test_window_smoke.py -v && PYTHONPATH=src python3 -m pytest -q`
Expected: PASS; smoke boot `BOOT OK`.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/results_cards.py src/youmudow/ui/window.py tests/unit/
git rm src/youmudow/ui/widgets/results_table.py
git commit -m "feat(ui): replace results table with thumbnail cards"
```

---

### Task 11: Loading / empty / error states

**Files:**
- Modify: `src/youmudow/ui/widgets/results_cards.py` (empty state)
- Modify: `src/youmudow/ui/widgets/history_panel.py` (empty state)
- Modify: `src/youmudow/ui/widgets/queue_panel.py` (empty state)
- Modify: `src/youmudow/ui/widgets/search_bar.py` (spinner while searching)
- Test: `tests/unit/test_states.py`

**Interfaces:**
- Consumes: `EmptyState`, `Spinner`, `SearchEntry`.
- Produces: each list shows an `EmptyState` when empty; search bar shows a `Spinner` while `is_searching`.

- [ ] **Step 1: Write the failing tests**

```python
def test_empty_states_exposed(root):
    w = ResultsCards(root, state, loader); w.clear_results()
    assert w._empty_state is not None and w._empty_state.winfo_ismapped()

def test_spinner_runs_while_searching(root):
    bar = SearchBar(root, ...)
    bar.update_button_states(is_searching=True, is_downloading=False)
    assert bar._spinner.is_running()
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_states.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the states**

Show `EmptyState` ("Sin resultados", "Historial vacío", "Cola vacía") when each list is empty; drive a `Spinner` in the search bar from `update_button_states(is_searching=...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_states.py -v && PYTHONPATH=src python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/ tests/unit/test_states.py
git commit -m "feat(ui): loading, empty and error states"
```

---

### Task 12: Performance — lazy imports, startup, redundant work

**Files:**
- Modify: `src/youmudow/ui/widgets/components/thumbnail.py` and `detail_panel.py` (lazy `PIL`/`urllib` import)
- Modify: `src/youmudow/ui/widgets/options_panel.py` (memoize `get_available_browsers` per instance)
- Test: `tests/unit/test_perf.py`

**Interfaces:**
- Consumes: `measure_startup.py`.
- Produces: no behavioral change; startup time printed by `measure_startup.py` improves or stays within 10 % of baseline.

- [ ] **Step 1: Write the failing test**

```python
def test_browser_profiles_cached_per_instance(tmp_path):
    panel = OptionsPanel(parent, config, state)
    a = panel._browser_options()
    b = panel._browser_options()
    assert a == b  # no re-detect between calls
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_perf.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement lazy imports and memoization**

Move `from PIL import ...` and `import urllib.request` to inside the functions that use them (thumbnail loader / image decode). In `options_panel`, cache the `get_available_browsers()` result per instance. Re-run `measure_startup.py` and record the delta vs Task 0.

- [ ] **Step 4: Run tests and measure**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_perf.py -v && PYTHONPATH=src python3 scripts/measure_startup.py`
Expected: PASS; startup time recorded.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/ src/youmudow/services/ tests/unit/test_perf.py
git commit -m "perf: lazy imports and redundant-work removal"
```

---

### Task 13: Shared atomic persistence

**Files:**
- Create: `src/youmudow/services/persistence.py`
- Modify: `src/youmudow/app/config.py` (import instead of local copies)
- Modify: `src/youmudow/services/history_service.py` (import instead of local copies)
- Test: `tests/unit/test_persistence.py`

**Interfaces:**
- Consumes: the exact bodies currently in `config.py:46-75` and `history_service.py:20-48`.
- Produces: `write_atomic(path: Path, text: str) -> None`, `backup_corrupt(path: Path) -> Path | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_write_atomic_no_tmp_left(tmp_path):
    p = tmp_path / "f.json"; write_atomic(p, "{}")
    assert p.read_text() == "{}"
    assert list(tmp_path.glob("*.tmp")) == []

def test_write_atomic_keeps_original_on_failure(tmp_path, monkeypatch):
    p = tmp_path / "f.json"; p.write_text("orig")
    monkeypatch.setattr("os.replace", lambda a, b: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        write_atomic(p, "new")
    assert p.read_text() == "orig"

def test_backup_corrupt_renames(tmp_path):
    p = tmp_path / "f.json"; p.write_text("bad")
    b = backup_corrupt(p)
    assert b is not None and b.suffix == ".corrupt"
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_persistence.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `write_atomic`/`backup_corrupt` and de-duplicate**

Create `services/persistence.py` with the two functions; delete the local copies in `config.py` and `history_service.py` and import from the shared module (keep their `logger` usage via a module logger).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_persistence.py tests/unit/test_config.py tests/unit/test_history_service.py -v && PYTHONPATH=src python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/services/persistence.py src/youmudow/app/config.py src/youmudow/services/history_service.py tests/unit/test_persistence.py
git commit -m "refactor: share atomic persistence between config and history"
```

---

### Task 14: De-duplicate controller thumbnail loops

**Files:**
- Modify: `src/youmudow/app/controller.py` (`_perform_search`, `_perform_search_url`, `search_playlist`)
- Test: `tests/unit/test_controller.py` (extend)

**Interfaces:**
- Consumes: `ThumbnailService`.
- Produces: `_apply_thumbnail(video: Video) -> None` (private helper) setting `video.thumbnail` when empty and the URL is a YouTube URL.

- [ ] **Step 1: Write the failing test**

```python
def test_apply_thumbnail_sets_youtube_thumbnail():
    v = Video(title="t", url="https://youtu.be/abc12345678", ...)
    controller._apply_thumbnail(v)
    assert v.thumbnail == "https://img.youtube.com/vi/abc12345678/hqdefault.jpg"

def test_apply_thumbnail_skips_non_youtube():
    v = Video(title="t", url="https://soundcloud.com/x/y", ...)
    controller._apply_thumbnail(v)
    assert v.thumbnail == ""
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_controller.py -v`
Expected: FAIL (`_apply_thumbnail` undefined).

- [ ] **Step 3: Implement `_apply_thumbnail` and replace the 3 loops**

Extract the repeated `if not video.thumbnail and is_valid_youtube_url(video.url): video.thumbnail = ...` block into `_apply_thumbnail(video)` and call it from all three search methods.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_controller.py -v && PYTHONPATH=src python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/app/controller.py tests/unit/test_controller.py
git commit -m "refactor: single thumbnail-resolution helper in controller"
```

---

### Task 15: Data-driven options form + slim window

**Files:**
- Modify: `src/youmudow/ui/widgets/options_panel.py` (data-driven rows)
- Modify: `src/youmudow/ui/window.py` (extract theme + shortcut helpers)
- Test: `tests/unit/test_options_panel.py` (extend)

**Interfaces:**
- Consumes: `AppConfig`, `StateManager`, `RoundedButton`.
- Produces: a `_build_rows(specs) -> list[tk.Widget]` helper in `options_panel.py`; `window.py` gains `_bind_shortcuts()` and `_toggle_theme()`.

- [ ] **Step 1: Write the failing test**

```python
def test_options_rows_built_from_specs(root):
    panel = OptionsPanel(parent, config, state)
    assert panel._rows_count >= 6  # format, quality, concurrent, subtitles, auth, extra
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_options_panel.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the refactors**

Replace the hand-built form rows in `options_panel.py` with a small spec-driven builder (each row described as `(label, kind, var, choices/opts)`), preserving all fields, order, validation and save/load. Extract the keyboard bindings from `window.__init__` into `_bind_shortcuts()` and the theme toggle body into `_toggle_theme()` (already a method — move the duplicated logic from `__init__` into it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_options_panel.py -v && PYTHONPATH=src python3 -m pytest -q && PYTHONPATH=src python3 scripts/smoke_boot.py`
Expected: PASS + `BOOT OK`.

- [ ] **Step 5: Commit**

```bash
git add src/youmudow/ui/widgets/options_panel.py src/youmudow/ui/window.py tests/unit/test_options_panel.py
git commit -m "refactor(ui): data-driven options form and slimmer window"
```

---

### Task 16: Final validation and summary

**Files:**
- Modify: `CHANGELOG.md`, `docs/` (add the technical summary)
- Create: `docs/superpowers/2026-11-12-modernize-summary.md`

**Interfaces:**
- Consumes: all previous tasks.

- [ ] **Step 1: Full gate**

Run: `ruff check src/ tests/ && ruff format --check src/ tests/ && PYTHONPATH=src python3 -m mypy && PYTHONPATH=src python3 -m pytest --cov=src/youmudow -q`
Expected: all green; coverage ≥ 87 %.

- [ ] **Step 2: Smoke and startup comparison**

Run: `PYTHONPATH=src python3 scripts/smoke_boot.py && PYTHONPATH=src python3 scripts/measure_startup.py`
Expected: `BOOT OK`; startup vs Task 0 baseline noted.

- [ ] **Step 3: Manual UI check on X**

Launch the app once (`PYTHONPATH=src python3 -m youmudow`), verify search/history/queue, theme toggle in both directions, results cards selection + keyboard nav, and that no console errors appear.

- [ ] **Step 4: Write the technical summary**

Write `docs/superpowers/2026-11-12-modernize-summary.md` with the eight sections the user asked for: problems found, changes made, affected files/modules, performance optimizations, visual/UX improvements, refactors/simplifications, test results, open items/limitations.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md docs/
git commit -m "docs: modernization technical summary"
```

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-11-12-modernize-optimize.md`.
