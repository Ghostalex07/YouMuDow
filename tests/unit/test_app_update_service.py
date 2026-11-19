"""Tests for the GitHub release check."""

import io
import json
import urllib.error
from unittest.mock import patch

from youmudow.services.app_update_service import (
    check_for_update,
    is_newer,
    parse_version,
)


def test_parse_version_accepts_prefixes():
    assert parse_version("v1.10.2") == (1, 10, 2)
    assert parse_version("1.9.0") == (1, 9, 0)
    assert parse_version("nightly") is None


def test_is_newer_compares_numerically():
    assert is_newer("1.10.0", "1.9.0") is True
    assert is_newer("v1.9.1", "1.9.0") is True
    assert is_newer("1.9.0", "1.9.0") is False
    assert is_newer("1.8.9", "1.9.0") is False


def test_is_newer_ignores_unparseable_versions():
    assert is_newer("nightly", "1.9.0") is False
    assert is_newer("2.0.0", "dev") is False


def _response(payload):
    return io.BytesIO(json.dumps(payload).encode())


def test_check_returns_the_newer_release():
    with patch(
        "urllib.request.urlopen",
        return_value=_response(
            {"tag_name": "v1.10.0", "html_url": "https://github.com/x/y/releases/tag/v1.10.0"}
        ),
    ):
        info = check_for_update("1.9.0")
    assert info is not None
    assert info.version == "1.10.0"
    assert info.url.endswith("v1.10.0")


def test_check_returns_none_when_up_to_date():
    with patch(
        "urllib.request.urlopen",
        return_value=_response(
            {"tag_name": "v1.9.0", "html_url": "https://github.com/x/y/releases/tag/v1.9.0"}
        ),
    ):
        assert check_for_update("1.9.0") is None


def test_check_survives_a_network_error():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
        assert check_for_update("1.9.0") is None


def test_check_survives_a_broken_payload():
    with patch("urllib.request.urlopen", return_value=io.BytesIO(b"not json")):
        assert check_for_update("1.9.0") is None
