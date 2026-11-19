"""Check GitHub for a newer YouMuDow release.

Deliberately read-only: it never replaces the running binary. Finding an update
only tells the UI to offer the release page, so a failed check or a corporate
proxy can never break the app.
"""

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

RELEASES_URL = "https://api.github.com/repos/Ghostalex07/YouMuDow/releases/latest"
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    url: str


def parse_version(value: str) -> tuple[int, int, int] | None:
    """Parse ``1.9.0`` / ``v1.10.2`` into a comparable tuple."""
    match = _VERSION.search(value or "")
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer(candidate: str, current: str) -> bool:
    newer = parse_version(candidate)
    installed = parse_version(current)
    if newer is None or installed is None:
        return False
    return newer > installed


def check_for_update(current_version: str, timeout: float = 5.0) -> ReleaseInfo | None:
    """Return the latest release when it is newer than ``current_version``."""
    request = urllib.request.Request(
        RELEASES_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "YouMuDow"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload: dict[str, Any] = json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.debug("Update check skipped: %s", exc)
        return None

    tag = str(payload.get("tag_name", ""))
    url = str(payload.get("html_url", "")) or RELEASES_URL
    if not url or not is_newer(tag, current_version):
        return None
    return ReleaseInfo(version=tag.lstrip("v"), url=url)
