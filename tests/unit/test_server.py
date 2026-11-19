"""Tests for the headless HTTP server."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from youmudow.domain.enums import DownloadStatus
from youmudow.server import make_server
from youmudow.services.download_service import DownloadService


class FakeAdapter:
    def download(self, video, output_path, progress_callback=None, cancel_event=None):
        video.status = DownloadStatus.DONE
        return video


@pytest.fixture
def server(tmp_path):
    service = DownloadService(adapter=FakeAdapter(), default_output_path=tmp_path)
    httpd = make_server("127.0.0.1", 0, service, token="secret")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", service
    httpd.shutdown()
    httpd.server_close()
    service.stop()


def call(base, method, path, body=None, token="secret"):
    data = None if body is None else body if isinstance(body, bytes) else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=data, method=method)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def test_health_reports_the_version(server):
    base, _ = server
    status, payload = call(base, "GET", "/api/health")
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["version"]


def test_requests_without_the_token_are_rejected(server):
    base, _ = server
    status, _payload = call(base, "GET", "/api/health", token=None)
    assert status == 401


def test_enqueue_adds_to_the_shared_queue(server):
    base, _service = server
    status, payload = call(base, "POST", "/api/downloads", {"url": "https://x.test/a"})
    assert status == 202
    assert payload["queued"] == 1

    status, listing = call(base, "GET", "/api/downloads")
    assert status == 200
    assert [item["url"] for item in listing["queue"]] == ["https://x.test/a"]


def test_unsupported_url_is_rejected(server):
    base, _ = server
    status, payload = call(base, "POST", "/api/downloads", {"url": "not a url"})
    assert status == 400
    assert "url" in payload["error"].lower()


def test_unknown_format_is_rejected(server):
    base, _ = server
    status, payload = call(
        base, "POST", "/api/downloads", {"url": "https://x.test/a", "format": "wav9"}
    )
    assert status == 400
    assert "format" in payload["error"].lower()


def test_malformed_json_is_rejected(server):
    base, _ = server
    status, _payload = call(base, "POST", "/api/downloads", b"{not json")
    assert status == 400


def test_pause_and_resume(server):
    base, _service = server
    assert call(base, "POST", "/api/queue/pause")[0] == 200
    assert call(base, "GET", "/api/downloads")[1]["paused"] is True
    assert call(base, "POST", "/api/queue/resume")[0] == 200
    assert call(base, "GET", "/api/downloads")[1]["paused"] is False


def test_delete_removes_a_queued_entry(server):
    base, service = server
    call(base, "POST", "/api/downloads", {"url": "https://x.test/a"})
    call(base, "POST", "/api/downloads", {"url": "https://x.test/b"})
    first = service.queued_videos()[0]
    status, payload = call(base, "DELETE", f"/api/queue/{first.queue_id}")
    assert status == 200
    assert payload["removed"] is True
    assert [v.url for v in service.queued_videos()] == ["https://x.test/b"]


def test_delete_of_an_unknown_entry_is_a_404(server):
    base, _ = server
    status, _payload = call(base, "DELETE", "/api/queue/nope")
    assert status == 404


def test_unknown_route_is_a_404(server):
    base, _ = server
    assert call(base, "GET", "/api/nope")[0] == 404


def test_non_loopback_binds_require_a_token(tmp_path):
    service = DownloadService(adapter=FakeAdapter(), default_output_path=tmp_path)
    with pytest.raises(ValueError):
        make_server("0.0.0.0", 0, service, token=None)


def test_batch_endpoint_queues_and_skips(server):
    base, service = server
    status, payload = call(
        base,
        "POST",
        "/api/downloads/batch",
        {
            "urls": [
                "https://x.test/a",
                "https://x.test/b",
                "https://x.test/a",
                "not a url",
            ]
        },
    )
    assert status == 202
    assert payload["queued"] == 2
    assert payload["skipped"] == 1
    assert payload["rejected"] == ["not a url"]
    assert [v.url for v in service.queued_videos()] == ["https://x.test/a", "https://x.test/b"]


def test_batch_endpoint_rejects_a_missing_list(server):
    base, _ = server
    status, payload = call(base, "POST", "/api/downloads/batch", {"urls": "nope"})
    assert status == 400
    assert "urls" in payload["error"]
