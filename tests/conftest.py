"""Shared pytest fixtures for YouMuDow tests."""

import pytest

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Reset the global EventBus between tests to avoid state leakage."""
    from youmudow.app.events import EventBus

    EventBus.reset()
    yield
    EventBus.reset()


@pytest.fixture
def sample_options() -> DownloadOptions:
    """A standard DownloadOptions instance for testing."""
    return DownloadOptions(
        file_format="mp3",
        quality="best",
        subtitles=False,
        subtitle_lang="en",
        embed_subtitles=False,
        use_cookies=False,
    )


@pytest.fixture
def sample_video(sample_options: DownloadOptions) -> Video:
    """A standard Video instance for testing."""
    return Video(
        title="Test Video",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        uploader="Test Channel",
        duration=213,
        thumbnail="https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg",
        status=DownloadStatus.READY,
        options=sample_options,
    )
