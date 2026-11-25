"""Finding likely duplicate downloads by size and duration."""

from dataclasses import dataclass

from youmudow.domain.models import HistoryEntry


@dataclass(frozen=True)
class DuplicateGroup:
    """One file to keep plus the extra copies that look identical."""

    keep: HistoryEntry
    extras: tuple[HistoryEntry, ...]

    @property
    def reclaim_bytes(self) -> int:
        return sum(entry.file_size_bytes for entry in self.extras)


def find_duplicate_groups(entries: list[HistoryEntry]) -> list[DuplicateGroup]:
    """Group entries that share an exact size and duration.

    Matching both numbers avoids flagging the same song at another bitrate,
    which shares the duration but not the size. Entries without a recorded
    size or path are skipped: they cannot be compared safely.
    """
    buckets: dict[tuple[int, int], list[HistoryEntry]] = {}
    for entry in entries:
        if entry.file_size_bytes <= 0 or not entry.output_path:
            continue
        buckets.setdefault((entry.file_size_bytes, entry.duration), []).append(entry)

    groups: list[DuplicateGroup] = []
    for copies in buckets.values():
        if len(copies) < 2:
            continue
        ordered = sorted(copies, key=lambda entry: entry.downloaded_at, reverse=True)
        groups.append(DuplicateGroup(keep=ordered[0], extras=tuple(ordered[1:])))
    groups.sort(key=lambda group: group.reclaim_bytes, reverse=True)
    return groups
