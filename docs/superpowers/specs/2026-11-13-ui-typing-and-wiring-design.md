# UI Typing & Component Wiring — Design

**Date:** 2026-11-13
**Status:** approved by the user ("si a+b1")
**Branch:** `feature/ui-typing-and-wiring` (from `main` at v1.3.0)

## Intent

The modernization work (PR #34, v1.3.0) shipped a component library
(`SearchEntry`, `RoundedButton`, `Card`, `Spinner`, `EmptyState`) but never wired
two of them into the real UI, and left the entire `youmudow.ui.*` package
exempt from mypy via `ignore_errors = true`. The result is a codebase that
*looks* type-checked but is not: the escape hatch hides 183 real type errors,
and two finished components sit unused in `src/`.

The user asked to "do the recommendation" — which was: (1) make the CI real,
(4) wire `SearchEntry` + `RoundedButton` for real, (10) remove the mypy
`ignore_errors` escape hatch. After investigation, (1) turned out to be already
fixed (the CI failure was a flaky Tk test, fixed in `3d46657`), so the work is
(4) + (10), done properly rather than quickly.

## What we found

### The CI was not broken — a test was

`.github/workflows/ci.yml` already has the right four jobs: `lint`, `typecheck`,
`test` (matrix 3.10/3.11/3.12 under `xvfb-run`), and `build`. The red CI run
came from `test_search_entry.py::test_return_fires_command`, which used
`event_generate('<Return>')` — unreliable under headless X, where the window
never receives keyboard focus. That test was rewritten in `3d46657` to call the
handler directly and assert the binding. **No CI config change is needed.**

### The mypy escape hatch hides 183 errors

Measured with `ignore_errors = false` for `youmudow.ui.*`:

| File | Errors | Dominant cause |
|---|---|---|
| `ui/window.py` | 40 | 38 `union-attr` on `X \| None` attributes + 2 `arg-type` |
| `ui/styles/theme_apply.py` | 32 | 25 `call-arg` — `configure(bg=…)` on `tk.Misc` |
| `ui/widgets/detail_panel.py` | 32 | 23 `attr-defined` on `self._mw._x` + 9 `arg-type` |
| `ui/widgets/options_panel.py` | 18 | 10 `attr-defined`, 6 `arg-type`, 2 `call-overload` |
| `ui/widgets/search_bar.py` | 16 | 12 `attr-defined`, 4 `arg-type` |
| `ui/widgets/results_cards.py` | 12 | mixed |
| `ui/widgets/components/rounded_button.py` | 8 | `command: object` not callable, font tuples |
| `ui/widgets/queue_panel.py` | 7 | `attr-defined` |
| `ui/widgets/history_panel.py` | 7 | `attr-defined` |
| `ui/styles/constants.py` | 4 | `_c()` with non-literal keys |
| `ui/widgets/status_bar.py` | 3 | `attr-defined` |
| `ui/widgets/log_terminal.py` | 2 | misc |
| `ui/widgets/components/empty_state.py` | 2 | misc |
| `ui/widgets/components/thumbnail.py` | 1 | `import-untyped` (Pillow) |
| `ui/widgets/components/search_entry.py` | 1 | misc |
| `ui/styles/styles.py` | 1 | misc |

Error codes overall: 61 `attr-defined`, 41 `arg-type`, 38 `union-attr`,
31 `call-arg`, 3 `call-overload`, 3 `operator`, 4 `misc`, 1 `import-untyped`,
1 `no-any-return`.

**Root causes — there are exactly three, not 183:**

1. **Widgets typed `main_window: object`.** Every `self._mw._on_search()` is an
   `attr-defined` error. This alone accounts for ~90 errors.
2. **`widget.configure(**kwargs)` on `tk.Misc`.** Tkinter's `configure` is typed
   as `configure(cnf: Any = ..., **kwargs: Any)`, but mypy rejects `bg=` and
   `fg=` as unexpected keyword arguments for `Misc`. ~31 errors.
3. **`FONT` inferred too widely.** `FONT` is `dict[str, tuple[str, int, str] |
   tuple[str, int]]`; Tk's `font=` parameter wants `str | Font | list[Any] |
   tuple[str] | tuple[str, int, *tuple[str, ...]] | ...`. The `tuple[str, int]`
   member does not match. ~20 errors.

The remaining `union-attr` errors in `window.py` are genuine: attributes like
`self._status_bar` are declared `StatusBar | None` but used unconditionally
inside handlers.

### The search bar still uses hand-rolled widgets

`src/youmudow/ui/widgets/search_bar.py` (190 lines) uses a `ttk.Combobox` with
a **fake placeholder**: the placeholder string is written into the entry as if
it were a value, and `get_query()` compares against it to decide if the field
is empty. Three `tk.Button`s are built by hand, each with its own `_theme`
dict and `add_hover_effect` call. `SearchEntry` — which implements a *real*
placeholder — and `RoundedButton` are unused.

## Approaches considered

### For the mypy escape hatch

**A — Type the UI layer properly (chosen).** Introduce a `MainWindowProtocol`
declaring the members the widgets actually use, a typed helper module for
Tkinter's dynamic surface (`configure_widget`, `setattr_any`, `FontSpec`), and
narrow the `FONT` annotation. Then remove the override entirely.

- *Why*: it removes the three root causes rather than the 183 symptoms, and
  the typecheck becomes a real guarantee instead of a boolean. It also aligns
  with Task 5, which rewrites `search_bar.py` anyway — better to write the new
  code typed from the start than to retrofit it.
- *Cost*: the largest task in the plan. `window.py`'s 38 `union-attr` errors
  need honest narrowing, not `# type: ignore`.
- *Rejected*: adding per-module overrides (`youmudow.ui.widgets.*`) instead of
  `youmudow.ui.*` — that just moves the escape hatch and keeps the lie.

**B — Partial unblocking.** Remove the override only from the modules that are
already clean (`components/`, `styles/`) and keep it for the legacy widgets.
- *Why not*: fast, but `main_window: object` remains, and the `typecheck` CI
  job stays decorative for the part of the UI users actually touch.

### For the search history dropdown

`SearchEntry` is a plain `tk.Entry`; the current `ttk.Combobox` provides a
dropdown of past searches. Replacing the combo naively would **delete a
feature**, which the user explicitly forbade.

**B1 — Extend `SearchEntry` with a history dropdown (chosen).** A lazily
created `tk.Listbox` placed below the entry, opened with `<Down>`, populated
from `set_history()`, with click/`<Return>` selection.
- *Why*: the dropdown is the reason the combobox exists; keeping it in the
  component means the component is actually complete and reusable.
- *Cost*: ~60 lines in `search_entry.py` plus tests.

**B2 — Keep a separate combobox beside `SearchEntry`.**
- *Why not*: two overlapping inputs in one row; the user would have to learn
  which one takes the text.

**B3 — Chips or a side list.**
- *Why not*: more UI surface than the current behaviour warrants.

### For the RoundedButton theme staleness

`RoundedButton` caches `_fill_color` / `_text_color` in `_update_colors()`,
which runs only at construction, on hover, and on `set_enabled`. A theme toggle
therefore leaves the buttons in the old palette. This was deferred minor F4
from the previous review — but it becomes user-visible the moment these
buttons are actually on screen.

**Chosen:** resolve the colours at draw time (`_draw()` calls
`_update_colors()`), so every repaint re-reads the palette. No caching, no
staleness, and the code is shorter.

## The design

### 1. `src/youmudow/ui/typed.py` — the typed Tkinter surface

Three helpers, each with one job:

- `configure_widget(widget: tk.Misc, **options: str) -> None` — the single
  checked entry point for `configure()`, swallowing `tk.TclError`.
- `setattr_any(obj: object, name: str, value: object) -> None` — sets dynamic
  attributes (`_bg_key`, `_border_key`, `_theme`) without `attr-defined` errors.
- `FontSpec = tuple[str, int] | tuple[str, int, str]` — the narrow type Tk
  accepts for `font=`, used to annotate `FONT`.

### 2. `src/youmudow/ui/protocols.py` — the widget/main-window contract

`MainWindowProtocol` declares exactly the members the widgets use (verified by
grep, not guessed):

- attributes: `_root`, `_controller`, `_selected_video`, `_results_cards`,
  `_search_bar`, `_notebook`, `_main_content_frame`
- methods: `_on_search`, `_on_cancel_search`, `_on_cancel_download`,
  `_on_download_now`, `_on_open_folder`, `_set_status`

`AppControllerProtocol` declares `state`, `history`, `enqueue`,
`enqueue_multiple`, `remove_from_queue`, `clear_queue`, `start_downloads`,
`stop_downloads`.

`ResultsCardsLike` and `SearchBarLike` are minimal Protocols declared *inside*
`protocols.py` (not imports of the widget classes) so there is no import cycle:
`ui/__init__.py` imports `window.py`, which imports the widgets, which would
import `protocols.py`.

Widgets change `main_window: object` → `main_window: MainWindowProtocol`.

### 3. Removing the override

`pyproject.toml` loses the `[[tool.mypy.overrides]]` block for `youmudow.ui.*`
entirely — not narrowed, removed. The three root causes are fixed at source:

- `configure(**kwargs)` → `configure_widget(widget, **kwargs)`.
- `FONT: dict[str, FontSpec]` so `font=FONT["body"]` type-checks.
- `main_window: MainWindowProtocol` so `self._mw._on_search()` type-checks.

`window.py`'s Optional attributes get honest local narrowing
(`status_bar = self._status_bar; if status_bar is not None: ...`), never
`# type: ignore`.

### 4. `SearchEntry` with history

New surface: `set_history(history)`, `open_history()`, `close_history()`,
`history_is_open()`. `<Down>` opens the dropdown; it does nothing when the
history is empty. Selecting an item sets the field and fires the command.
`clear()` closes the dropdown.

### 5. `SearchBar` rewired

- `ttk.Combobox` → `SearchEntry` (real placeholder; the fake-placeholder hack
  and `get_query()`'s placeholder comparison are deleted).
- Three hand-rolled `tk.Button`s → three `RoundedButton`s
  (`primary`, `secondary`, `danger`).
- `update_history()` → `SearchEntry.set_history()`.
- `update_button_states()` → `RoundedButton.set_enabled()`.
- `search_entry` property now returns the `SearchEntry` — `window.py`'s Ctrl+L
  shortcut keeps working unchanged, because `SearchEntry.focus_set()` already
  exists.
- All keyboard bindings preserved: `<Return>`, `<Control-Return>`,
  `<Control-v>`/`<Control-V>`, `<Control-a>`/`<Control-A>`,
  `<Control-BackSpace>`, plus the new `<Down>`.

### 6. `RoundedButton` repaints on theme change

`_draw()` calls `_update_colors()` first, so colours are resolved at draw time
rather than cached. Fixes deferred minor F4 as a side effect of the button
becoming user-visible.

## Goals / non-goals / anti-goals

**Goals**
- `PYTHONPATH=src python3 -m mypy` passes on `src/youmudow` with no UI override.
- `SearchEntry` and `RoundedButton` are the widgets the search bar actually uses.
- The search-history dropdown, every shortcut, the spinner, the clipboard
  auto-paste and the per-button disabled states all still work.
- The CI `typecheck` job is meaningful.

**Non-goals**
- Not a visual redesign — the modernization work already did that.
- Not a rewrite of `window.py`'s structure.
- No new runtime dependencies.

**Anti-goals**
- No `# type: ignore` sprinkles to make mypy quiet.
- No narrowed override replacing the broad one (that is the same lie, smaller).
- No feature loss to make the code simpler (the dropdown is the trap here).

## Constraints

- Python ≥ 3.10 (`X | None` syntax, `typing.Protocol`).
- Runtime deps stay exactly `yt-dlp` + `Pillow`.
- `config.json` / `history.json` formats and locations unchanged.
- UI copy stays in English.
- Local GUI tests need `DISPLAY=:0` (no `xvfb-run` on this machine).

## The parts of the how we decided

| Decision | Choice | Why |
|---|---|---|
| mypy strategy | A (type it properly) | Fixes the 3 root causes, not the 183 symptoms |
| Dropdown | B1 (inside `SearchEntry`) | Keeps the combobox feature |
| Button theming | resolve at draw time | Fixes F4 while the button becomes visible |
| Protocol location | `ui/protocols.py` | Avoids the `ui/__init__` → `window` → widgets cycle |
| Widget typing | `Protocol`, not the concrete class | Widgets do not need the whole `MainWindow` |
| `configure` helper | one module-level function | One checked place instead of 25 scattered calls |

## What's left to the builder

The full task-by-task plan, with exact file paths, signatures, test names and
commit messages, lives in
`docs/superpowers/plans/2026-11-13-ui-typing-and-wiring.md` (6 tasks).
