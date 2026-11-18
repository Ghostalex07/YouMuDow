import os
import platform
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("tkinter")

if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
    collect_ignore_glob = ["*.py"]

from youmudow.app.config import AppConfig
from youmudow.app.controller import AppController
from youmudow.domain.enums import DownloadStatus
from youmudow.services.download_service import DownloadService
from youmudow.services.search_service import SearchService
from youmudow.ui.window import MainWindow


class FakeSearchAdapter:
    def __init__(self, results=None, playlist=None, metadata=None):
        self.results = list(results or [])
        self.playlist = list(playlist or [])
        self.metadata = metadata
        self.queries = []
        self.log_callback = None

    def set_log_callback(self, callback):
        self.log_callback = callback

    def search(self, query, limit=10):
        self.queries.append(query)
        return self.results[:limit]

    def get_metadata(self, url):
        return self.metadata

    def get_playlist_videos(self, url, limit=50):
        return self.playlist[:limit]


class FakeDownloadAdapter:
    def __init__(self):
        self.downloaded = []
        self.fail_urls = set()
        self.progress_steps = []
        self.log_callback = None

    def set_log_callback(self, callback):
        self.log_callback = callback

    def download(self, video, output_path, progress_callback=None, cancel_event=None):
        if video.url in self.fail_urls:
            video.status = DownloadStatus.ERROR
            video.error_message = "boom"
            return video
        if progress_callback is not None:
            self.progress_steps.append(50.0)
            progress_callback(50.0, "1.0MiB/s")
        video.status = DownloadStatus.DONE
        video.path = str(output_path / f"{video.title}.{video.options.file_format}")
        with open(video.path, "w", encoding="utf-8") as f:
            f.write("fake")
        self.downloaded.append(video)
        return video


def pump(window, predicate, timeout=3.0):
    """Run the real Tk main loop until predicate is true.

    The app schedules callbacks with `after()` from worker threads, which only
    works while the main thread is inside `mainloop()`; `update()` in a loop
    makes Tk drop them with "main thread is not in main loop".
    """
    root = window._root
    deadline = time.monotonic() + timeout
    state = {"settled": False}

    def check():
        if predicate() or time.monotonic() > deadline:
            state["settled"] = predicate()
            root.quit()
        else:
            root.after(10, check)

    root.after(10, check)
    root.mainloop()
    if not state["settled"]:
        raise AssertionError("timed out waiting for the UI to settle")


def build_stack(tmp_path, monkeypatch, run_startup_checks=False):
    monkeypatch.setattr("youmudow.app.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("youmudow.app.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    config = AppConfig()

    search_adapter = FakeSearchAdapter()
    download_adapter = FakeDownloadAdapter()
    search = SearchService(adapter=search_adapter)
    downloads = DownloadService(adapter=download_adapter, default_output_path=tmp_path)
    controller = AppController(search_service=search, download_service=downloads, config=config)
    window = MainWindow(
        controller=controller,
        config=config,
        run_startup_checks=run_startup_checks,
    )
    return SimpleNamespace(
        window=window,
        controller=controller,
        search=search,
        adapter=search_adapter,
        download_adapter=download_adapter,
        downloads=downloads,
        config=config,
    )


@pytest.fixture
def stack(tmp_path, monkeypatch):
    built = build_stack(tmp_path, monkeypatch)
    try:
        yield built
    finally:
        built.window.destroy()
        built.downloads.stop()


@pytest.fixture
def stack_factory(tmp_path, monkeypatch):
    built = []

    def make(run_startup_checks=False):
        namespace = build_stack(tmp_path, monkeypatch, run_startup_checks)
        built.append(namespace)
        return namespace

    try:
        yield make
    finally:
        for namespace in built:
            namespace.window.destroy()
            namespace.downloads.stop()
