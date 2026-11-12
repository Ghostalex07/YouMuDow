"""Command-line argument builders for the yt-dlp subprocess.

Every function here is a pure transformation from a ``YtdlpConfig`` (plus,
optionally, a ``Video``) into a list of CLI tokens: no subprocess is spawned
and nothing is written to disk. The only filesystem facts consulted are
whether a cookies file or browser profile exists, because the cookie flags
depend on it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from youmudow.adapters.browser_profiles import check_browser_profile, get_fallback_browser
from youmudow.domain.validators import AUDIO_FORMATS

if TYPE_CHECKING:
    from collections.abc import Callable

    from youmudow.adapters.ytdlp_adapter import YtdlpConfig
    from youmudow.domain.models import Video

THUMBNAIL_EMBED_FORMATS: frozenset[str] = frozenset({"mp3", "m4a", "opus"})

VIDEO_QUALITY_SELECTORS: dict[str, str] = {
    "1080p": "bestvideo[height<=1080]+bestaudio/best",
    "720p": "bestvideo[height<=720]+bestaudio/best",
    "480p": "bestvideo[height<=480]+bestaudio/best",
    "360p": "bestvideo[height<=360]+bestaudio/best",
}

AUDIO_QUALITY_MAP: dict[str, str] = {
    "320kbps": "0",
    "256kbps": "1",
    "192kbps": "2",
    "128kbps": "3",
    "96kbps": "4",
    "64kbps": "5",
}

# Profile names that mean "just use the browser's default profile", which
# yt-dlp must not be told explicitly.
_DEFAULT_PROFILE_NAMES: tuple[str, ...] = ("default", "main")

# Fields printed for every entry of a search or playlist listing.
FLAT_PRINT_TEMPLATE = "%(url)s | %(title)s | %(uploader)s | %(duration)s"


def _emit(log: Callable[[str], None] | None, message: str) -> None:
    """Send ``message`` to the log callback, if one was given."""
    if log is not None:
        log(message)


def _has_explicit_profile(profile: str | None) -> bool:
    """Return whether ``profile`` names a non-default browser profile."""
    if not profile:
        return False
    return profile.lower() not in _DEFAULT_PROFILE_NAMES


def _browser_cookie_args(
    browser: str,
    profile: str | None,
    log: Callable[[str], None] | None,
) -> list[str]:
    """Build ``--cookies-from-browser`` arguments, falling back on absence.

    A missing browser is logged and replaced by the first other installed
    browser; the caller's ``DownloadOptions`` are never mutated.
    """
    browser = browser.lower()
    exists, message = check_browser_profile(browser)
    if not exists:
        _emit(log, f"[AUTH] {message}")
        fallback = get_fallback_browser()
        if fallback and fallback != browser:
            _emit(log, f"[AUTH] Falling back to {fallback.capitalize()}")
            browser = fallback
            profile = None

    cookie_arg = browser
    if _has_explicit_profile(profile):
        cookie_arg = f"{browser}:{profile}"
    profile_msg = f" ({profile})" if _has_explicit_profile(profile) else ""
    _emit(log, f"[AUTH] Using {browser.capitalize()}{profile_msg} cookies")
    return ["--cookies-from-browser", cookie_arg]


def _cookies_file_args(
    cookies_file: str,
    log: Callable[[str], None] | None,
) -> list[str]:
    """Build ``--cookies`` arguments for a Netscape-format cookies file."""
    cookie_path = Path(cookies_file)
    if not cookie_path.exists():
        _emit(log, f"[WARNING] Cookies file not found: {cookies_file}")
        return []
    _emit(log, "[AUTH] Using cookies file")
    return ["--cookies", str(cookie_path)]


def _cookie_args(
    config: YtdlpConfig,
    video: Video | None,
    skip_cookies: bool,
    log: Callable[[str], None] | None,
) -> list[str]:
    """Build the cookie flags for a run, if any are needed."""
    if skip_cookies:
        return []
    opts = video.options if video is not None else None
    if opts is not None:
        # A per-video request wins outright: the config-level cookies file is
        # only used when the video did not ask for cookies at all.
        if not opts.use_cookies:
            return []
        if opts.cookies_from_browser:
            return _browser_cookie_args(opts.cookies_from_browser, opts.cookies_profile, log)
        if opts.cookies_file:
            return _cookies_file_args(opts.cookies_file, log)
        return []
    if config.cookies_file:
        return ["--cookies", config.cookies_file]
    return []


def build_base_args(
    config: YtdlpConfig,
    video: Video | None = None,
    skip_cookies: bool = False,
    log: Callable[[str], None] | None = None,
) -> list[str]:
    """Build the yt-dlp arguments shared by every command.

    Covers the binary name, certificate handling, ffmpeg/user-agent overrides
    and cookie authentication. ``skip_cookies`` suppresses every cookie flag,
    which the adapter uses to retry a failed browser-cookie download.
    """
    args = ["yt-dlp"]
    # YouTube needs an external JS runtime to sign download URLs. yt-dlp
    # only enables deno by default; node/quickjs must be requested with an
    # explicit flag or the download fails with HTTP Error 403 Forbidden.
    # Imported lazily to avoid a circular import with the services package.
    from youmudow.services.environment_service import js_runtimes_flag

    args.extend(js_runtimes_flag())
    if not config.verify_certificates:
        args.append("--no-check-certificate")

    if config.ffmpeg_location:
        args.extend(["--ffmpeg-location", config.ffmpeg_location])
    if config.user_agent:
        args.extend(["--user-agent", config.user_agent])

    args.extend(_cookie_args(config, video, skip_cookies, log))
    return args


def build_download_args(
    config: YtdlpConfig,
    video: Video,
    skip_cookies: bool = False,
    log: Callable[[str], None] | None = None,
) -> list[str]:
    """Build the full yt-dlp command line for downloading ``video``."""
    args = build_base_args(config, video, skip_cookies, log)

    opts = video.options
    args.extend(
        [
            "-f",
            get_format_selector(opts.file_format, opts.quality),
            "-o",
            str(config.output_template),
        ]
    )

    if opts.file_format in AUDIO_FORMATS:
        args.extend(
            [
                "--extract-audio",
                "--audio-format",
                opts.file_format,
                "--audio-quality",
                get_audio_quality(opts.quality),
            ]
        )

    if config.embed_metadata:
        args.append("--embed-metadata")

    if config.embed_thumbnail and opts.file_format in THUMBNAIL_EMBED_FORMATS:
        args.append("--embed-thumbnail")

    if config.add_chapters:
        args.append("--embed-chapters")

    if opts.subtitles:
        args.extend(["--write-subs", "--sub-langs", opts.subtitle_lang])
        if opts.embed_subtitles:
            args.append("--embed-subs")
    elif config.embed_subs:
        args.extend(["--write-subs", "--embed-subs"])

    if opts.rate_limit:
        args.extend(["--limit-rate", opts.rate_limit])

    if opts.split_chapters:
        args.append("--split-chapters")

    if config.parse_metadata:
        args.extend(["--parse-metadata", config.parse_metadata])

    if config.metadata_from_title:
        args.extend(["--metadata-from-title", config.metadata_from_title])

    args.append(video.url)

    return args


def build_flat_playlist_args(
    config: YtdlpConfig,
    target: str,
    playlist_end: int | None = None,
    log: Callable[[str], None] | None = None,
) -> list[str]:
    """Build a ``--flat-playlist --print`` listing command.

    ``target`` is a search expression (``ytsearchN:query``) or a playlist URL;
    ``playlist_end`` limits how many entries yt-dlp extracts. No download
    happens, so no download-specific flags are added.
    """
    args = build_base_args(config, None, False, log)
    args.append("--flat-playlist")
    if playlist_end is not None:
        args.extend(["--playlist-end", str(playlist_end)])
    args.extend(["--print", FLAT_PRINT_TEMPLATE, target])
    return args


def get_format_selector(fmt: str, quality: str = "best") -> str:
    """Build the yt-dlp ``-f`` selector for a file format and quality."""
    if fmt in AUDIO_FORMATS:
        return "bestaudio/best"

    quality_selector = VIDEO_QUALITY_SELECTORS.get(quality.lower())
    if quality_selector:
        return quality_selector

    return "bestvideo+bestaudio/best"


def get_audio_quality(quality: str) -> str:
    """Map an audio bitrate such as ``320kbps`` to yt-dlp's quality index."""
    return AUDIO_QUALITY_MAP.get(quality.lower(), "0")
