# UI Typing & Component Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the UI layer honestly type-checked (remove the `youmudow.ui.*` mypy escape hatch), wire `SearchEntry` and `RoundedButton` into the real search bar with working search-history dropdown, and keep the CI green.

**Architecture:** A `MainWindowProtocol` in `ui/protocols.py` declares the members the widgets use, so widgets depend on an interface instead of `object`. Tkinter's `configure(**kwargs)` is untyped, so every dynamic colour call goes through a typed helper module. `SearchEntry` grows an optional history dropdown implemented with `tk.Listbox` + `<Down>` binding; `SearchBar` swaps its `ttk.Combobox` and hand-rolled `tk.Button`s for `SearchEntry` and `RoundedButton`.

**Tech Stack:** Python 3.10+, tkinter (stdlib), mypy 2.3.0, ruff 0.16.1, pytest 9.0.2.

**Spec:** `docs/superpowers/specs/2026-11-13-ui-typing-and-wiring-design.md` (this plan's design; the modernization spec `docs/superpowers/specs/2026-11-12-modernize-design.md` remains the visual source of truth).

## Global Constraints

- No new runtime dependencies. Runtime deps stay exactly `yt-dlp` and `Pillow`.
- Every current user-facing feature is preserved: search history dropdown, Ctrl+Return, Ctrl+V/Ctrl+A/Ctrl+BackSpace, clipboard auto-paste, spinner, per-button disabled states, all keyboard shortcuts.
- `mypy` must pass on `src/youmudow` with **no** `ignore_errors` override for `youmudow.ui.*`.
- `ruff check src/ tests/` and `ruff format --check src/ tests/` must pass.
- `PYTHONPATH=src python3 -m pytest` must be green; GUI tests need `DISPLAY=:0` (real X, no `xvfb-run` locally).
- `scripts/smoke_boot.py` must print `BOOT OK`.
- Public API of `youmudow.domain`, `youmudow.app` and `youmudow.services` is unchanged.
- Existing persistence formats (`config.json`, `history.json`) and their locations are unchanged.
- UI copy stays in English.
- Python floor is 3.10: use `X | None` syntax, `typing.Protocol`, `from __future__ import annotations` where needed.

## Review Focus

The spec is a vision document; these are the input classes and failure modes it implies but no task's tests exercise. Each line names a test to add in the task that owns the code.

1. **The user pastes a URL while the history dropdown is open** → the dropdown closes, the pasted URL is searched, and the placeholder is not left in the field. → Task 4.
2. **The user clears the field with Ctrl+N while the history dropdown is open** → the dropdown closes and the placeholder comes back, so the field is never left showing stale history. → Task 4.
3. **A user types a query, then clicks a history entry** → the history entry replaces the query and the search runs exactly once (not twice). → Task 5.
4. **The user opens the history dropdown with no history at all** → the dropdown does not appear (an empty popup is a dead end). → Task 4.
5. **The theme is toggled while the search bar is visible** → the search field, its dropdown and its buttons are repainted in the new palette, not the old one. → Task 5.

---

### Task 1: Typed Tkinter helpers

**Files:**
- Create: `src/youmudow/ui/typed.py`
- Test: `tests/unit/test_typed.py`

**Interfaces:**
- Consumes: nothing (stdlib + tkinter only).
- Produces:
  - `configure_widget(widget: tk.Misc, **options: str) -> None` — calls `widget.configure(**options)` in a way mypy accepts; swallows `tk.TclError`.
  - `FontSpec = tuple[str, int] | tuple[str, int, str]`
  - `font_tuple(spec: FontSpec) -> tuple[str, int] | tuple[str, int, str]` — returns the spec unchanged; exists so `FONT` values are typed narrowly enough for Tk's `font=` parameter.
  - `setattr_any(obj: object, name: str, value: object) -> None` — sets a dynamic attribute (`_bg_key`, `_border_key`, `_theme`) without mypy `attr-defined` errors.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the typed Tkinter helpers."""

import tkinter as tk

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.typed import configure_widget, font_tuple, setattr_any


class TestConfigureWidget:
    def test_sets_options(self, root):
        frame = tk.Frame(root)
        configure_widget(frame, bg="#123456")
        assert frame.cget("bg") == "#123456"

    def test_swallows_tcl_error(self):
        class Frozen:
            def configure(self, **kwargs):
                raise tk.TclError("nope")

        configure_widget(Frozen(), bg="#123456")  # must not raise


class TestFontTuple:
    def test_returns_two_tuple_unchanged(self):
        assert font_tuple(("Ubuntu", 11)) == ("Ubuntu", 11)

    def test_returns_three_tuple_unchanged(self):
        assert font_tuple(("Ubuntu", 11, "bold")) == ("Ubuntu", 11, "bold")


class TestSetattrAny:
    def test_sets_attribute(self):
        frame = tk.Frame
        obj = tk.Frame.__new__(tk.Frame)
        setattr_any(obj, "_bg_key", "surface")
        assert obj._bg_key == "surface"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_typed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'youmudow.ui.typed'`

- [ ] **Step 3: Implement `src/youmudow/ui/typed.py`**

```python
"""Typed helpers for Tkinter's dynamically typed surface.

Tkinter's ``configure`` accepts arbitrary keyword arguments and mypy cannot
check them; widgets also carry dynamic attributes such as ``_bg_key``. These
helpers give both a single, checked entry point.
"""

from __future__ import annotations

import tkinter as tk

FontSpec = tuple[str, int] | tuple[str, int, str]


def configure_widget(widget: tk.Misc, **options: str) -> None:
    """Apply widget options, ignoring options the widget does not accept."""
    try:
        widget.configure(**options)
    except tk.TclError:
        pass


def font_tuple(spec: FontSpec) -> tuple[str, int] | tuple[str, int, str]:
    """Return a font spec Tk accepts, unchanged."""
    return spec


def setattr_any(obj: object, name: str, value: object) -> None:
    """Set a dynamic attribute on an otherwise statically typed object."""
    object.__setattr__(obj, name, value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_typed.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run full gates**

Run: `PYTHONPATH=src python3 -m pytest -q && ruff check src/ tests/ && ruff format --check src/ tests/ && PYTHONPATH=src python3 -m mypy`
Expected: suite green, `All checks passed!`, `Success: no issues found`

- [ ] **Step 6: Commit**

```bash
git add src/youmudow/ui/typed.py tests/unit/test_typed.py
git commit -m "feat(ui): add typed helpers for dynamic Tkinter attributes"
```

---

### Task 2: MainWindowProtocol

**Files:**
- Create: `src/youmudow/ui/protocols.py`
- Modify: `src/youmudow/ui/widgets/search_bar.py:12` (constructor annotation)
- Modify: `src/youmudow/ui/widgets/detail_panel.py:21` (constructor annotation)
- Modify: `src/youmudow/ui/widgets/options_panel.py:34` (constructor annotation)
- Modify: `src/youmudow/ui/widgets/queue_panel.py:39` (constructor annotation)
- Modify: `src/youmudow/ui/widgets/history_panel.py:16` (constructor annotation)
- Modify: `src/youmudow/ui/widgets/status_bar.py:9` (constructor annotation)
- Test: `tests/unit/test_protocols.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `src/youmudow/ui/protocols.py` with:
  - `class MainWindowProtocol(Protocol)` declaring the members the widgets use.
  - `class AppControllerProtocol(Protocol)` declaring the controller members the widgets use.

**Members the widgets actually use** (verified by grep — do not add more than these):

`MainWindowProtocol`:
- `_root: tk.Misc`
- `_controller: AppControllerProtocol`
- `_selected_video: Video | None`
- `_results_cards: ResultsCardsLike`
- `_search_bar: SearchBarLike`
- `_notebook: ttk.Notebook`
- `_main_content_frame: tk.Frame`
- `_on_search(self) -> None`
- `_on_cancel_search(self) -> None`
- `_on_cancel_download(self) -> None`
- `_on_download_now(self) -> None`
- `_on_open_folder(self) -> None`
- `_set_status(self, message: str) -> None`

`AppControllerProtocol`:
- `state: StateManager`
- `history: HistoryService`
- `enqueue(self, video: Video) -> None`
- `enqueue_multiple(self, videos: list[Video]) -> None`
- `remove_from_queue(self, video: Video) -> None`
- `clear_queue(self) -> None`
- `start_downloads(self) -> None`
- `stop_downloads(self) -> None`

Use forward references (`from __future__ import annotations`) and `TYPE_CHECKING` imports for `ResultsCards`, `SearchBar`, `StateManager`, `HistoryService`, `Video` so `protocols.py` imports no widget module at runtime (avoids an import cycle: `ui/__init__.py` imports `window.py`).

To avoid a cycle, `ResultsCardsLike` and `SearchBarLike` are **minimal Protocols declared in `protocols.py` themselves**, not imports of the widget classes:

```python
class ResultsCardsLike(Protocol):
    @property
    def is_playlist(self) -> bool: ...
    @property
    def playlist_videos(self) -> list[Video]: ...
    def get_selected_videos(self) -> list[Video]: ...

class SearchBarLike(Protocol):
    @property
    def search_var(self) -> tk.StringVar: ...
```

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the UI protocol definitions."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.protocols import MainWindowProtocol


class TestMainWindowProtocol:
    def test_main_window_satisfies_protocol(self):
        from youmudow.ui.window import MainWindow

        assert isinstance(MainWindow.__new__(MainWindow), MainWindowProtocol)

    def test_protocol_members_are_declared(self):
        names = set(MainWindowProtocol.__annotations__)
        assert {
            "_root",
            "_controller",
            "_selected_video",
            "_results_cards",
            "_search_bar",
            "_notebook",
            "_main_content_frame",
        } <= names
        assert {
            "_on_search",
            "_on_cancel_search",
            "_on_cancel_download",
            "_on_download_now",
            "_on_open_folder",
            "_set_status",
        } <= set(MainWindowProtocol.__dict__)

    def test_missing_attribute_does_not_satisfy_protocol(self):
        class Partial:
            pass

        assert not isinstance(Partial(), MainWindowProtocol)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_protocols.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'youmudow.ui.protocols'`

- [ ] **Step 3: Implement `src/youmudow/ui/protocols.py`**

Declare `ResultsCardsLike`, `SearchBarLike`, `AppControllerProtocol` and `MainWindowProtocol` as above, with `from __future__ import annotations` and `TYPE_CHECKING`-only imports of `Video`, `StateManager`, `HistoryService`.

- [ ] **Step 4: Annotate the widget constructors**

In each of `search_bar.py`, `detail_panel.py`, `options_panel.py`, `queue_panel.py`, `history_panel.py`, `status_bar.py`, change the constructor annotation from `main_window: object` to `main_window: MainWindowProtocol`, adding `from youmudow.ui.protocols import MainWindowProtocol` to the imports.

Note: `detail_panel.py` receives `main_window` and also constructs `QueuePanel(main_window._main_content_frame, main_window)`; `queue_panel.py` reads `self._mw._controller`. Both attributes exist in the protocol.

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_protocols.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run full gates**

Run: `PYTHONPATH=src python3 -m pytest -q && ruff check src/ tests/ && ruff format --check src/ tests/ && PYTHONPATH=src python3 -m mypy`
Expected: suite green, ruff green, mypy green (the `ignore_errors` override still hides `youmudow.ui.*`, so mypy passes as before)

- [ ] **Step 7: Commit**

```bash
git add src/youmudow/ui/protocols.py src/youmudow/ui/widgets/ tests/unit/test_protocols.py
git commit -m "refactor(ui): type widgets against a MainWindow protocol"
```

---

### Task 3: Remove the mypy escape hatch (strict UI typing)

**Files:**
- Modify: `pyproject.toml:80-84` (delete the `[[tool.mypy.overrides]]` block)
- Modify: `src/youmudow/ui/styles/theme_apply.py`
- Modify: `src/youmudow/ui/styles/constants.py`
- Modify: `src/youmudow/ui/window.py`
- Modify: `src/youmudow/ui/widgets/*.py` (each file with errors)
- Test: `tests/unit/test_typing.py`

**Interfaces:**
- Consumes: `configure_widget`, `setattr_any`, `font_tuple` from `src/youmudow/ui/typed.py` (Task 1); `MainWindowProtocol` from `src/youmudow/ui/protocols.py` (Task 2).
- Produces: `pyproject.toml` with **no** `[[tool.mypy.overrides]]` block; `PYTHONPATH=src python3 -m mypy` reports `Success: no issues found`.

**Measured error budget** (from `--config-file` with `ignore_errors = false`; 183 errors / 16 files):

| File | Errors | Dominant cause |
|---|---|---|
| `ui/window.py` | 40 | 38 `union-attr` on Optional attributes (`_status_bar`, `_detail_panel`, `_results_cards`, …) + 2 `arg-type` |
| `ui/styles/theme_apply.py` | 32 | 25 `call-arg` — `configure(bg=…)` on `tk.Misc`; 3 `attr-defined`; rest misc |
| `ui/widgets/detail_panel.py` | 32 | 23 `attr-defined` on `self._mw._x`; 9 `arg-type` (font tuples) |
| `ui/widgets/options_panel.py` | 18 | 10 `attr-defined`; 6 `arg-type`; 2 `call-overload` |
| `ui/widgets/search_bar.py` | 16 | 12 `attr-defined` on `self._mw._x`; 4 `arg-type` |
| `ui/widgets/results_cards.py` | 12 | mixed |
| `ui/widgets/components/rounded_button.py` | 8 | `command: object` not callable; font tuples |
| `ui/widgets/queue_panel.py` | 7 | `attr-defined` |
| `ui/widgets/history_panel.py` | 7 | `attr-defined` |
| `ui/styles/constants.py` | 4 | `_c()` with non-literal keys |
| `ui/widgets/status_bar.py` | 3 | `attr-defined` |
| `ui/widgets/log_terminal.py` | 2 | misc |
| `ui/widgets/components/empty_state.py` | 2 | misc |
| `ui/widgets/components/thumbnail.py` | 1 | `import-untyped` for PIL |
| `ui/widgets/components/search_entry.py` | 1 | misc |
| `ui/styles/styles.py` | 1 | misc |

- [ ] **Step 1: Write the failing test**

```python
"""The UI package must be type-checked without a mypy escape hatch."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


class TestNoMypyEscapeHatch:
    def test_pyproject_has_no_ignore_errors_override(self):
        content = PYPROJECT.read_text(encoding="utf-8")
        assert "ignore_errors" not in content

    def test_mypy_passes_on_ui_package(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/youmudow/ui"],
            capture_output=True,
            text=True,
            cwd=str(PYPROJECT.parent),
        )
        assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_typing.py -v`
Expected: FAIL — `assert "ignore_errors" not in content` fails (the override is still in `pyproject.toml`)

- [ ] **Step 3: Delete the override in `pyproject.toml`**

Remove the whole block:

```toml
[[tool.mypy.overrides]]
module = "youmudow.ui.*"
ignore_errors = true
```

Do not add any replacement override for `youmudow.ui.*`.

- [ ] **Step 4: Fix `ui/styles/theme_apply.py`**

Replace every `widget.configure(...)` call with `configure_widget(widget, ...)` from `youmudow.ui.typed`. The `_RULES` table keeps its shape; only the call site changes. Also replace the `getattr(widget, "_bg_key", "bg")` dynamic reads with a typed accessor that mypy accepts:

```python
from youmudow.ui.typed import configure_widget, setattr_any
```

and read dynamic attributes through `getattr(widget, "_bg_key", "bg")` as today — `getattr` with a literal string is already mypy-safe. Only the `configure(**kwargs)` calls are the problem.

- [ ] **Step 5: Fix `ui/styles/constants.py`**

`FONT` is inferred as `dict[str, tuple[str, int, str] | tuple[str, int]]`; Tk's `font=` parameter wants a narrower type. Annotate the dict:

```python
from youmudow.ui.typed import FontSpec

FONT: dict[str, FontSpec] = { ... }
```

where `FontSpec = tuple[str, int] | tuple[str, int, str]`. Then every `font=FONT["body"]` call site type-checks. `FONT["h2"]` is `tuple[str, int, str]` — still compatible.

The `_c(key)` `call-arg` errors come from `_c` being called with non-literal keys in `constants.py` itself; annotate `_c` as `def _c(key: str) -> str` (already) and ensure callers pass `str`.

- [ ] **Step 6: Fix the widget files**

Apply, per file:

- `detail_panel.py`, `options_panel.py`, `search_bar.py`, `queue_panel.py`, `history_panel.py`, `status_bar.py`: the `attr-defined` errors on `self._mw._x` are already gone from Task 2 (the protocol declares them). Remaining errors are `arg-type` on `font=FONT[...]` (fixed by Step 5) and `_bg_key` assignments (fix with `setattr_any(self, "_bg_key", "surface")`).
- `results_cards.py`: `_bg_key` / `_border_key` assignments → `setattr_any`; font args → fixed by Step 5.
- `rounded_button.py`: change `command: object | None = None` to `command: Callable[[], None] | None = None` and store it as `self._command: Callable[[], None] | None`. The `self._command()` call then type-checks.
- `empty_state.py`: `action_command` gets the same `Callable[[], None] | None` treatment.
- `search_entry.py`: `command` → `Callable[[], None] | None`; `textvariable` → `tk.StringVar | None`.
- `thumbnail.py`: add `# type: ignore[import-untyped]` on the PIL import **only** (Pillow ships no type stubs) — `warn_unused_ignores` is on, so the ignore must be exactly what mypy needs.
- `log_terminal.py`, `styles.py`: fix the remaining misc/operator errors per the mypy output.

- [ ] **Step 7: Fix `ui/window.py`**

The 38 `union-attr` errors come from attributes declared `X | None` but used after construction. The widgets are built inside `_setup_ui`/`_create_main_content`, so by the time any handler runs they exist.

Preferred fix (keeps the optional declaration honest): make the handlers guard on `None` where the attribute can legitimately be absent, and use local narrowing where mypy cannot follow the construction order. Concretely:

```python
status_bar = self._status_bar
if status_bar is not None:
    status_bar.set_status(message)
```

Use this narrowing pattern for `_status_bar`, `_detail_panel`, `_results_cards`, `_search_bar`, `_history_panel`, `_log_terminal`, `_log_frame`, `_menubar`, `_notebook`, `_paned_window`, `_main_content_frame`.

Do **not** silence these with `# type: ignore` — the point of this task is that mypy checks them.

- [ ] **Step 8: Verify mypy is clean**

Run: `PYTHONPATH=src python3 -m mypy`
Expected: `Success: no issues found in N source files` with **no** per-module override for `youmudow.ui.*`.

If errors remain, iterate on the reported file:line until zero. Do not add `ignore_errors` back and do not add blanket `# type: ignore` comments.

- [ ] **Step 9: Run the full gates**

Run: `PYTHONPATH=src python3 -m pytest -q && ruff check src/ tests/ && ruff format --check src/ tests/ && PYTHONPATH=src python3 -m mypy && PYTHONPATH=src python3 scripts/smoke_boot.py`
Expected: suite green, ruff green, mypy green, `BOOT OK`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml src/youmudow/ui/ tests/unit/test_typing.py
git commit -m "refactor(ui): type-check the UI layer without a mypy override"
```

---

### Task 4: SearchEntry with history dropdown

**Files:**
- Modify: `src/youmudow/ui/widgets/components/search_entry.py`
- Test: `tests/unit/test_search_entry.py` (extend)

**Interfaces:**
- Consumes: `configure_widget`, `setattr_any` from `src/youmudow/ui/typed.py` (Task 1).
- Produces: `SearchEntry` gains:
  - `__init__(self, master, *, placeholder="", textvariable=None, command=None, history: list[str] | None = None)`
  - `set_history(history: list[str]) -> None` — stores the list and, if the dropdown is open, refreshes it.
  - `open_history() -> None` — opens the dropdown with the current history (no-op if the history is empty).
  - `close_history() -> None` — closes the dropdown.
  - `history_is_open() -> bool`
  - `<Down>` binding on the inner entry opens the dropdown when history is non-empty.

The dropdown is a `tk.Listbox` created lazily inside the `SearchEntry` frame, anchored below the entry, `overlap` style via `place(relx=0, rely=1, anchor="nw")`. Selecting an item (double-click or `<Return>` while open) sets the field to that value and fires `command`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_search_entry.py`:

```python
class TestSearchEntryHistory:
    def test_history_dropdown_does_not_open_without_history(self, root):
        e = SearchEntry(root, history=[])
        e.open_history()
        assert not e.history_is_open()

    def test_history_dropdown_opens_with_history(self, root):
        e = SearchEntry(root, history=["url1", "url2"])
        e.open_history()
        assert e.history_is_open()

    def test_set_history_updates_dropdown_contents(self, root):
        e = SearchEntry(root, history=["url1"])
        e.open_history()
        e.set_history(["a", "b"])
        assert list(e._history_listbox.get(0, "end")) == ["a", "b"]

    def test_selecting_history_item_sets_field_and_fires_command(self, root):
        calls = []
        e = SearchEntry(root, command=lambda: calls.append(1), history=["url1"])
        e.open_history()
        e._history_listbox.selection_set(0)
        e._on_history_select(None)
        assert e.get() == "url1"
        assert calls == [1]

    def test_close_history_hides_dropdown(self, root):
        e = SearchEntry(root, history=["url1"])
        e.open_history()
        e.close_history()
        assert not e.history_is_open()

    def test_clear_closes_history(self, root):
        e = SearchEntry(root, history=["url1"])
        e.open_history()
        e.clear()
        assert not e.history_is_open()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_search_entry.py -v`
Expected: FAIL — `AttributeError: 'SearchEntry' object has no attribute 'open_history'`

- [ ] **Step 3: Implement the dropdown in `src/youmudow/ui/widgets/components/search_entry.py`**

- Add `history: list[str] | None = None` to `__init__`; store `self._history = list(history or [])`.
- Create `self._history_listbox: tk.Listbox | None = None` lazily in `_ensure_history_listbox()`, using `configure_widget` for its colors.
- `open_history()`: if `not self._history`, return. Otherwise ensure the listbox, replace its contents with the history, `place(relx=0, rely=1, anchor="nw", width=self.winfo_width())`, and `lift()` it above other widgets.
- `close_history()`: `place_forget()` the listbox if it exists.
- `set_history(history)`: replace `self._history`; if the dropdown is open, refresh the listbox contents.
- `_on_history_select(_event)`: set the field to the selected entry, close the dropdown, and fire `self._command()`.
- Bind `<Down>` on the inner entry to `open_history` (return `"break"` when it opens so the caret does not move).
- `clear()` closes the dropdown.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_search_entry.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run full gates**

Run: `PYTHONPATH=src python3 -m pytest -q && ruff check src/ tests/ && ruff format --check src/ tests/ && PYTHONPATH=src python3 -m mypy`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add src/youmudow/ui/widgets/components/search_entry.py tests/unit/test_search_entry.py
git commit -m "feat(ui): add history dropdown to SearchEntry"
```

---

### Task 5: Wire SearchEntry and RoundedButton into SearchBar

**Files:**
- Modify: `src/youmudow/ui/widgets/search_bar.py`
- Modify: `src/youmudow/ui/window.py` (theme repaint must reach the new widgets; the `_apply_theme_colors` walk already covers `tk.Frame` children, but the `RoundedButton` canvas needs its colours recomputed)
- Test: `tests/unit/test_search_bar.py` (new file), `tests/unit/test_widgets.py` (update the `SearchBar` expectations)

**Interfaces:**
- Consumes: `SearchEntry` with `set_history` / `open_history` (Task 4); `RoundedButton` from `src/youmudow/ui/widgets/components/rounded_button.py`; `MainWindowProtocol` (Task 2); `configure_widget` / `setattr_any` (Task 1).
- Produces: `SearchBar` public surface:
  - `search_var: tk.StringVar` — unchanged.
  - `search_entry: SearchEntry` — **type changes** from `ttk.Combobox` to `SearchEntry`. `window.py`'s Ctrl+L shortcut calls `.focus_set()`, which `SearchEntry` already provides.
  - `update_history(history: list[str]) -> None` — forwards to `SearchEntry.set_history`.
  - `get_query() -> str` — unchanged semantics: returns `""` when the field shows the placeholder.
  - `update_button_states(is_searching: bool, is_downloading: bool) -> None` — unchanged semantics; now drives `RoundedButton.set_enabled`.
  - `_search_btn`, `_cancel_btn`, `_cancel_dl_btn` become `RoundedButton` instances (test code referencing `.cget("state")` must change to `.invoke()` / a new `is_enabled()` accessor).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_search_bar.py`:

```python
"""Tests for the wired SearchBar."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.ui.widgets.components.rounded_button import RoundedButton
from youmudow.ui.widgets.components.search_entry import SearchEntry
from youmudow.ui.widgets.search_bar import SearchBar


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def mw():
    m = Mock()
    m._root = tk.Tk()
    m._root.withdraw()
    m._controller = Mock()
    m._selected_video = None
    return m


class TestSearchBarWiring:
    def test_uses_search_entry(self, root, mw):
        bar = SearchBar(root, mw)
        assert isinstance(bar.search_entry, SearchEntry)

    def test_uses_rounded_buttons(self, root, mw):
        bar = SearchBar(root, mw)
        assert isinstance(bar._search_btn, RoundedButton)
        assert isinstance(bar._cancel_btn, RoundedButton)
        assert isinstance(bar._cancel_dl_btn, RoundedButton)

    def test_update_history_forwards_to_entry(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_history(["url1", "url2"])
        assert bar.search_entry._history == ["url1", "url2"]

    def test_get_query_is_empty_when_placeholder_shown(self, root, mw):
        bar = SearchBar(root, mw)
        assert bar.get_query() == ""

    def test_get_query_returns_typed_text(self, root, mw):
        bar = SearchBar(root, mw)
        bar.search_var.set("hello")
        assert bar.get_query() == "hello"

    def test_search_button_invokes_search(self, root, mw):
        mw._on_search = Mock()
        bar = SearchBar(root, mw)
        bar._search_btn.invoke()
        mw._on_search.assert_called_once()

    def test_cancel_button_disabled_while_not_searching(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_button_states(False, False)
        assert not bar._cancel_btn.is_enabled()

    def test_cancel_button_enabled_while_searching(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_button_states(True, False)
        assert bar._cancel_btn.is_enabled()

    def test_stop_button_enabled_while_downloading(self, root, mw):
        bar = SearchBar(root, mw)
        bar.update_button_states(False, True)
        assert bar._cancel_dl_btn.is_enabled()

    def test_paste_url_triggers_search_on_return(self, root, mw):
        mw._on_search = Mock()
        bar = SearchBar(root, mw)
        bar.search_var.set("https://youtu.be/abc12345678")
        bar.search_entry._on_return(None)
        mw._on_search.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_search_bar.py -v`
Expected: FAIL — `isinstance(bar.search_entry, SearchEntry)` fails (it is still a `ttk.Combobox`)

- [ ] **Step 3: Extend `RoundedButton` with `is_enabled()`**

In `src/youmudow/ui/widgets/components/rounded_button.py`, add:

```python
def is_enabled(self) -> bool:
    return self._enabled
```

and change `command: object | None = None` to `command: Callable[[], None] | None = None`.

- [ ] **Step 4: Rewrite `SearchBar` to use `SearchEntry` and `RoundedButton`**

- Replace the `entry_frame` + `ttk.Combobox` with a `SearchEntry` instance:

```python
self._entry = SearchEntry(
    self,
    placeholder="Search or paste URL (YouTube, SoundCloud, Vimeo...)",
    textvariable=self._search_var,
    command=self._on_submit,
)
self._entry.pack(side="left", fill="both", expand=True, padx=(0, SPACING["sm"]))
```

  `SearchEntry` handles the placeholder itself (real placeholder, not a value), so the old `_placeholder`/`_on_focus_in`/`_on_focus_out` hack and `get_query`'s placeholder comparison are deleted. `get_query()` becomes `return self._entry.get().strip()`.

- Keep the keyboard bindings, now on `self._entry._entry` (the inner `tk.Entry`):
  - `<Return>` → search (the `SearchEntry` `command` covers this; keep the `command=self._on_submit` wiring and do not bind `<Return>` twice).
  - `<Control-Return>` → download if a video is selected, else search.
  - `<Control-v>` / `<Control-V>` → paste the clipboard URL if it is a supported URL (keep the existing `_on_paste` logic, operating on `self._search_var`).
  - `<Control-a>` / `<Control-A>` → select all.
  - `<Control-BackSpace>` → delete the last word.
  - `<Down>` → open the history dropdown (handled by `SearchEntry`).

- Replace the three `tk.Button`s with `RoundedButton`s:

```python
self._search_btn = RoundedButton(self, "Search", command=lambda: self._mw._on_search(), variant="primary", font=FONT["h3"])
self._cancel_btn = RoundedButton(self, "Cancel", command=lambda: self._mw._on_cancel_search(), variant="secondary")
self._cancel_dl_btn = RoundedButton(self, "Stop", command=lambda: self._mw._on_cancel_download(), variant="danger")
```

  Each `pack(side="left", padx=...)` as today. `self._search_btn` keeps `font=FONT["h3"]` to match the current visual weight.

- `update_history(history)` → `self._entry.set_history(history)`.

- `update_button_states(is_searching, is_downloading)` → use `set_enabled`:

```python
self._search_btn.set_enabled(not is_busy)
self._cancel_btn.set_enabled(is_searching)
self._cancel_dl_btn.set_enabled(is_downloading)
```

  Keep the spinner behaviour exactly as today.

- Remove `add_hover_effect` usage and the `_theme` dicts (the `RoundedButton` owns hover and theme).

- Keep `search_entry` as a property returning the `SearchEntry`, so `window.py`'s Ctrl+L shortcut keeps working unchanged.

- The `search_var` property stays.

- [ ] **Step 5: Make the theme repaint reach the new widgets**

`RoundedButton` caches `_fill_color` / `_text_color` (it redraws only on `<Configure>`, hover, `set_enabled` and `set_text`). A theme toggle would leave it stale.

Fix in `src/youmudow/ui/widgets/components/rounded_button.py`: resolve the colours at draw time instead of caching them. Change `_update_colors()` to compute the current colours into instance attributes **and** call it from `_draw()`, so every repaint re-reads the palette:

```python
def _draw(self) -> None:
    self._update_colors()
    self.delete("all")
    ...
```

- [ ] **Step 6: Update the existing `SearchBar` tests**

In `tests/unit/test_widgets.py`, the `TestSearchBar` class refers to the old internals:
- `test_get_query_ignores_placeholder` uses `sb._search_combo.set(sb._placeholder)` → rewrite as `sb.search_entry.set("")` and assert `sb.get_query() == ""`.
- `test_update_history` asserts `sb._search_combo["values"]` → rewrite as `assert sb.search_entry._history == history`.
- `test_search_entry_property` asserts `sb.search_entry is sb._search_combo` → rewrite as `assert isinstance(sb.search_entry, SearchEntry)`.
- `test_update_button_states` asserts `sb._search_btn.cget("state") == "disabled"` → rewrite as `assert not sb._search_btn.is_enabled()`.

Those cases now live in `tests/unit/test_search_bar.py`; delete them from `test_widgets.py` rather than duplicating them.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/unit/test_search_bar.py tests/unit/test_widgets.py tests/unit/test_search_entry.py tests/unit/test_rounded_button.py -v`
Expected: PASS

- [ ] **Step 8: Run the full gates**

Run: `PYTHONPATH=src python3 -m pytest -q && ruff check src/ tests/ && ruff format --check src/ tests/ && PYTHONPATH=src python3 -m mypy && PYTHONPATH=src python3 scripts/smoke_boot.py`
Expected: all green, `BOOT OK`

- [ ] **Step 9: Manually verify the search bar**

Run: `PYTHONPATH=src python3 scripts/smoke_boot.py` (must print `BOOT OK`) and then drive the bar with a short throwaway script under `DISPLAY=:0` that:
- opens the history dropdown with `bar.search_entry.set_history(["a", "b"])` and asserts `history_is_open()`;
- types a query and confirms `get_query()` returns it;
- confirms the placeholder returns after `clear()`.

Do not commit the throwaway script.

- [ ] **Step 10: Commit**

```bash
git add src/youmudow/ui/widgets/search_bar.py src/youmudow/ui/widgets/components/rounded_button.py src/youmudow/ui/window.py tests/unit/test_search_bar.py tests/unit/test_widgets.py
git commit -m "feat(ui): wire SearchEntry and RoundedButton into the search bar"
```

---

### Task 6: CI verification and documentation

**Files:**
- Modify: `docs/superpowers/2026-11-13-ui-typing-and-wiring-summary.md` (new summary)
- Modify: `CHANGELOG.md` (`## [Unreleased]`)

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: a summary document and CHANGELOG entries.

- [ ] **Step 1: Run the whole gate one last time**

Run: `PYTHONPATH=src python3 -m pytest -q && ruff check src/ tests/ && ruff format --check src/ tests/ && PYTHONPATH=src python3 -m mypy && PYTHONPATH=src python3 scripts/smoke_boot.py && PYTHONPATH=src python3 -m pytest --cov=youmudow --cov-report=term-missing -q`
Expected: everything green; coverage ≥ the 86.91% baseline.

- [ ] **Step 2: Push the branch and let CI run**

```bash
git checkout -b feature/ui-typing-and-wiring
git push -u origin feature/ui-typing-and-wiring
```

Then check `gh run list` until the CI workflow finishes. The `typecheck` job must be green **because the override is gone** — that is the proof the change works.

If the CI `test` job fails on a Tk event test, make the test deterministic (call the handler directly instead of `event_generate`) rather than adding retries — the same fix already applied in commit `3d46657`.

- [ ] **Step 3: Write the summary**

Create `docs/superpowers/2026-11-13-ui-typing-and-wiring-summary.md` with the sections: problems found, changes made, files affected, performance, UI/UX, refactors, test results, known limitations.

- [ ] **Step 4: Update the CHANGELOG**

Under `## [Unreleased]`, add:
- **Changed**: the UI layer is now type-checked by mypy without a per-package override; the search bar uses `SearchEntry` and `RoundedButton`; `RoundedButton` repaints when the theme changes.
- **Added**: `SearchEntry` history dropdown; typed Tkinter helpers in `youmudow.ui.typed`; the `MainWindowProtocol` interface.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/2026-11-13-ui-typing-and-wiring-summary.md CHANGELOG.md
git commit -m "docs: summarize UI typing and component wiring work"
```

- [ ] **Step 6: Open the pull request**

```bash
gh pr create --base main --head feature/ui-typing-and-wiring --title "Type-check the UI layer and wire the new UI components" --body "..."
```

Report the PR URL. Keep the branch — the user asked for the "option to go back", so nothing is merged or deleted without an explicit request.
