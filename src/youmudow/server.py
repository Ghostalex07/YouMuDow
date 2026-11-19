"""Headless HTTP server that feeds the shared download queue.

The server is a thin JSON layer over :class:`DownloadService`: the same queue,
the same SQLite library and the same event contract as the desktop app, so a
download started from a phone shows up in the window and vice versa.
"""

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from youmudow import __version__
from youmudow.app.config import AppConfig
from youmudow.domain.models import DownloadOptions, Video
from youmudow.domain.validators import (
    SUPPORTED_FORMATS,
    SUPPORTED_QUALITIES,
    is_supported_url,
)
from youmudow.services.download_service import DownloadService

logger = logging.getLogger(__name__)

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_PORT = 8765


def _video_summary(video: Video) -> dict[str, object]:
    return {
        "id": str(video.queue_id) if video.queue_id is not None else None,
        "title": video.title,
        "url": video.url,
        "status": video.status.name,
        "progress": round(float(video.progress or 0.0), 1),
    }


class _Handler(BaseHTTPRequestHandler):
    server: "DownloadHTTPServer"

    def log_message(self, fmt: str, *args: object) -> None:
        logger.debug("http %s - %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    def _authorized(self) -> bool:
        token = self.server.token
        if token is None:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {token}"

    def _respond(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0:
            return None
        try:
            parsed = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _dispatch(self, method: str) -> None:
        if not self._authorized():
            self._respond(HTTPStatus.UNAUTHORIZED, {"error": "missing or invalid token"})
            return

        path = urlparse(self.path).path.rstrip("/") or "/"
        service = self.server.service

        if method == "GET" and path == "/api/health":
            self._respond(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "version": __version__,
                    "queued": service.queue_size,
                    "active": service.active_count,
                    "paused": service.is_paused,
                },
            )
            return

        if method == "GET" and path == "/api/downloads":
            self._respond(
                HTTPStatus.OK,
                {
                    "queue": [_video_summary(v) for v in service.queued_videos()],
                    "active": [_video_summary(v) for v in service.active_videos()],
                    "running": service.is_running,
                    "paused": service.is_paused,
                },
            )
            return

        if method == "POST" and path == "/api/downloads/batch":
            self._enqueue_batch()
            return

        if method == "POST" and path == "/api/downloads":
            self._enqueue()
            return

        if method == "POST" and path in ("/api/queue/pause", "/api/queue/resume"):
            if path.endswith("pause"):
                service.pause()
            else:
                service.resume()
            self._respond(HTTPStatus.OK, {"paused": service.is_paused})
            return

        if method == "DELETE" and path.startswith("/api/queue/"):
            self._delete(path.rsplit("/", 1)[-1])
            return

        self._respond(HTTPStatus.NOT_FOUND, {"error": "unknown route"})

    def _enqueue(self) -> None:
        body = self._read_body()
        if body is None:
            self._respond(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON object"})
            return

        url = str(body.get("url") or "").strip()
        if not is_supported_url(url):
            self._respond(HTTPStatus.BAD_REQUEST, {"error": "unsupported url"})
            return

        options = DownloadOptions()
        if fmt := body.get("format"):
            if fmt not in SUPPORTED_FORMATS:
                self._respond(HTTPStatus.BAD_REQUEST, {"error": f"unknown format: {fmt}"})
                return
            options.file_format = str(fmt)
        if quality := body.get("quality"):
            if quality not in SUPPORTED_QUALITIES:
                self._respond(HTTPStatus.BAD_REQUEST, {"error": f"unknown quality: {quality}"})
                return
            options.quality = str(quality)

        video = Video(title=url, url=url, options=options)
        self.server.service.add_to_queue(video)
        self._respond(
            HTTPStatus.ACCEPTED,
            {"id": str(video.queue_id), "queued": self.server.service.queue_size},
        )

    def _enqueue_batch(self) -> None:
        body = self._read_body()
        if body is None or not isinstance(body.get("urls"), list):
            self._respond(
                HTTPStatus.BAD_REQUEST,
                {"error": "expected a JSON object with a urls list"},
            )
            return

        service = self.server.service
        known = {v.url for v in service.queued_videos()} | {v.url for v in service.active_videos()}
        queued = skipped = 0
        rejected: list[str] = []
        urls = body["urls"]
        assert isinstance(urls, list)
        for raw in urls:
            url = str(raw or "").strip()
            if not is_supported_url(url):
                rejected.append(url)
                continue
            if url in known:
                skipped += 1
                continue
            known.add(url)
            service.add_to_queue(Video(title=url, url=url, options=DownloadOptions()))
            queued += 1
        self._respond(
            HTTPStatus.ACCEPTED,
            {"queued": queued, "skipped": skipped, "rejected": rejected},
        )

    def _delete(self, entry_id: str) -> None:
        service = self.server.service
        for video in service.queued_videos():
            if str(video.queue_id) == entry_id:
                service.cancel_video(video)
                self._respond(HTTPStatus.OK, {"removed": True})
                return
        self._respond(HTTPStatus.NOT_FOUND, {"error": "no queued entry with that id"})


class DownloadHTTPServer(ThreadingHTTPServer):
    """Threading server carrying the service and the optional token."""

    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        service: DownloadService,
        token: str | None,
    ) -> None:
        super().__init__(address, _Handler)
        self.service = service
        self.token = token


def make_server(
    host: str,
    port: int,
    service: DownloadService,
    token: str | None = None,
) -> DownloadHTTPServer:
    """Build (but do not start) the server.

    Exposing the queue outside the machine without a token would let anyone on
    the network download into the user's folder, so that combination is refused.
    """
    if host not in LOOPBACK_HOSTS and not token:
        raise ValueError("a token is required when the server listens beyond localhost")
    return DownloadHTTPServer((host, port), service, token)


def serve(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    token: str | None = None,
    output: Path | None = None,
    config: AppConfig | None = None,
) -> int:
    """Run the server until Ctrl-C. Returns a process exit code."""
    if host not in LOOPBACK_HOSTS and not token:
        logger.error("Refusing to listen on %s without --token", host)
        return 2

    config = config or AppConfig()
    service = DownloadService(
        default_output_path=output or config.output_path,
        max_concurrent=1,
        max_retries=int(config.get("max_retries", 2)),
    )
    service.set_log_callback(lambda line: print(line, flush=True))
    restored = service.restore_queue()
    if restored:
        logger.info("Restored %s download(s) from the saved queue", restored)
    service.start()

    httpd = make_server(host, port, service, token)
    logger.info("Listening on http://%s:%s", host, httpd.server_address[1])
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        httpd.server_close()
        service.stop()
    return 0
