from youmudow.domain.presets import PRESETS, find_preset
from youmudow.domain.validators import is_valid_format, is_valid_quality


def test_presets_are_valid():
    for preset in PRESETS:
        assert is_valid_format(preset.options.file_format)
        assert is_valid_quality(preset.options.quality)


def test_preset_names_are_the_documented_ones():
    assert [preset.name for preset in PRESETS] == ["Music 320", "Video 1080", "Archive FLAC"]


def test_find_preset():
    assert find_preset("Music 320").options.quality == "320kbps"
    assert find_preset("nope") is None
