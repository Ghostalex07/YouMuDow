"""Tests for the yt-dlp environment service."""

import time
from unittest.mock import Mock, patch


class TestDetectJsRuntime:
    def test_returns_none_when_no_runtime(self):
        from youmudow.services.environment_service import detect_js_runtime

        with patch(
            "youmudow.services.environment_service.shutil.which", return_value=None
        ) as which:
            assert detect_js_runtime() is None
            assert which.call_count == 5  # deno, node, quickjs, qjs, bun

    def test_returns_deno_when_present(self):
        from youmudow.services.environment_service import detect_js_runtime

        with patch(
            "youmudow.services.environment_service.shutil.which",
            side_effect=lambda name: f"/usr/bin/{name}" if name == "deno" else None,
        ):
            assert detect_js_runtime() == "deno"

    def test_returns_node_when_no_deno(self):
        from youmudow.services.environment_service import detect_js_runtime

        def which(name):
            return "/usr/bin/node" if name == "node" else None

        with patch("youmudow.services.environment_service.shutil.which", side_effect=which):
            assert detect_js_runtime() == "node"


class TestJsRuntimesFlag:
    def test_empty_when_no_runtime(self):
        from youmudow.services.environment_service import js_runtimes_flag

        with patch(
            "youmudow.services.environment_service.detect_js_runtime", return_value=None
        ):
            assert js_runtimes_flag() == []

    def test_empty_when_deno(self):
        from youmudow.services.environment_service import js_runtimes_flag

        with patch(
            "youmudow.services.environment_service.detect_js_runtime", return_value="deno"
        ):
            assert js_runtimes_flag() == []

    def test_node_requires_flag(self):
        from youmudow.services.environment_service import js_runtimes_flag

        with patch(
            "youmudow.services.environment_service.detect_js_runtime", return_value="node"
        ):
            assert js_runtimes_flag() == ["--js-runtimes", "node"]

    def test_quickjs_requires_flag(self):
        from youmudow.services.environment_service import js_runtimes_flag

        with patch(
            "youmudow.services.environment_service.detect_js_runtime", return_value="quickjs"
        ):
            assert js_runtimes_flag() == ["--js-runtimes", "quickjs"]

    def test_qjs_binary_maps_to_quickjs_runtime(self):
        from youmudow.services.environment_service import detect_js_runtime

        with patch("youmudow.services.environment_service.shutil.which") as which:
            which.side_effect = lambda name: "/usr/bin/qjs" if name == "qjs" else None
            assert detect_js_runtime() == "quickjs"


class TestIsEjsInstalled:
    def test_true_when_find_spec_returns(self):
        from youmudow.services.environment_service import is_ejs_installed

        with patch("youmudow.services.environment_service.importlib.util.find_spec") as spec:
            spec.return_value = object()
            assert is_ejs_installed() is True

    def test_false_when_missing(self):
        from youmudow.services.environment_service import is_ejs_installed

        with patch("youmudow.services.environment_service.importlib.util.find_spec") as spec:
            spec.return_value = None
            assert is_ejs_installed() is False


class TestClearYtdlpCache:
    def test_success(self):
        from youmudow.services.environment_service import clear_ytdlp_cache

        result = Mock()
        result.returncode = 0
        with patch("subprocess.run", return_value=result) as run:
            assert clear_ytdlp_cache() is True
            assert run.call_args[0][0] == ["yt-dlp", "--rm-cache-dir"]

    def test_failure(self):
        from youmudow.services.environment_service import clear_ytdlp_cache

        result = Mock()
        result.returncode = 1
        with patch("subprocess.run", return_value=result):
            assert clear_ytdlp_cache() is False

    def test_error_returns_false(self):
        from youmudow.services.environment_service import clear_ytdlp_cache

        with patch("subprocess.run", side_effect=OSError("boom")):
            assert clear_ytdlp_cache() is False


class TestInstallEjsScripts:
    def test_success_calls_on_success(self):
        from youmudow.services.environment_service import install_ejs_scripts

        result = Mock()
        result.returncode = 0
        on_success = Mock()
        on_error = Mock()
        with patch("subprocess.run", return_value=result):
            install_ejs_scripts(on_success, on_error)
            deadline = time.time() + 3
            while on_success.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_called_once()
        on_error.assert_not_called()

    def test_failure_calls_on_error(self):
        from youmudow.services.environment_service import install_ejs_scripts

        result = Mock()
        result.returncode = 1
        result.stderr = "pip failed"
        on_success = Mock()
        on_error = Mock()
        with patch("subprocess.run", return_value=result):
            install_ejs_scripts(on_success, on_error)
            deadline = time.time() + 3
            while on_error.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_not_called()
        on_error.assert_called_once()
        assert "pip failed" in on_error.call_args[0][0]

    def test_error_calls_on_error(self):
        from youmudow.services.environment_service import install_ejs_scripts

        on_success = Mock()
        on_error = Mock()
        with patch("subprocess.run", side_effect=OSError("boom")):
            install_ejs_scripts(on_success, on_error)
            deadline = time.time() + 3
            while on_error.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_not_called()
        on_error.assert_called_once()


class TestRepairYoutubeEnvironment:
    def test_success_calls_on_success_with_cache_note(self):
        from youmudow.services.environment_service import repair_youtube_environment

        result = Mock()
        result.returncode = 0
        on_success = Mock()
        on_error = Mock()
        with (
            patch("subprocess.run", return_value=result),
            patch(
                "youmudow.services.environment_service.clear_ytdlp_cache", return_value=True
            ),
        ):
            repair_youtube_environment(on_success, on_error)
            deadline = time.time() + 3
            while on_success.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_called_once()
        assert "cache cleared" in on_success.call_args[0][0]
        on_error.assert_not_called()

    def test_pip_failure_calls_on_error(self):
        from youmudow.services.environment_service import repair_youtube_environment

        result = Mock()
        result.returncode = 1
        result.stderr = "nope"
        on_success = Mock()
        on_error = Mock()
        with patch("subprocess.run", return_value=result):
            repair_youtube_environment(on_success, on_error)
            deadline = time.time() + 3
            while on_error.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
        on_success.assert_not_called()
        on_error.assert_called_once()


class TestYoutubeEnvironmentStatus:
    def test_reports_fields(self):
        from youmudow.services.environment_service import youtube_environment_status

        status = {
            "yt_dlp_installed": True,
            "js_runtime": "node",
            "ejs_installed": False,
        }
        with (
            patch(
                "youmudow.services.environment_service.shutil.which",
                side_effect=lambda name: "/usr/bin/yt-dlp" if name == "yt-dlp" else "",
            ),
            patch(
                "youmudow.services.environment_service.detect_js_runtime",
                return_value="node",
            ),
            patch(
                "youmudow.services.environment_service.is_ejs_installed",
                return_value=False,
            ),
        ):
            assert youtube_environment_status() == status