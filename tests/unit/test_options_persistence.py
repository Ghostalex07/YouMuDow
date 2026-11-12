"""Tests for OptionsPanel settings persistence.

The panel needs real Tk variables and a real combobox, so these tests build the
whole ``MainWindow`` against a mock controller and config, then drive the panel
through the same public ``load_settings``/``save_settings`` API the window uses.
"""

import os
import tkinter as tk
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("No display server available, skipping Tk tests", allow_module_level=True)

from youmudow.adapters.browser_profiles import BrowserProfile

SAVED_KEYS = {
    "format",
    "quality",
    "subtitles",
    "subtitle_lang",
    "embed_subtitles",
    "use_cookies",
    "cookies_source",
    "cookies_file",
    "browser",
    "profile",
    "rate_limit",
    "split_chapters",
    "options_panel_open",
    "concurrent_downloads",
}

BROWSERS = ["chrome", "firefox"]
PROFILES = {
    "chrome": [
        BrowserProfile(name="Default", path="/tmp/chrome-default", browser="chrome"),
        BrowserProfile(name="Profile 1", path="/tmp/chrome-p1", browser="chrome"),
    ],
    "firefox": [
        BrowserProfile(name="work", path="/tmp/firefox-work", browser="firefox"),
    ],
}


def _config(**values) -> Mock:
    """A config mock whose ``get`` reads from ``values``."""
    config = Mock()
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    return config


@pytest.fixture(autouse=True)
def browser_catalog():
    """Pin the browser/profile discovery so assertions do not depend on the host."""
    with (
        patch(
            "youmudow.ui.widgets.options_panel.get_available_browsers",
            return_value=list(BROWSERS),
        ),
        patch(
            "youmudow.ui.widgets.options_panel.get_all_browser_profiles",
            return_value=PROFILES,
        ),
    ):
        yield


@pytest.fixture
def options():
    from youmudow.ui.window import MainWindow

    config = Mock()
    config.get.side_effect = lambda key, default=None: default
    config.get_search_history.return_value = []
    config.window_geometry = ""

    controller = Mock()
    controller.state = Mock()

    window = MainWindow(controller=controller, config=config)
    window._root.update()
    yield window._detail_panel.options
    window.destroy()


class TestLoadSettings:
    def test_restores_every_persisted_value(self, options):
        config = _config(
            format="m4a",
            quality="1080",
            subtitles=True,
            subtitle_lang="es",
            embed_subtitles=True,
            use_cookies=True,
            cookies_source="browser",
            cookies_file="",
            browser="firefox",
            profile="work",
            rate_limit="1M",
            split_chapters=True,
            concurrent_downloads=3,
        )

        options.load_settings(config)

        assert options._format_var.get() == "m4a"
        assert options._quality_var.get() == "1080"
        assert options._subtitles_var.get() is True
        assert options._subtitle_lang_var.get() == "es"
        assert options._embed_subs_var.get() is True
        assert options._use_cookies_var.get() is True
        assert options._cookies_source_var.get() == "browser"
        assert options._browser_var.get() == "firefox"
        assert options._profile_var.get() == "work"
        assert options._rate_limit_var.get() == "1M"
        assert options._split_chapters_var.get() is True
        assert options._concurrent_var.get() == 3

    def test_restores_cookies_file_source(self, options):
        config = _config(cookies_source="file", cookies_file="/tmp/cookies.txt")

        options.load_settings(config)

        assert options._cookies_source_var.get() == "file"
        assert options._cookies_file_var.get() == "/tmp/cookies.txt"

    def test_unknown_saved_browser_falls_back_to_first_available(self, options):
        config = _config(browser="safari")

        options.load_settings(config)

        assert options._browser_var.get() == BROWSERS[0]

    def test_saved_profile_missing_from_combobox_falls_back_to_first_profile(self, options):
        config = _config(browser="chrome", profile="No Such Profile")

        options.load_settings(config)

        assert list(options._profile_combo["values"]) == ["Default", "Profile 1"]
        assert options._profile_var.get() == "Default"

    def test_no_installed_browser_falls_back_to_chrome(self, options):
        config = _config(browser="firefox")

        with (
            patch(
                "youmudow.ui.widgets.options_panel.get_available_browsers",
                return_value=[],
            ),
            patch(
                "youmudow.ui.widgets.options_panel.get_all_browser_profiles",
                return_value={},
            ),
        ):
            options.load_settings(config)

        assert options._browser_var.get() == "chrome"
        assert options._profile_var.get() == "Default"

    def test_browser_without_profiles_falls_back_to_default_profile(self, options):
        config = _config(browser="chrome", profile="Profile 1")

        with patch(
            "youmudow.ui.widgets.options_panel.get_all_browser_profiles",
            return_value={"chrome": []},
        ):
            options.load_settings(config)

        assert list(options._profile_combo["values"]) == ["Default"]
        assert options._profile_var.get() == "Default"

    def test_saved_open_state_packs_the_options_frame(self, options):
        config = _config(options_panel_open=True)

        options.load_settings(config)

        assert options._options_frame.winfo_manager() == "pack"
        assert "OPTIONS" in options._detail_toggle_btn.cget("text")

    def test_saved_closed_state_leaves_the_options_frame_hidden(self, options):
        options.load_settings(_config(options_panel_open=False))

        assert options._options_frame.winfo_manager() == ""


class TestSaveSettings:
    def test_writes_every_key_through_config_set(self, options):
        config = _config(concurrent_downloads=2)

        options.save_settings(config)

        stored = {call.args[0]: call.args[1] for call in config.set.call_args_list}
        assert set(stored) == SAVED_KEYS
        assert len(config.set.call_args_list) == len(SAVED_KEYS)

    def test_writes_current_option_values(self, options):
        config = _config(concurrent_downloads=2)
        options._format_var.set("m4a")
        options._quality_var.set("320kbps")
        options._subtitles_var.set(True)
        options._subtitle_lang_var.set("fr")
        options._split_chapters_var.set(True)

        options.save_settings(config)

        stored = {call.args[0]: call.args[1] for call in config.set.call_args_list}
        assert stored["format"] == "m4a"
        assert stored["quality"] == "320kbps"
        assert stored["subtitles"] is True
        assert stored["subtitle_lang"] == "fr"
        assert stored["split_chapters"] is True

    def test_invalid_rate_limit_is_stored_empty(self, options):
        config = _config(concurrent_downloads=2)
        options._rate_limit_var.set("3x")

        options.save_settings(config)

        stored = {call.args[0]: call.args[1] for call in config.set.call_args_list}
        assert stored["rate_limit"] == ""

    def test_valid_rate_limit_is_preserved(self, options):
        config = _config(concurrent_downloads=2)
        options._rate_limit_var.set("500K")

        options.save_settings(config)

        stored = {call.args[0]: call.args[1] for call in config.set.call_args_list}
        assert stored["rate_limit"] == "500K"

    def test_non_numeric_concurrent_keeps_saved_value(self, options):
        config = _config(concurrent_downloads=2)
        options._concurrent_var.set("3x")

        options.save_settings(config)

        stored = {call.args[0]: call.args[1] for call in config.set.call_args_list}
        assert stored["concurrent_downloads"] == 2

    def test_unreadable_rate_limit_variable_is_stored_empty(self, options):
        config = _config(concurrent_downloads=2)
        options._rate_limit_var = Mock()
        options._rate_limit_var.get.side_effect = tk.TclError("variable is gone")

        options.save_settings(config)

        stored = {call.args[0]: call.args[1] for call in config.set.call_args_list}
        assert stored["rate_limit"] == ""

    def test_failing_config_set_does_not_abort_remaining_keys(self, options):
        stored = {}

        def flaky_set(key, value):
            if key == "quality":
                raise ValueError("cannot store this key")
            stored[key] = value

        config = _config(concurrent_downloads=2)
        config.set.side_effect = flaky_set

        options.save_settings(config)

        assert config.set.call_count == len(SAVED_KEYS)
        assert set(stored) == SAVED_KEYS - {"quality"}
