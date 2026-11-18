import tkinter as tk


def test_window_builds_against_real_controller(stack):
    assert "YouMuDow" in stack.window._root.title()
    assert stack.window._search_bar is not None
    assert stack.window._results_cards is not None
    assert stack.window._detail_panel is not None


def test_startup_checks_can_be_skipped(stack_factory, monkeypatch):
    delays = []
    original_after = tk.Misc.after

    def spy_after(self, ms, func=None, *args):
        delays.append(ms)
        return original_after(self, ms, func, *args)

    monkeypatch.setattr(tk.Misc, "after", spy_after)
    stack_factory(run_startup_checks=False)
    assert 500 not in delays
    assert 3000 not in delays


def test_startup_checks_run_by_default(stack_factory, monkeypatch):
    delays = []
    original_after = tk.Misc.after

    def spy_after(self, ms, func=None, *args):
        delays.append(ms)
        return original_after(self, ms, func, *args)

    monkeypatch.setattr(tk.Misc, "after", spy_after)
    stack_factory(run_startup_checks=True)
    assert 500 in delays
    assert 3000 in delays
