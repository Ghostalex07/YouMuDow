"""Tests for centralized logging setup."""

import logging

import pytest


@pytest.fixture(autouse=True)
def _restore_logging_state():
    import youmudow.logging_config as module

    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    original_configured = module._configured

    yield

    module._configured = original_configured
    root.handlers = original_handlers
    root.setLevel(original_level)


class TestSetupLogging:
    def test_configures_root_logger(self):
        import youmudow.logging_config as module

        module._configured = False
        root = logging.getLogger()
        before = len(root.handlers)

        module.setup_logging()

        assert len(root.handlers) == before + 1
        assert module._configured is True

    def test_idempotent(self):
        import youmudow.logging_config as module

        module._configured = False
        module.setup_logging()
        handlers = list(logging.getLogger().handlers)

        module.setup_logging()
        assert logging.getLogger().handlers == handlers

    def test_creates_log_file(self, tmp_path):
        import youmudow.logging_config as module

        module._configured = False
        module.setup_logging(log_dir=tmp_path)
        assert (tmp_path / module.LOG_FILE_NAME).exists()

    def test_log_message_written_to_file(self, tmp_path, caplog):
        import youmudow.logging_config as module

        module._configured = False
        module.setup_logging(log_dir=tmp_path, level=logging.DEBUG)

        with caplog.at_level(logging.DEBUG):
            logging.getLogger("youmudow.test").info("hello from test")

        content = (tmp_path / module.LOG_FILE_NAME).read_text()
        assert "hello from test" in content
