"""Tests for the window-level settings helpers.

``apply_settings``/``save_settings`` only touch the config object and the Tk
root, so both are mocks here: no display server is required.
"""

import logging
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock

import pytest

pytest.importorskip("tkinter")

from youmudow.ui import window_settings

GEOMETRY = "1100x720+50+50"


@pytest.fixture
def root():
    root = Mock()
    root.geometry.return_value = GEOMETRY
    root.winfo_x.return_value = 50
    root.winfo_y.return_value = 50
    root.winfo_width.return_value = 1100
    root.winfo_height.return_value = 720
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    return root


@pytest.fixture
def options():
    return Mock()


@pytest.fixture
def config():
    config = Mock()
    config.window_geometry = ""
    return config


class TestApplySettings:
    def test_does_nothing_without_config(self, options, root):
        window_settings.apply_settings(None, options, root)

        options.load_settings.assert_not_called()
        root.geometry.assert_not_called()

    def test_loads_options_from_config(self, config, options, root):
        window_settings.apply_settings(config, options, root)

        options.load_settings.assert_called_once_with(config)

    def test_restores_saved_geometry(self, config, options, root):
        config.window_geometry = GEOMETRY

        window_settings.apply_settings(config, options, root)

        root.geometry.assert_called_once_with(GEOMETRY)

    def test_leaves_geometry_alone_when_none_is_saved(self, config, options, root):
        window_settings.apply_settings(config, options, root)

        root.geometry.assert_not_called()

    def test_logs_and_swallows_load_failure(self, config, options, root, caplog):
        options.load_settings.side_effect = ValueError("corrupt config")

        with caplog.at_level(logging.WARNING):
            window_settings.apply_settings(config, options, root)

        assert "Could not apply saved config" in caplog.text


class TestSaveSettings:
    def test_does_nothing_without_config(self, options, root):
        window_settings.save_settings(None, options, root, Path("/tmp/output"))

        options.save_settings.assert_not_called()

    def test_stores_options_geometry_output_path_and_flushes(self, config, options, root):
        output_path = Path("/tmp/output")

        window_settings.save_settings(config, options, root, output_path)

        options.save_settings.assert_called_once_with(config)
        assert config.window_geometry == GEOMETRY
        assert config.output_path == output_path
        config.save.assert_called_once()

    def test_reads_geometry_from_root(self, config, options, root):
        window_settings.save_settings(config, options, root, Path("/tmp/output"))

        root.geometry.assert_called_once()

    def test_keeps_saved_output_path_when_none_is_reported(self, config, options, root):
        previous = Path("/srv/previous")
        config.output_path = previous

        window_settings.save_settings(config, options, root, None)

        assert config.output_path == previous
        config.save.assert_called_once()

    def test_swallows_geometry_read_failure(self, config, options, root):
        root.geometry.side_effect = tk.TclError("application has been destroyed")

        window_settings.save_settings(config, options, root, Path("/tmp/output"))

        assert config.output_path == Path("/tmp/output")
        config.save.assert_called_once()

    def test_swallows_output_path_failure(self, options, root):
        class ReadOnlyOutputPath:
            def __init__(self):
                self.saved = False

            @property
            def output_path(self):
                return None

            @output_path.setter
            def output_path(self, value):
                raise ValueError("read-only")

            def save(self):
                self.saved = True

        config = ReadOnlyOutputPath()

        window_settings.save_settings(config, options, root, Path("/tmp/output"))

        assert config.saved is True

    def test_swallows_save_failure(self, config, options, root):
        config.save.side_effect = ValueError("cannot serialise")

        window_settings.save_settings(config, options, root, Path("/tmp/output"))

        options.save_settings.assert_called_once_with(config)


class TestRestoreGeometry:
    def test_keeps_on_screen_geometry(self, root):
        window_settings._restore_geometry(root, GEOMETRY)

        root.geometry.assert_called_once_with(GEOMETRY)

    def test_clamps_offscreen_position_to_origin(self, root):
        root.winfo_x.return_value = -5000
        root.winfo_y.return_value = -5000

        window_settings._restore_geometry(root, GEOMETRY)

        root.geometry.assert_called_with("1200x800+0+0")

    def test_clamps_size_to_smaller_screen(self, root):
        root.winfo_x.return_value = -5000
        root.winfo_screenwidth.return_value = 1024
        root.winfo_screenheight.return_value = 768

        window_settings._restore_geometry(root, GEOMETRY)

        root.geometry.assert_called_with("1024x768+0+0")

    def test_clamps_when_window_sits_past_screen_edge(self, root):
        root.winfo_x.return_value = 5000
        root.winfo_y.return_value = 4000

        window_settings._restore_geometry(root, GEOMETRY)

        assert root.geometry.call_args.args[0] == "1200x800+0+0"

    def test_ignores_tk_errors(self, root):
        root.geometry.side_effect = tk.TclError("bad geometry string")

        window_settings._restore_geometry(root, "not-a-geometry")
