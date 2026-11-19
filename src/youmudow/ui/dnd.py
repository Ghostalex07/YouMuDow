"""Optional drag-and-drop of links onto the window.

``tkinterdnd2`` ships a Tk extension, so it is imported lazily: without it the
app behaves exactly as before and only logs why dropping does not work.
"""

import logging
import re
import tkinter as tk
from collections.abc import Callable, Sequence

from youmudow.domain.validators import is_supported_url

logger = logging.getLogger(__name__)

_BRACED_OR_WORD = re.compile(r"\{([^}]*)\}|(\S+)")


def create_root() -> tk.Tk:
    """Build the Tk root, loading the TkDND extension when it is available.

    ``tkinterdnd2`` only exposes drop methods on a root it created itself, so
    the window has to ask for one instead of calling ``tk.Tk()`` directly.
    """
    try:
        from tkinterdnd2 import TkinterDnD
    except ImportError:
        return tk.Tk()
    try:
        root: tk.Tk = TkinterDnD.Tk()
        return root
    except Exception as exc:  # noqa: BLE001 - the bundled TkDND library can fail to load
        logger.warning("Falling back to a plain Tk root: %s", exc)
        return tk.Tk()


def parse_drop_data(data: object) -> list[str]:
    """Extract the supported URLs from a Tk drop payload.

    Tk hands over a Tcl list, so a single path arrives bare and several arrive
    braced (``{<url1>} {<url2>}``). Anything that is not a supported link is
    dropped.
    """
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        candidates = [str(item) for item in data]
    else:
        text = "" if data is None else str(data)
        candidates = [braced or bare for braced, bare in _BRACED_OR_WORD.findall(text)]
    return [url.strip() for url in candidates if is_supported_url(url.strip())]


def register_drop_target(widget: object, on_urls: Callable[[list[str]], None]) -> bool:
    """Turn ``widget`` into a drop target. Returns False when unavailable."""
    try:
        from tkinterdnd2 import DND_FILES
    except ImportError:
        logger.debug("tkinterdnd2 is not installed; drag and drop is disabled")
        return False

    try:
        widget.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
        widget.dnd_bind("<<Drop>>", lambda event: on_urls(parse_drop_data(event.data)))  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - the Tk extension can fail to load
        logger.warning("Could not enable drag and drop: %s", exc)
        return False
    return True
