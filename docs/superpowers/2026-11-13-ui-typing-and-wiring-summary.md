# UI Typing and Component Wiring — Technical Summary

> Branch: `feature/ui-typing-and-wiring`
> Date: 2026-11-13
> Plan: `docs/superpowers/plans/2026-11-13-ui-typing-and-wiring.md`
> Design: `docs/superpowers/specs/2026-11-13-ui-typing-and-wiring-design.md`

## 1. Problems found

The previous modernization pass (v1.3.0) introduced a component library and a
unified theme, but three things were left unfinished:

1. **The UI layer was never actually type-checked.** `pyproject.toml` carried
   `[[tool.mypy.overrides]] module = "youmudow.ui.*" ignore_errors = true`.
   Measured with that override disabled, mypy reported **183 errors across 16
   files**. The override was a mute button, not a fix.
2. **Two components were dead code.** `SearchEntry` and `RoundedButton` were
   built and tested but never imported by any production module. The search bar
   still used a `ttk.Combobox` with a hand-rolled placeholder hack and three
   `tk.Button`s, each carrying its own `_theme` dict and hover bindings.
3. **The CI failure was misdiagnosed.** The red CI run on the modernization PR
   was not a broken workflow — `.github/workflows/ci.yml` already had the right
   four jobs. The actual cause was one flaky Tk test
   (`event_generate('<Return>')` does not receive keyboard focus under
   headless xvfb), already fixed on `main` in commit `3d46657`.

### Root causes behind the 183 mypy errors

Not 183 independent problems — three causes:

| Cause | Effect | Fix |
|---|---|---|
| Widgets typed `main_window: object` | ~90 `attr-defined` errors: every `self._mw._on_search()` was unchecked | `MainWindowProtocol` in `youmudow.ui.protocols` |
| `widget.configure(**kwargs)` on `tk.Misc` | 31 `call-arg` errors — mypy cannot narrow Tk's dynamic `configure` | `configure_widget()` helper in `youmudow.ui.typed` |
| `FONT` inferred as a union of tuple shapes | ~20 `arg-type` errors: incompatible with Tk's `font=` parameter | `FONT: dict[str, FontSpec]` with an explicit alias |

The remainder were `union-attr` errors in `window.py` from optional widget
attributes (`_status_bar`, `_detail_panel`, `_results_cards`, …) used without
narrowing.

## 2. Changes made

### Typed UI layer (Task 3)

- Removed the `ignore_errors` override from `pyproject.toml`.
- `youmudow.ui.typed` — `FontSpec`, `configure_widget()`, `font_tuple()`,
  `setattr_any()`.
- `youmudow.ui.protocols` — `MainWindowProtocol`, `AppControllerProtocol`,
  `ResultsCardsLike`, `ResultsCardsWriter`, `SearchBarLike`.
- Every widget constructor now takes `main_window: MainWindowProtocol`.
- `window.py` uses honest local narrowing (`status_bar = self._status_bar`;
  `if status_bar is not None:`) instead of `# type: ignore` — the brief forbade
  blanket suppressions.
- Result: **183 errors → 0**, `Success: no issues found in 68 source files`.

### Component wiring (Tasks 4 and 5)

- `SearchEntry` gained a history dropdown: `set_history()`, `open_history()`,
  `close_history()`, `history_is_open()`. The `tk.Listbox` is created lazily on
  first use, anchored below the field, and `<Down>` opens it.
- `SearchBar` now embeds a `SearchEntry` and three `RoundedButton`s instead of
  a `ttk.Combobox` and three `tk.Button`s. The placeholder hack, the `_theme`
  dicts and `add_hover_effect` calls are gone.
- Every keyboard shortcut is preserved: `Return`, `Ctrl+Return`, `Ctrl+V`,
  `Ctrl+A`, `Ctrl+BackSpace`, plus `<Down>` for the history.
- `RoundedButton` now resolves its colours at draw time, so it repaints when
  the theme changes (this also closed deferred minor **F4** from the v1.3.0
  review).

### Bug found and fixed while wiring

With an externally supplied `textvariable`, `search_var.set("hello")` did not
clear the placeholder state, so `get_query()` returned `""` — the field looked
filled but searched for nothing. `SearchEntry` now keeps its placeholder state
in sync through a `trace_add("write", ...)` on the variable.

## 3. Files affected

**New**
- `src/youmudow/ui/typed.py`
- `src/youmudow/ui/protocols.py`
- `tests/unit/test_typed.py`
- `tests/unit/test_protocols.py`
- `tests/unit/test_typing.py`
- `tests/unit/test_search_bar.py`

**Modified**
- `pyproject.toml` (mypy override removed)
- `src/youmudow/ui/window.py`
- `src/youmudow/ui/widgets/search_bar.py`
- `src/youmudow/ui/widgets/components/search_entry.py`
- `src/youmudow/ui/widgets/components/rounded_button.py`
- `src/youmudow/ui/widgets/{detail_panel,options_panel,queue_panel,history_panel,status_bar,results_cards,log_terminal}.py`
- `src/youmudow/ui/styles/{theme_apply,constants}.py`
- `src/youmudow/ui/widgets/components/thumbnail.py`
- `tests/unit/test_widgets.py`, `tests/unit/test_search_entry.py`

## 4. Performance

- Startup unchanged (the change is type-level, not runtime); smoke boot stays
  at roughly the same ~200 ms.
- `SearchEntry` creates its history `Listbox` lazily, so the search bar costs
  nothing extra when no history exists.
- Removing the `ttk.Combobox` in favour of a plain `tk.Entry` drops one ttk
  widget from the widget tree.

## 5. UI/UX

- The search field is now the same component everywhere: flat surface, 1 px
  focus ring that turns primary on focus, placeholder in secondary text.
- The search history is a dropdown anchored under the field instead of a
  native ttk combo popup, matching the rest of the design.
- The Search / Cancel / Stop buttons are now rounded canvas buttons drawn from
  the theme palette, so they follow light/dark switches automatically.
- Disabled buttons render in the disabled colour instead of Tk's default grey.

## 6. Refactors

- One `apply_theme` path, one colour resolver, one `FONT` table — unchanged in
  spirit from v1.3.0, now type-safe.
- `theme_apply.py` uses `configure_widget()` instead of raw `configure()`.
- The `window.py` optional-attribute pattern was replaced by explicit local
  narrowing, which also removed 38 potential `AttributeError`s.
- The `_download_service` access in `options_panel` goes through `getattr`
  instead of widening the controller protocol with a private attribute.

## 7. Test results

| Gate | Result |
|---|---|
| `pytest -q` | green (all tests) |
| `ruff check src/ tests/` | All checks passed |
| `ruff format --check src/ tests/` | formatted |
| `mypy` | Success: no issues found in 68 source files |
| `scripts/smoke_boot.py` | BOOT OK |
| Coverage | see the CI run; the v1.3.0 baseline was 86.91% |
| Manual check | placeholder, query, history dropdown, history pick, clear, button states — all OK |

New tests: `test_typed.py` (5), `test_protocols.py` (3), `test_typing.py` (3),
`test_search_bar.py` (10), plus 6 history tests in `test_search_entry.py`.

`test_typing.py` runs mypy on `src/youmudow/ui` as a subprocess, so the
absence of the escape hatch is enforced by the suite itself, not only by CI.

## 8. Known limitations

- `youmudow.ui.typed.setattr_any` exists because Tk widgets accept dynamic
  attributes that mypy cannot express; it is the sanctioned escape hatch for
  `_bg_key` / `_border_key` / `_theme` only.
- `options_panel` reaches the download service through `getattr`, because the
  service is optional at that point; the controller protocol deliberately does
  not expose a private attribute.
- `DetailPanel` still builds a real `ThumbnailLoader` (daemon thread plus the
  real cache directory) when no loader is injected — deferred from the v1.3.0
  review as minor **F7**.
- `write_atomic` still does not `fsync` the parent directory — inherited from
  the original implementation, deferred as minor **F8**.
