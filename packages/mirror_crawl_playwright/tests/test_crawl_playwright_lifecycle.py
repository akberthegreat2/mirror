"""Lifecycle tests for the Playwright crawl provider."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from mirror_crawl_playwright.provider import PlaywrightCrawlProvider


class _FakeBrowser:
    closed = False

    async def close(self) -> None:
        self.closed = True


class _FakePlaywright:
    stopped = False

    async def stop(self) -> None:
        self.stopped = True


def _launcher(browser: _FakeBrowser) -> Callable[[object], Awaitable[object]]:
    async def launch(settings: object) -> object:
        return browser

    return launch


@pytest.mark.asyncio
async def test_setup_launches_browser_once() -> None:
    browser = _FakeBrowser()
    provider = PlaywrightCrawlProvider(launcher=_launcher(browser))
    await provider.setup()
    assert provider._browser is browser
    await provider.setup()
    assert provider._browser is browser
    await provider.teardown()


@pytest.mark.asyncio
async def test_teardown_closes_browser_and_stops_playwright() -> None:
    browser = _FakeBrowser()
    provider = PlaywrightCrawlProvider(launcher=_launcher(browser))
    provider._playwright = _FakePlaywright()
    await provider.setup()
    await provider.teardown()
    assert browser.closed is True
    assert provider._browser is None
    assert provider._playwright is None


@pytest.mark.asyncio
async def test_teardown_is_idempotent() -> None:
    provider = PlaywrightCrawlProvider()
    await provider.teardown()
    await provider.teardown()
    assert provider._browser is None
