"""Reusable test fixtures for legal reference sites (ADR-0049).

Provides live, opt-in fixtures for the Tier 1/2 sites from
docs/testing/LEGAL_TEST_SITES.md so integration tests can exercise
real backends without flaking CI.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
import pytest


def _live_enabled() -> bool:
    return os.environ.get("MIRROR_LIVE_TESTS") == "1"


def _skip_if_offline() -> None:
    if not _live_enabled():
        pytest.skip("Live network tests require MIRROR_LIVE_TESTS=1")


# --- Marker registration ---


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: requires live network access to legal test sites (opt-in via MIRROR_LIVE_TESTS=1)",
    )


# --- Site catalogue ---


@dataclass(frozen=True)
class LegalSite:
    name: str
    base_url: str
    tier: int
    description: str
    requires_javascript: bool = False
    allows_crawling: bool = True


LEGAL_SITES: tuple[LegalSite, ...] = (
    LegalSite(
        name="books.toscrape.com",
        base_url="http://books.toscrape.com",
        tier=1,
        description="Static HTML, pagination, extraction",
    ),
    LegalSite(
        name="quotes.toscrape.com",
        base_url="http://quotes.toscrape.com",
        tier=1,
        description="Login/CSRF and scripted interactions",
    ),
    LegalSite(
        name="scrapethissite.com",
        base_url="https://scrapethissite.com",
        tier=1,
        description="Pagination, AJAX, frames, session cookies",
    ),
    LegalSite(
        name="httpbin.org",
        base_url="https://httpbin.org",
        tier=2,
        description="Methods, headers, cookies, delays, redirects",
    ),
    LegalSite(
        name="jsonplaceholder.typicode.com",
        base_url="https://jsonplaceholder.typicode.com",
        tier=2,
        description="REST/API extraction",
    ),
)


# --- Catalogue fixtures (always available, no network) ---


@pytest.fixture(scope="session")
def legal_sites() -> tuple[LegalSite, ...]:
    return LEGAL_SITES


@pytest.fixture(scope="session")
def tier1_sites() -> tuple[LegalSite, ...]:
    return tuple(s for s in LEGAL_SITES if s.tier == 1)


@pytest.fixture(scope="session")
def tier2_sites() -> tuple[LegalSite, ...]:
    return tuple(s for s in LEGAL_SITES if s.tier == 2)


# --- Raw httpx helpers ---


@dataclass(frozen=True)
class LiveFetchResult:
    url: str
    status_code: int
    content: bytes
    content_type: str | None
    headers: dict[str, str]
    duration: float


async def _fetch(client: httpx.AsyncClient, url: str) -> LiveFetchResult:
    start = time.perf_counter()
    resp = await client.get(url)
    duration = time.perf_counter() - start
    return LiveFetchResult(
        url=str(resp.url),
        status_code=resp.status_code,
        content=resp.content,
        content_type=resp.headers.get("content-type"),
        headers=dict(resp.headers),
        duration=duration,
    )


# --- Assertion helpers ---


def assert_ok(result: LiveFetchResult) -> None:
    assert result.status_code == 200, f"Expected 200, got {result.status_code} for {result.url}"
    assert result.content, f"Empty response from {result.url}"


def assert_html(result: LiveFetchResult) -> str:
    ct = (result.content_type or "").lower()
    assert "html" in ct or result.content.startswith(b"<!DOCTYPE"), f"Not HTML: {ct}"
    return result.content.decode("utf-8", errors="replace")


def assert_json(result: LiveFetchResult) -> Any:
    ct = (result.content_type or "").lower()
    assert "json" in ct, f"Not JSON: {ct}"
    return json.loads(result.content)


# --- Live session-scoped fixtures (skip when offline) ---


@pytest.fixture(scope="session")
async def live_http_client() -> httpx.AsyncClient:
    _skip_if_offline()
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        yield client


@pytest.fixture
async def live_httpx_fetch() -> Any:
    _skip_if_offline()
    from mirror_fetch_httpx.provider import HTTPXProvider
    from mirror_fetch_httpx.settings import HTTPXSettings

    provider = HTTPXProvider(HTTPXSettings())
    await provider.setup()
    try:
        yield provider
    finally:
        try:
            await provider.teardown()
        except RuntimeError:
            # httpx transport may fail to close when the event loop is already
            # shutting down.  The connection pool is garbage-collected anyway.
            pass


@pytest.fixture
async def live_local_crawl(live_httpx_fetch: Any) -> Any:
    _skip_if_offline()
    from mirror_crawl_local.provider import LocalCrawlProvider

    yield LocalCrawlProvider(fetch=live_httpx_fetch)


# --- Per-site convenience fixtures ---


@pytest.fixture(scope="session")
async def httpbin(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "https://httpbin.org/get")


@pytest.fixture(scope="session")
async def httpbin_headers(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "https://httpbin.org/headers")


@pytest.fixture(scope="session")
async def httpbin_cookies(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "https://httpbin.org/cookies/set?test=value")


@pytest.fixture(scope="session")
async def httpbin_redirect(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "https://httpbin.org/redirect/2")


@pytest.fixture(scope="session")
async def httpbin_delay(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "https://httpbin.org/delay/1")


@pytest.fixture(scope="session")
async def jsonplaceholder_posts(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "https://jsonplaceholder.typicode.com/posts")


@pytest.fixture(scope="session")
async def books_index(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "http://books.toscrape.com/")


@pytest.fixture(scope="session")
async def books_page2(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "http://books.toscrape.com/catalogue/page-2.html")


@pytest.fixture(scope="session")
async def quotes_index(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "http://quotes.toscrape.com/")


@pytest.fixture(scope="session")
async def quotes_login_page(live_http_client: httpx.AsyncClient) -> LiveFetchResult:
    return await _fetch(live_http_client, "http://quotes.toscrape.com/login")


__all__ = [
    "LEGAL_SITES",
    "LegalSite",
    "LiveFetchResult",
    "assert_html",
    "assert_json",
    "assert_ok",
    "books_index",
    "books_page2",
    "httpbin",
    "httpbin_cookies",
    "httpbin_delay",
    "httpbin_headers",
    "httpbin_redirect",
    "jsonplaceholder_posts",
    "legal_sites",
    "live_http_client",
    "live_httpx_fetch",
    "live_local_crawl",
    "quotes_index",
    "quotes_login_page",
    "tier1_sites",
    "tier2_sites",
]
