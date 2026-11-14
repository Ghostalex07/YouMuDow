"""Shared pytest fixtures for YouMuDow tests."""

import gc
import threading
import time
import tkinter

import pytest

from youmudow.domain.enums import DownloadStatus
from youmudow.domain.models import DownloadOptions, Video

_WORKER_THREAD_NAME = "thumbnail-loader"
_JOIN_TIMEOUT_SECONDS = 2.0


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


def _live_worker_threads() -> list[threading.Thread]:
    return [
        thread
        for thread in threading.enumerate()
        if thread.name == _WORKER_THREAD_NAME and thread.is_alive()
    ]


@pytest.fixture(autouse=True)
def _no_leaked_thumbnail_workers():
    """Fail deterministically when a test leaves a thumbnail worker alive.

    A daemon worker that outlives its Tk root is the suspected cause of the
    intermittent interpreter abort (a daemon thread racing the garbage
    collector during shutdown). Turning the leak into a hard failure keeps the
    crash visible as a normal test error instead of killing the whole run.
    """
    yield
    deadline = time.monotonic() + _JOIN_TIMEOUT_SECONDS
    while _live_worker_threads() and time.monotonic() < deadline:
        time.sleep(0.01)
    leaked = _live_worker_threads()
    if leaked:
        pytest.fail(
            f"{len(leaked)} thumbnail worker thread(s) still alive after the test: "
            + ", ".join(thread.name for thread in leaked)
        )


@pytest.fixture(autouse=True)
def _collect_tk_garbage_on_main_thread():
    """Collect garbage on the main thread after every test.

    Tkinter objects must be destroyed by the thread that owns Tk. When the
    cyclic collector runs inside a daemon thread and frees a leftover
    ``tk.Tk``, Tcl panics and aborts the interpreter (``Fatal Python error:
    Aborted``), which is what killed the CI test jobs. Collecting here, on the
    main thread, keeps those destructors where Tcl expects them, and the check
    below turns a leaked root into a normal test failure.
    """
    yield
    gc.collect()
    leftover = tkinter._default_root
    if leftover is None:
        return
    try:
        alive = leftover.winfo_exists()
    except tkinter.TclError:
        return
    if alive:
        pytest.fail(
            "a test left a Tk root alive; destroy it in the fixture so the "
            "collector never frees Tk objects on a worker thread"
        )
