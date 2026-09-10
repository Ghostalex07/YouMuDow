"""Tests for LogTerminal widget."""

import tkinter as tk

import pytest


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")


def test_log_terminal_clear_empties_buffer(tk_root):
    from youmudow.ui.widgets.log_terminal import LogTerminal

    terminal = LogTerminal(tk_root)
    terminal.append("test message", level="info")
    tk_root.update_idletasks()
    terminal.clear()
    tk_root.update_idletasks()
    assert terminal.get_logs() == ""


def test_log_terminal_trim_updates_line_count(tk_root):
    from youmudow.ui.widgets.log_terminal import LogTerminal

    terminal = LogTerminal(tk_root, max_lines=10)
    terminal._line_count = 15
    terminal._text.configure(state="normal")
    for i in range(15):
        terminal._text.insert("end", f"line {i}\n")
    terminal._text.configure(state="disabled")
    terminal._trim_lines()
    assert terminal._line_count == max(0, 15 - 10 // 10)


def test_log_terminal_buffer_is_capped(tk_root):
    from youmudow.ui.widgets.log_terminal import MAX_LINES, LogTerminal

    terminal = LogTerminal(tk_root, max_lines=MAX_LINES)
    for i in range(5000):
        terminal.append(f"msg {i}")
    lines = terminal.get_logs().split("\n")
    assert len(lines) <= MAX_LINES * 5 + 1
    assert any(l.endswith("msg 4999") for l in lines)
