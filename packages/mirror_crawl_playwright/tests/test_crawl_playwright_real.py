"""Real-browser crawl tests against a local HTTP site.

These drive an actual Playwright Chromium browser against a real local HTTP
server — no browser, page, or server is mocked (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from mirror_core.metadata import InMemoryMetadataStore
from mirror_core.storage import InMemoryBlobStore
from mirror_crawl.models import CrawlRequest
from mirror_crawl_playwright.provider import PlaywrightCrawlProvider
from pydantic import HttpUrl

_SITE = {
    "/": b"<html><head><title>Home</title></head><body><a href='/about'>About</a></body></html>",
    "/about": b"<html><head><title>About</title></head><body><p>about page</p></body></html>",
}


class _SiteHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = _SITE.get(self.path, b"<html><body>404</body></html>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@contextmanager
def _local_site() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_crawl_renders_and_persists_real_site() -> None:
    with _local_site() as base_url:
        provider = PlaywrightCrawlProvider()
        metadata = InMemoryMetadataStore()
        blobs = InMemoryBlobStore()
        await provider.setup()
        try:
            result = await provider.crawl(
                CrawlRequest(url=HttpUrl(f"{base_url}/"), max_depth=1, max_pages=5),
                metadata_store=metadata,
                blob_store=blobs,
            )
        finally:
            await provider.teardown()

        assert result.seed_url == f"{base_url}/"
        assert f"{base_url}/" in result.visited_urls
        assert f"{base_url}/about" in result.visited_urls
        assert result.stored_urls == 2
        assert result.stored_pages == 2

        records = metadata.list("crawl.urls")
        assert len(records) == 2
        keys = {record.key for record in records}
        assert f"{base_url}/" in keys
        assert f"{base_url}/about" in keys

        by_url = {record.key: record for record in records}
        about_record = by_url[f"{base_url}/about"]
        assert about_record.payload["status_code"] == 200
        assert about_record.payload["blob_key"] is not None
        stored = blobs.get_bytes(about_record.payload["blob_key"])
        assert stored is not None
        assert b"about page" in stored


@pytest.mark.asyncio
async def test_crawl_same_host_limits_to_seed_domain() -> None:
    with _local_site() as base_url:
        provider = PlaywrightCrawlProvider()
        await provider.setup()
        try:
            result = await provider.crawl(
                CrawlRequest(
                    url=HttpUrl(f"{base_url}/"),
                    max_depth=1,
                    max_pages=10,
                    same_host_only=True,
                )
            )
        finally:
            await provider.teardown()
        assert len(result.discovered_urls) == 2
        assert all(url.startswith(base_url) for url in result.visited_urls)
