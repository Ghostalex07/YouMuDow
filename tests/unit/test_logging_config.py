"""Tests for the logging setup."""

import logging

import pytest

from youmudow import logging_config


@pytest.fixture
def reset_logging():
    previous = logging_config._configured
    logging_config._configured = False
    root = logging.getLogger()
    saved = list(root.handlers)
    root.handlers.clear()
    yield root
    for handler in list(root.handlers):
        handler.close()
    root.handlers.clear()
    root.handlers.extend(saved)
    logging_config._configured = previous


def test_log_file_rotates_instead_of_growing_forever(reset_logging, tmp_path):
    logging_config.setup_logging(log_dir=tmp_path, level=logging.INFO)

    handlers = [
        h for h in reset_logging.handlers if isinstance(h, logging_config.RotatingFileHandler)
    ]
    assert len(handlers) == 1
    assert handlers[0].maxBytes == 5 * 1024 * 1024
    assert handlers[0].backupCount == 3


def test_the_log_file_is_written_and_rotated(reset_logging, tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_MAX_BYTES", 512)
    logging_config.setup_logging(log_dir=tmp_path, level=logging.INFO)

    logger = logging.getLogger("youmudow.rotation-test")
    for _ in range(40):
        logger.info("x" * 60)

    files = sorted(p.name for p in tmp_path.iterdir())
    assert "youmudow.log" in files
    assert any(name.startswith("youmudow.log.") for name in files)
