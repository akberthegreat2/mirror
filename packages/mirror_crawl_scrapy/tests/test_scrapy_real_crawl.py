"""Real Scrapy crawl tests against a local HTTP site.

These drive the actual Scrapy crawler engine against a real local HTTP server —
no Scrapy internals are mocked (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from mirror_crawl.models import CrawlRequest
from mirror_crawl_scrapy.provider import ScrapyCrawlProvider

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
async def test_scrapy_crawls_local_site() -> None:
    with _local_site() as base_url:
        provider = ScrapyCrawlProvider()
        result = await provider.crawl(
            CrawlRequest(url=f"{base_url}/", max_depth=1, max_pages=5)
        )
        assert result.seed_url == f"{base_url}/"
        assert f"{base_url}/" in result.visited_urls
        assert f"{base_url}/about" in result.visited_urls
        assert len(result.discovered_urls) >= 2


@pytest.mark.asyncio
async def test_scrapy_respects_max_pages() -> None:
    with _local_site() as base_url:
        provider = ScrapyCrawlProvider()
        result = await provider.crawl(
            CrawlRequest(url=f"{base_url}/", max_depth=1, max_pages=1)
        )
        assert len(result.visited_urls) == 1
        assert f"{base_url}/" in result.visited_urls
