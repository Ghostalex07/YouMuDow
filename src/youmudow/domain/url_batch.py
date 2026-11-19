"""Parse a pasted or imported list of links."""

from youmudow.domain.validators import is_supported_url


def parse_url_list(text: str) -> list[str]:
    """Return the supported, de-duplicated links found in ``text``.

    One link per line, ``#`` comments and blank lines are ignored, and a CSV
    row contributes its first column so exporting from a spreadsheet works.
    """
    urls: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        candidate = stripped.split(",", 1)[0].strip()
        if candidate and is_supported_url(candidate) and candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls
