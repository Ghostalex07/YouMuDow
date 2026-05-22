import json
import platform
from pathlib import Path
from typing import Any

from youmudow.domain.models import DownloadOptions


CONFIG_DIR: Path = Path.home() / ".config" / "youmudow" if platform.system() != "Windows" else Path.home() / "AppData" / "Local" / "YouMuDow"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "window_geometry": "",
    "output_path": str(Path.home() / "Music" / "YouMuDow" if platform.system() != "Windows" else Path.home() / "Desktop" / "YouMuDow"),
    "format": "mp3",
    "quality": "best",
    "subtitles": False,
    "subtitle_lang": "en",
    "embed_subtitles": False,
    "use_cookies": False,
    "cookies_source": "browser",
    "cookies_file": "",
    "browser": "chrome",
    "profile": "Default",
    "rate_limit": "",
    "split_chapters": False,
    "debug_mode": False,
    "options_panel_open": False,
    "theme": "dark",
    "concurrent_downloads": 1,
    "search_history": [],
}


class AppConfig:
    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULT_CONFIG)
        self._load()

    def _load(self) -> None:
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    stored = json.load(f)
                self._data = {**DEFAULT_CONFIG, **stored}
        except json.JSONDecodeError:
            import sys
            print(f"[config] Corrupted config file, using defaults: {CONFIG_FILE}", file=sys.stderr)
        except OSError as e:
            import sys
            print(f"[config] Failed to load config: {e}", file=sys.stderr)

    def save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError as e:
            import sys
            print(f"[config] Failed to save config: {e}", file=sys.stderr)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def window_geometry(self) -> str:
        return str(self._data.get("window_geometry", ""))

    @window_geometry.setter
    def window_geometry(self, value: str) -> None:
        self._data["window_geometry"] = value

    @property
    def output_path(self) -> Path:
        return Path(str(self._data.get("output_path", DEFAULT_CONFIG["output_path"])))

    @output_path.setter
    def output_path(self, value: Path | str) -> None:
        self._data["output_path"] = str(value)

    def add_search(self, query: str) -> None:
        history = self.get("search_history", [])
        if query in history:
            history.remove(query)
        history.insert(0, query)
        self.set("search_history", history[:10])

    def get_search_history(self) -> list[str]:
        return self.get("search_history", [])

    def to_download_options(self) -> DownloadOptions:
        return DownloadOptions(
            file_format=str(self._data.get("format", "mp3")),
            quality=str(self._data.get("quality", "best")),
            subtitles=bool(self._data.get("subtitles", False)),
            subtitle_lang=str(self._data.get("subtitle_lang", "en")),
            embed_subtitles=bool(self._data.get("embed_subtitles", False)),
            use_cookies=bool(self._data.get("use_cookies", False)),
            cookies_file=str(self._data.get("cookies_file", "")) if self._data.get("cookies_source") == "file" else None,
            cookies_from_browser=str(self._data.get("browser", "chrome")) if self._data.get("cookies_source") != "file" else None,
            cookies_profile=str(self._data.get("profile", "")) or None,
            rate_limit=str(self._data.get("rate_limit", "")) or None,
            split_chapters=bool(self._data.get("split_chapters", False)),
        )

    def from_download_options(self, opts: DownloadOptions) -> None:
        self._data["format"] = opts.file_format or "mp3"
        self._data["quality"] = opts.quality or "best"
        self._data["subtitles"] = opts.subtitles
        self._data["subtitle_lang"] = opts.subtitle_lang or "en"
        self._data["embed_subtitles"] = opts.embed_subtitles
        self._data["use_cookies"] = opts.use_cookies
        self._data["cookies_source"] = "file" if opts.cookies_file else "browser"
        self._data["cookies_file"] = opts.cookies_file or ""
        self._data["browser"] = opts.cookies_from_browser or "chrome"
        self._data["profile"] = opts.cookies_profile or "Default"
        self._data["rate_limit"] = opts.rate_limit or ""
        self._data["split_chapters"] = opts.split_chapters
