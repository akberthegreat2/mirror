"""Settings validation for the Playwright crawl provider."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mirror_crawl_playwright.settings import PlaywrightCrawlSettings


def test_defaults() -> None:
    settings = PlaywrightCrawlSettings()
    assert settings.headless is True
    assert settings.browser == "chromium"
    assert settings.navigation_timeout == 30.0
    assert settings.user_agent == "Mirror Crawl/0.1"


def test_browser_selection() -> None:
    assert PlaywrightCrawlSettings(browser="firefox").browser == "firefox"


def test_invalid_browser_rejected() -> None:
    with pytest.raises(ValidationError):
        PlaywrightCrawlSettings(browser="netscape")


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        PlaywrightCrawlSettings(navigation_timeout=0.0)
