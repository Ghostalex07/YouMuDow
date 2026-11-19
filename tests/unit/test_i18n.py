"""Tests for the translation layer."""

import pytest

from youmudow.i18n import (
    available_languages,
    detect_system_language,
    get_language,
    resolve_language,
    set_language,
    t,
)


@pytest.fixture(autouse=True)
def _reset_language():
    set_language("en")
    yield
    set_language("en")


def test_english_is_the_source_language():
    assert get_language() == "en"
    assert t("Ready") == "Ready"


def test_spanish_translates_known_strings():
    set_language("es")
    assert t("Ready") == "Listo"
    assert t("Searching...") == "Buscando..."


def test_unknown_strings_fall_back_to_english():
    set_language("es")
    assert t("Some string nobody translated") == "Some string nobody translated"


def test_placeholders_are_filled():
    set_language("es")
    assert t("Downloaded: {title}", title="Song") == "Descargado: Song"


def test_missing_placeholder_returns_the_template_instead_of_raising():
    set_language("es")
    assert t("Downloaded: {title}") == "Descargado: {title}"


def test_unknown_language_falls_back_to_english():
    assert set_language("xx") == "en"


def test_resolve_language_honours_explicit_settings(monkeypatch):
    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    assert resolve_language("en") == "en"
    assert resolve_language("es") == "es"
    assert resolve_language("auto") == "es"


def test_auto_detection_uses_the_locale(monkeypatch):
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    assert detect_system_language() == "es"

    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert detect_system_language() == "en"


def test_available_languages_lists_english_first():
    languages = available_languages()
    assert next(iter(languages)) == "en"
    assert "es" in languages
