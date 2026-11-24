"""The settings file has one schema, and every value is coerced to it on load."""

from youmudow.app.settings import DEFAULT_SETTINGS, coerce_setting, normalize_settings


def test_defaults_cover_the_keys_the_app_reads():
    for key in (
        "output_path",
        "format",
        "quality",
        "max_retries",
        "playlist_limit",
        "concurrent_downloads",
        "search_history",
        "language",
    ):
        assert key in DEFAULT_SETTINGS


def test_stored_values_are_coerced_to_their_declared_type():
    data = normalize_settings(
        {
            "concurrent_downloads": "3",
            "debug_mode": "false",
            "playlist_limit": "abc",
            "search_history": "oops",
        }
    )
    assert data["concurrent_downloads"] == 3
    assert data["debug_mode"] is False
    assert data["playlist_limit"] == 50
    assert data["search_history"] == []


def test_boolean_spellings_are_understood():
    assert normalize_settings({"check_for_updates": "true"})["check_for_updates"] is True
    assert normalize_settings({"check_for_updates": "no"})["check_for_updates"] is False
    assert normalize_settings({"check_for_updates": 0})["check_for_updates"] is False


def test_unknown_keys_survive_a_round_trip():
    assert normalize_settings({"future_flag": 1})["future_flag"] == 1


def test_history_entries_are_trimmed_and_blanks_dropped():
    history = normalize_settings({"search_history": ["a", "", " b "]})["search_history"]
    assert history == ["a", "b"]


def test_coerce_setting_passes_unknown_keys_through():
    marker = object()
    assert coerce_setting("future_flag", marker) is marker
