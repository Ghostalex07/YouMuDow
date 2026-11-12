"""Subprocess concerns for the yt-dlp adapter.

This module owns the long-running download process: spawning it, streaming its
output, enforcing the inactivity timeout and tearing the whole process group
down on cancel. It knows nothing about download bookkeeping.
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from youmudow.adapters.ytdlp_parsing import parse_progress
from youmudow.domain.exceptions import YtDlpNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

    from youmudow.adapters.ytdlp_adapter import YtdlpConfig
    from youmudow.domain.models import Video

logger = logging.getLogger(__name__)

DESTINATION_RE = re.compile(r"\[download\]\s+Destination:\s+(\S+)")
ALREADY_DOWNLOADED_RE = re.compile(r"\[download\]\s+(\S+)\s+has already been downloaded")

# Return code used to report "the process was killed for inactivity".
TIMEOUT_RETURNCODE = -2


def _emit(log: Callable[[str], None] | None, message: str) -> None:
    """Send ``message`` to the log callback, if one was given."""
    if log is not None:
        log(message)


def signal_process_group(process: subprocess.Popen, sig: int) -> None:
    """Send ``sig`` to yt-dlp's whole process group.

    The child is spawned with ``start_new_session=True``, so its group also
    holds the ffmpeg helpers yt-dlp spawns; signalling yt-dlp alone leaves
    ffmpeg muxing into the output directory after a cancel. Falls back to
    signalling yt-dlp itself when the group cannot be targeted (the group
    may already be gone, or the platform has no process groups).
    """
    try:
        os.killpg(os.getpgid(process.pid), sig)
        return
    except (AttributeError, ProcessLookupError, PermissionError):
        logger.debug("Process group unavailable, signalling yt-dlp directly")
    if sig == signal.SIGKILL:
        process.kill()
    else:
        process.terminate()


def terminate_process_group(process: subprocess.Popen) -> None:
    """Terminate the process group, escalating to SIGKILL after a grace period."""
    signal_process_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        signal_process_group(process, signal.SIGKILL)


def run_capture(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Run yt-dlp once and capture its complete output.

    Used for the short-lived search, metadata and playlist queries, which are
    read as a whole rather than streamed.
    """
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_process(
    args: list[str],
    output_path: Path,
    video: Video,
    cancel_event: threading.Event | None,
    progress_callback: Callable[[float, str], None] | None,
    config: YtdlpConfig,
    log: Callable[[str], None] | None = None,
) -> tuple[int, list[str], list[str], list[str]]:
    """Run yt-dlp and stream its output.

    Returns a ``(returncode, error_lines, destinations, already_downloaded)``
    tuple; the destinations are the output files yt-dlp reported for this run,
    and ``already_downloaded`` lists the files yt-dlp reported as already
    present (a pre-existing file explicitly attributed to this run). The
    return code is ``TIMEOUT_RETURNCODE`` when the process was killed for
    inactivity.
    """
    error_lines: list[str] = []
    destinations: list[str] = []
    already_downloaded: list[str] = []
    output_lock = threading.Lock()
    # Set by the reader thread for every line yt-dlp writes, so the main
    # loop can tell an active download from a silent/hung one.
    activity = threading.Event()

    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(output_path),
            start_new_session=True,
        )
    except FileNotFoundError as e:
        raise YtDlpNotFoundError(
            "yt-dlp binary not found. Install it with: pip install yt-dlp"
        ) from e

    def read_output() -> None:
        stdout = process.stdout
        if stdout is None:
            return
        try:
            for line in stdout:
                if cancel_event and cancel_event.is_set():
                    signal_process_group(process, signal.SIGTERM)
                    break
                if line:
                    activity.set()
                    stripped = line.strip()
                    with output_lock:
                        if "error" in stripped.lower() or "warning" in stripped.lower():
                            error_lines.append(stripped)
                    dest_match = DESTINATION_RE.search(stripped)
                    if dest_match:
                        destinations.append(dest_match.group(1))
                    else:
                        already_match = ALREADY_DOWNLOADED_RE.search(stripped)
                        if already_match:
                            destinations.append(already_match.group(1))
                            already_downloaded.append(already_match.group(1))
                    _emit(log, stripped)
                    if progress_callback:
                        info = parse_progress(stripped)
                        if info:
                            video.progress = info.progress
                            progress_callback(info.progress, info.speed)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            logger.debug("Output reader stopped for %s: %s", video.url, e)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    timeout_reached = False
    try:
        if cancel_event is None:
            process.wait(timeout=config.download_timeout)
        else:
            deadline = time.monotonic() + config.download_timeout
            while process.poll() is None:
                if cancel_event.is_set():
                    _emit(log, "[CANCEL] Cancelled, terminating process")
                    terminate_process_group(process)
                    break
                # download_timeout is an inactivity budget: every line
                # yt-dlp writes pushes the deadline back, so a download that
                # is still reporting progress is never killed.
                activity.clear()
                if activity.wait(timeout=0.1):
                    deadline = time.monotonic() + config.download_timeout
                elif time.monotonic() >= deadline:
                    _emit(log, "[ERROR] Download timed out")
                    terminate_process_group(process)
                    timeout_reached = True
                    break
    except subprocess.TimeoutExpired:
        _emit(log, "[ERROR] Download timed out")
        signal_process_group(process, signal.SIGKILL)
        timeout_reached = True
    finally:
        if process.poll() is None:
            terminate_process_group(process)
        # Close the read end from the main thread: this forces the reader to
        # hit EOF even if the process died without closing stdout, so the
        # reader thread cannot stay alive blocked on readline().
        stdout = process.stdout
        if stdout is not None:
            try:
                stdout.close()
            except OSError:
                pass

    reader.join(timeout=2)
    if reader.is_alive():
        logger.warning("Output reader thread still alive for %s", video.url)

    if timeout_reached:
        return TIMEOUT_RETURNCODE, error_lines, destinations, already_downloaded
    return process.returncode, error_lines, destinations, already_downloaded
