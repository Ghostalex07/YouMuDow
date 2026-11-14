"""Typed helpers for Tkinter's dynamically typed surface.

Tkinter's ``configure`` accepts arbitrary keyword arguments and mypy cannot
check them; widgets also carry dynamic attributes such as ``_bg_key``. These
helpers give both a single, checked entry point.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Mapping
from typing import Any, Generic, TypeVar, cast

FontSpec = tuple[str, int] | tuple[str, int, str]


def configure_widget(
    widget: tk.Misc,
    options: Mapping[str, object] | None = None,
    **extra: object,
) -> None:
    """Apply widget options, ignoring options the widget does not accept.

    ``options`` covers the mapping form (``configure_widget(w, {"bg": x})``)
    and ``extra`` the keyword form. Values are typed as ``object`` so callers
    can pass an ``int`` width or a ``Literal`` state without a cast.
    """
    merged: dict[str, object] = dict(options or {})
    merged.update(extra)
    try:
        # Tk accepts any option value; mypy cannot model that surface.
        widget.configure(**cast(Any, merged))
    except tk.TclError:
        pass


def setattr_any(obj: object, name: str, value: object) -> None:
    """Set a dynamic attribute on an otherwise statically typed object."""
    object.__setattr__(obj, name, value)


T = TypeVar("T")


class readonly_property(Generic[T]):
    """Expose a private backing attribute under the name a protocol declares.

    Protocol members are invariant when declared as plain attributes, so a
    read-only property is the only shape that a Tk subclass with a dynamic
    ``__getattr__`` can satisfy. Writing one property per member is noisy; this
    descriptor keeps the type and the read-only behaviour in one line.
    """

    def __init__(self, backing: str) -> None:
        self._backing = backing

    def __get__(self, instance: object, owner: type | None = None) -> T:
        return cast(T, getattr(instance, self._backing))

    def __set__(self, instance: object, value: object) -> None:
        raise AttributeError("this attribute is read-only")
