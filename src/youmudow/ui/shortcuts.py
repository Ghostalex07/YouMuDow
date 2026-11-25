"""Small helpers shared by the keyboard bindings."""

MAX_TAB_INDEX = 2


def tab_index_for(key: str) -> int | None:
    """Map a digit key to a notebook index, or None when out of range."""
    if len(key) != 1 or not key.isdigit():
        return None
    index = int(key) - 1
    return index if 0 <= index <= MAX_TAB_INDEX else None
