"""Tests for AppConfig."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from youmudow.app.config import AppConfig
from youmudow.domain.models import DownloadOptions


@pytest.fixture(autouse=True)
def _isolated_config_file(tmp_path):
    """Keep every AppConfig() in this module off the real user config file.

    Without this, tests that only assert defaults silently read
    ~/.config/youmudow/config.json and fail depending on its contents.
    """
    with (
        patch("youmudow.app.config.CONFIG_DIR", tmp_path),
        patch("youmudow.app.config.CONFIG_FILE", tmp_path / "config.json"),
    ):
        yield


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

    def test_corrupted_config_is_preserved_as_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text("invalid json{{{", encoding="utf-8")
            with patch("youmudow.app.config.CONFIG_FILE", config_file):
                cfg = AppConfig()
            assert cfg.get("format") == "mp3"
            backup = config_file.with_suffix(".json.corrupt")
            assert backup.exists()
            assert backup.read_text(encoding="utf-8") == "invalid json{{{"
            assert not config_file.exists()

    def test_non_dict_json_root_falls_back_to_defaults(self):
        for payload in ("[]", '"x"', "5"):
            with tempfile.TemporaryDirectory() as tmp:
                config_file = Path(tmp) / "config.json"
                config_file.write_text(payload, encoding="utf-8")
                with patch("youmudow.app.config.CONFIG_FILE", config_file):
                    cfg = AppConfig()
                assert cfg.get("format") == "mp3"
                assert cfg.get("quality") == "best"
                assert config_file.with_suffix(".json.corrupt").exists()

    def test_non_utf8_config_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_bytes(b'{"format": "mp4", "output_path": "\xff\xfe"}')
            with patch("youmudow.app.config.CONFIG_FILE", config_file):
                cfg = AppConfig()
                assert cfg.get("format") == "mp3"
            backup = config_file.with_suffix(".json.corrupt")
            assert backup.exists()
            assert backup.read_bytes() == b'{"format": "mp4", "output_path": "\xff\xfe"}'

    def test_save_is_atomic_and_leaves_no_tmp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            with (
                patch("youmudow.app.config.CONFIG_DIR", Path(tmp)),
                patch("youmudow.app.config.CONFIG_FILE", config_file),
            ):
                cfg = AppConfig()
                cfg.set("format", "flac")
                cfg.save()
            assert list(Path(tmp).glob("*.tmp")) == []
            assert list(Path(tmp).iterdir()) == [config_file]

    def test_failed_save_leaves_no_tmp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            original = json.dumps({"format": "mp3"}, indent=2)
            config_file.write_text(original, encoding="utf-8")
            with (
                patch("youmudow.app.config.CONFIG_DIR", Path(tmp)),
                patch("youmudow.app.config.CONFIG_FILE", config_file),
                patch("youmudow.app.config.os.replace", side_effect=OSError("no space")),
            ):
                cfg = AppConfig()
                cfg.set("format", "flac")
                cfg.save()
            assert list(Path(tmp).glob("*.tmp")) == []
            assert config_file.read_text(encoding="utf-8") == original

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
