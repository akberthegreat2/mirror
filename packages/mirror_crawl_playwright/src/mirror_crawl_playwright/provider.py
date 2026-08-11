"""Playwright browser crawl provider implementation.

Drives a real browser (Chromium/Firefox/WebKit) to render pages — including
JavaScript-heavy pages — collect links, and persist discovered URLs and page
bodies exactly like the fetch-composed crawl providers (CLAUDE.md §15).
"""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from mirror_core.exceptions import ExecutionError
from mirror_core.extensions.models import ProviderManifest
from mirror_core.lifecycle import AsyncLifecycle
from mirror_core.metadata import MetadataRecord, MetadataStore
from mirror_core.storage import BlobStore
from mirror_crawl.models import CrawlRecord, CrawlRequest, CrawlResult
from mirror_crawl.protocol import Crawl

from mirror_crawl_playwright.settings import PlaywrightCrawlSettings

logger = logging.getLogger(__name__)


class _LinkExtractor(HTMLParser):
    """Extract anchor links and the document title from rendered HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title: str | None = None
        self._capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            for key, value in attrs:
                if key.lower() == "href" and value:
                    self.links.append(value)
        if tag.lower() == "title":
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title = (self.title or "") + data


def _parse_html(content: str, extract_titles: bool) -> tuple[str | None, list[str]]:
    parser = _LinkExtractor()
    parser.feed(content)
    return (parser.title if extract_titles else None, parser.links)


def _blob_key(request: CrawlRequest, url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    host = urlparse(str(request.url)).netloc or "crawl"
    return f"{request.blob_namespace}/{host}/{digest}.html"


class PlaywrightCrawlProvider(AsyncLifecycle, Crawl):
    """Crawl a site with a real Playwright browser."""

    def __init__(
        self,
        settings: PlaywrightCrawlSettings | None = None,
        *,
        launcher: Any = None,
    ) -> None:
        self._settings = settings or PlaywrightCrawlSettings()
        self._launcher = launcher
        self._playwright: Any = None
        self._browser: Any = None

    async def setup(self) -> None:
        await self._ensure_browser()

    async def teardown(self) -> None:
        browser, self._browser = self._browser, None
        if browser is not None:
            try:
                await browser.close()
            except Exception:  # noqa: BLE001 - teardown must not raise
                logger.debug("playwright browser close failed", exc_info=True)
        playwright, self._playwright = self._playwright, None
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:  # noqa: BLE001 - teardown must not raise
                logger.debug("playwright stop failed", exc_info=True)

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        if self._launcher is not None:
            self._browser = await self._launcher(self._settings)
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ExecutionError(
                "Playwright crawl requires 'playwright'; install mirror-crawl-playwright"
            ) from exc
        self._playwright = await async_playwright().start()
        browser_type = getattr(self._playwright, self._settings.browser)
        try:
            self._browser = await browser_type.launch(headless=self._settings.headless)
        except Exception as exc:
            await self._playwright.stop()
            self._playwright = None
            raise ExecutionError(
                "Playwright browser executable is unavailable; run 'playwright install'"
            ) from exc

    async def crawl(
        self,
        request: CrawlRequest,
        *,
        metadata_store: MetadataStore | None = None,
        blob_store: BlobStore | None = None,
    ) -> CrawlResult:
        await self._ensure_browser()
        assert self._browser is not None

        context = await self._browser.new_context(user_agent=self._settings.user_agent)
        page = await context.new_page()
        parsed_seed = urlparse(str(request.url))

        queue: deque[tuple[str, str | None, int]] = deque(
            [(str(request.url), None, 0)]
        )
        seen: set[str] = set()
        visited: list[str] = []
        discovered: list[CrawlRecord] = []
        stored_urls = 0
        stored_pages = 0

        try:
            while queue and len(visited) < request.max_pages:
                current_url, parent_url, depth = queue.popleft()
                if current_url in seen:
                    continue
                seen.add(current_url)

                status_code: int | None = None
                content = ""
                try:
                    response = await page.goto(
                        current_url,
                        wait_until="domcontentloaded",
                        timeout=int(self._settings.navigation_timeout * 1000),
                    )
                    status_code = response.status if response is not None else None
                    content = await page.content()
                except Exception as exc:  # noqa: BLE001 - surfaced per record
                    logger.debug(
                        "playwright crawl navigation failed",
                        extra={"url": current_url, "error": str(exc)},
                    )
                    continue

                visited.append(current_url)
                title, links = _parse_html(content, self._settings.extract_titles)

                blob_key = None
                if request.store_pages and blob_store is not None:
                    blob_key = _blob_key(request, current_url)
                    blob_store.put_bytes(
                        blob_key, content.encode("utf-8", errors="replace")
                    )
                    stored_pages += 1

                discovered.append(
                    CrawlRecord(
                        url=current_url,
                        depth=depth,
                        parent_url=parent_url,
                        status_code=status_code,
                        title=title,
                        content_type="text/html",
                        blob_key=blob_key,
                    )
                )

                if request.persist_discovered_urls and metadata_store is not None:
                    metadata_store.put(
                        MetadataRecord(
                            namespace=request.metadata_namespace,
                            key=current_url,
                            payload={
                                "depth": depth,
                                "parent_url": parent_url,
                                "status_code": status_code,
                                "content_type": "text/html",
                                "blob_key": blob_key,
                            },
                        )
                    )
                    stored_urls += 1

                if depth >= request.max_depth:
                    continue
                for link in links:
                    absolute = urljoin(current_url, link)
                    if absolute in seen:
                        continue
                    if (
                        request.same_host_only
                        and urlparse(absolute).netloc != parsed_seed.netloc
                    ):
                        continue
                    queue.append((absolute, current_url, depth + 1))
        finally:
            await context.close()

        return CrawlResult(
            seed_url=str(request.url),
            discovered_urls=discovered,
            visited_urls=visited,
            stored_urls=stored_urls,
            stored_pages=stored_pages,
        )


provider = ProviderManifest(
    name="playwright",
    capability="crawl",
    capability_api="~=1.0",
    factory="mirror_crawl_playwright.provider:PlaywrightCrawlProvider",
    settings_model="mirror_crawl_playwright.settings:PlaywrightCrawlSettings",
    features=["browser", "javascript", "rendering", "dom", "persist"],
    priority=20,
    metadata={"description": "Playwright browser crawl provider"},
)
