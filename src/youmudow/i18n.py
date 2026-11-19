"""Very small translation layer.

English source strings are the keys, so a missing entry simply falls back to
English instead of showing a placeholder. Only the strings a user actually
reads are wrapped: menus, buttons, status messages and the in-app guide.
"""

import locale
import os

from youmudow.i18n_catalog import LANGUAGE_NAMES, MESSAGES

DEFAULT_LANGUAGE = "en"
_current = DEFAULT_LANGUAGE


def available_languages() -> dict[str, str]:
    """Language code -> name, English first."""
    return {"en": LANGUAGE_NAMES["en"], **{code: LANGUAGE_NAMES[code] for code in MESSAGES}}


def get_language() -> str:
    return _current


def set_language(code: str) -> str:
    """Set the active language; unknown codes fall back to English."""
    global _current
    _current = code if code in MESSAGES else DEFAULT_LANGUAGE
    return _current


def detect_system_language() -> str:
    """Best-effort guess from the environment, for the ``auto`` setting."""
    raw = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG")
    if not raw:
        try:
            raw = locale.getlocale()[0] or ""
        except ValueError:
            raw = ""
    code = raw.split(".")[0].split("_")[0].strip().lower()
    return code if code in MESSAGES else DEFAULT_LANGUAGE


def resolve_language(setting: str) -> str:
    """Turn the stored setting (``auto``/``en``/``es``) into a language code."""
    if setting in LANGUAGE_NAMES:
        return setting
    return detect_system_language()


def t(text: str, **values: object) -> str:
    """Translate ``text``, formatting any placeholders with ``values``."""
    template = MESSAGES.get(_current, {}).get(text, text)
    if not values:
        return template
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        return template
