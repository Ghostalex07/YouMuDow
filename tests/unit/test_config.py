"""Tests for AppConfig."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from youmudow.app.config import AppConfig
from youmudow.domain.models import DownloadOptions


class TestAppConfig:
    def test_default_values(self):
        cfg = AppConfig()
        assert cfg.get("format") == "mp3"
        assert cfg.get("quality") == "best"
        assert cfg.get("debug_mode") is False

    def test_set_and_get(self):
        cfg = AppConfig()
        cfg.set("format", "mp4")
        assert cfg.get("format") == "mp4"

    def test_window_geometry_property(self):
        cfg = AppConfig()
        cfg.window_geometry = "800x600+100+100"
        assert cfg.window_geometry == "800x600+100+100"

    def test_output_path_property(self):
        cfg = AppConfig()
        cfg.output_path = "/tmp/test"
        assert str(cfg.output_path) == "/tmp/test"

    def test_to_download_options(self):
        cfg = AppConfig()
        opts = cfg.to_download_options()
        assert isinstance(opts, DownloadOptions)
        assert opts.file_format == "mp3"

    def test_from_download_options(self):
        cfg = AppConfig()
        opts = DownloadOptions(file_format="mp4", quality="1080p")
        cfg.from_download_options(opts)
        assert cfg.get("format") == "mp4"
        assert cfg.get("quality") == "1080p"

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig()
            cfg.set("format", "flac")
            with (
                patch("youmudow.app.config.CONFIG_DIR", Path(tmp)),
                patch("youmudow.app.config.CONFIG_FILE", Path(tmp) / "config.json"),
            ):
                cfg.save()
                assert (Path(tmp) / "config.json").exists()

    def test_corrupted_config_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text("invalid json{{{")
            with patch("youmudow.app.config.CONFIG_FILE", config_file):
                cfg = AppConfig()
                assert cfg.get("format") == "mp3"

    def test_load_oserror_falls_back_to_defaults(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youmudow.app.config.CONFIG_FILE", Path(tmp)),
        ):
            cfg = AppConfig()
            assert cfg.get("format") == "mp3"

    def test_save_oserror_is_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocking = Path(tmp) / "blocking"
            blocking.write_text("not a directory")
            with patch("youmudow.app.config.CONFIG_DIR", blocking):
                cfg = AppConfig()
                cfg.set("format", "mp4")
                cfg.save()  # should not raise

    def test_get_str_returns_default_when_value_is_none(self):
        cfg = AppConfig()
        cfg.set("format", None)
        assert cfg.get_str("format", "mp3") == "mp3"

    def test_get_str_missing_key_returns_default(self):
        assert AppConfig().get_str("missing", "fallback") == "fallback"

    def test_add_search_prepends_and_dedups(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youmudow.app.config.CONFIG_FILE", Path(tmp) / "config.json"),
        ):
            cfg = AppConfig()
            cfg.add_search("second")
            cfg.add_search("first")
            cfg.add_search("second")
            assert cfg.get_search_history() == ["second", "first"]

    def test_add_search_truncates_to_ten(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youmudow.app.config.CONFIG_FILE", Path(tmp) / "config.json"),
        ):
            cfg = AppConfig()
            for i in range(12):
                cfg.add_search(f"query-{i}")
            assert len(cfg.get_search_history()) == 10
            assert cfg.get_search_history()[0] == "query-11"

    def test_get_search_history_returns_empty_for_non_list(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youmudow.app.config.CONFIG_FILE", Path(tmp) / "config.json"),
        ):
            cfg = AppConfig()
            cfg.set("search_history", "not-a-list")
            assert cfg.get_search_history() == []

    def test_search_history_entries_coerced_to_string(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("youmudow.app.config.CONFIG_FILE", Path(tmp) / "config.json"),
        ):
            cfg = AppConfig()
            cfg.set("search_history", [123, 456])
            assert cfg.get_search_history() == ["123", "456"]
