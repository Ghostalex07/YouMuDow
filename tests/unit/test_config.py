"""Tests for AppConfig."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from youmudow.app.config import AppConfig, DEFAULT_CONFIG, CONFIG_DIR, CONFIG_FILE
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
        assert opts.format == "mp3"

    def test_from_download_options(self):
        cfg = AppConfig()
        opts = DownloadOptions(format="mp4", quality="1080p")
        cfg.from_download_options(opts)
        assert cfg.get("format") == "mp4"
        assert cfg.get("quality") == "1080p"

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig()
            cfg.set("format", "flac")
            with patch("youmudow.app.config.CONFIG_DIR", Path(tmp)):
                with patch("youmudow.app.config.CONFIG_FILE", Path(tmp) / "config.json"):
                    cfg.save()
                    assert (Path(tmp) / "config.json").exists()

    def test_corrupted_config_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text("invalid json{{{")
            with patch("youmudow.app.config.CONFIG_FILE", config_file):
                cfg = AppConfig()
                assert cfg.get("format") == "mp3"
