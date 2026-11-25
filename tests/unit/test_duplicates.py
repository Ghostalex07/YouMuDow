from youmudow.domain.duplicates import find_duplicate_groups
from youmudow.domain.models import HistoryEntry


def _entry(title: str, size: int, duration: int, when: str) -> HistoryEntry:
    return HistoryEntry(
        title=title,
        url=f"https://x.test/{title}",
        uploader="U",
        file_format="mp3",
        output_path=f"/music/{title}.mp3",
        downloaded_at=when,
        duration=duration,
        file_size_bytes=size,
    )


def test_identical_size_and_duration_is_a_duplicate_and_newest_is_kept():
    groups = find_duplicate_groups(
        [
            _entry("old", 1000, 200, "2026-01-01T00:00:00+00:00"),
            _entry("new", 1000, 200, "2026-02-01T00:00:00+00:00"),
            _entry("other", 2000, 300, "2026-01-01T00:00:00+00:00"),
        ]
    )

    assert len(groups) == 1
    assert groups[0].keep.title == "new"
    assert [entry.title for entry in groups[0].extras] == ["old"]
    assert groups[0].reclaim_bytes == 1000


def test_same_duration_different_size_is_not_a_duplicate():
    groups = find_duplicate_groups(
        [
            _entry("a", 1000, 200, "2026-01-01T00:00:00+00:00"),
            _entry("b", 1400, 200, "2026-01-01T00:00:00+00:00"),
        ]
    )
    assert groups == []


def test_entries_without_size_or_path_are_ignored():
    entries = [
        _entry("a", 0, 200, "2026-01-01T00:00:00+00:00"),
        _entry("b", 0, 200, "2026-01-01T00:00:00+00:00"),
    ]
    assert find_duplicate_groups(entries) == []
