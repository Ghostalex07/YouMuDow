"""Tests for browser profile detection."""

from youmudow.adapters import browser_profiles
from youmudow.adapters.browser_profiles import (
    SUPPORTED_BROWSERS,
    BrowserProfile,
    check_browser_profile,
    get_all_browser_profiles,
    get_available_browsers,
    get_fallback_browser,
    invalidate_browsers_cache,
)


class TestSupportedBrowsers:
    def test_supported_browsers_constant(self):
        assert isinstance(SUPPORTED_BROWSERS, list)
        assert len(SUPPORTED_BROWSERS) == 7
        expected = ["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi"]
        assert SUPPORTED_BROWSERS == expected


class TestBrowserProfileChecks:
    def test_get_available_browsers_returns_list(self):
        result = get_available_browsers()
        assert isinstance(result, list)
        for browser in result:
            assert browser in SUPPORTED_BROWSERS

    def test_check_browser_profile_returns_tuple(self):
        result = check_browser_profile("firefox")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_check_browser_profile_unknown(self):
        exists, message = check_browser_profile("unknown_browser")
        assert exists is False
        assert "not installed" in message.lower() or "available" in message.lower()

    def test_get_fallback_browser_returns_or_none(self):
        result = get_fallback_browser()
        if result is not None:
            assert result in SUPPORTED_BROWSERS

    def test_get_all_browser_profiles_returns_dict(self):
        result = get_all_browser_profiles()
        assert isinstance(result, dict)
        for browser, profiles in result.items():
            assert browser in SUPPORTED_BROWSERS
            assert isinstance(profiles, list)


class TestBrowserProfileDataclass:
    def test_browser_profile_dataclass(self):
        profile = BrowserProfile(name="Default", path="/path/to/profile", browser="chrome")
        assert profile.name == "Default"
        assert profile.path == "/path/to/profile"
        assert profile.browser == "chrome"


class TestBrowsersCache:
    def test_get_available_browsers_cached(self):
        invalidate_browsers_cache()

        call_count = [0]
        original = browser_profiles.check_browser_profile

        def counting_check(browser):
            call_count[0] += 1
            return original(browser)

        browser_profiles.check_browser_profile = counting_check
        try:
            r1 = browser_profiles.get_available_browsers()
            call_count[0] = 0

            r2 = browser_profiles.get_available_browsers()
            calls_second = call_count[0]

            assert r1 == r2
            assert calls_second == 0, f"Cache not used: {calls_second} calls"
        finally:
            browser_profiles.check_browser_profile = original
            invalidate_browsers_cache()
