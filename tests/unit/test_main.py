"""Tests for the application entry point."""

import logging
import runpy
from pathlib import Path
from unittest.mock import Mock, patch

from youmudow import main as main_module


class TestMain:
    def test_wires_config_controller_and_window(self, tmp_path: Path) -> None:
        config = Mock()
        config.get.return_value = False
        config.output_path = tmp_path / "downloads"
        controller = Mock()
        window = Mock()

        with (
            patch.object(main_module, "AppConfig", return_value=config),
            patch.object(main_module, "setup_logging") as setup_logging,
            patch.object(main_module, "AppController", return_value=controller),
            patch.object(main_module, "MainWindow", return_value=window) as window_cls,
        ):
            main_module.main()

        setup_logging.assert_called_once_with(log_dir=main_module.CONFIG_DIR, level=logging.INFO)
        controller.set_output_path.assert_called_once_with(config.output_path)
        assert config.output_path.is_dir()
        window_cls.assert_called_once_with(controller, debug_mode=False, config=config)
        window.run.assert_called_once_with()

    def test_debug_mode_sets_debug_log_level(self, tmp_path: Path) -> None:
        config = Mock()
        config.get.return_value = True
        config.output_path = tmp_path / "downloads"

        with (
            patch.object(main_module, "AppConfig", return_value=config),
            patch.object(main_module, "setup_logging") as setup_logging,
            patch.object(main_module, "AppController"),
            patch.object(main_module, "MainWindow"),
        ):
            main_module.main()

        setup_logging.assert_called_once_with(log_dir=main_module.CONFIG_DIR, level=logging.DEBUG)


class TestMainModule:
    def test_python_m_youmudow_runs_main(self) -> None:
        """``python -m youmudow`` must reach the same entry point."""
        with patch("youmudow.main.main") as entry_point:
            runpy.run_module("youmudow", run_name="__main__")

        entry_point.assert_called_once_with()

    def test_module_exposes_main(self) -> None:
        from youmudow import __main__ as package_main

        assert package_main.main is main_module.main
