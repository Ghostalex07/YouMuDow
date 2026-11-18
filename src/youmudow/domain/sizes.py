"""Human-readable byte sizes, shared by the UI and the history."""

_SIZE_UNITS = ("B", "KB", "MB", "GB")


def format_size(num_bytes: int) -> str:
    """Render a byte count like "5.0 MB"; zero or negative renders as empty."""
    if num_bytes <= 0:
        return ""
    size: float = num_bytes
    for unit in _SIZE_UNITS:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
