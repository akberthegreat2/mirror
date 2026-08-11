"""Real composition tests for the local crawl provider.

These exercise the actual LocalCrawlProvider composed with the real
HTTPXProvider against a real local HTTP server — no fakes (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from mirror_crawl.models import CrawlRequest
from mirror_crawl_local.provider import LocalCrawlProvider
from mirror_fetch_httpx.provider import HTTPXProvider

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
async def test_local_crawl_with_real_httpx_fetch() -> None:
    """LocalCrawlProvider composed with real HTTPXProvider fetches real pages."""
    with _local_site() as base_url:
        fetch = HTTPXProvider()
        await fetch.setup()
        try:
            provider = LocalCrawlProvider(fetch=fetch)
            result = await provider.crawl(
                CrawlRequest(url=f"{base_url}/", max_depth=1, max_pages=5)
            )
        finally:
            await fetch.teardown()

        assert result.seed_url == f"{base_url}/"
        assert f"{base_url}/" in result.visited_urls
        assert f"{base_url}/about" in result.visited_urls
        assert len(result.discovered_urls) >= 2


@pytest.mark.asyncio
async def test_local_crawl_respects_max_depth() -> None:
    with _local_site() as base_url:
        fetch = HTTPXProvider()
        await fetch.setup()
        try:
            provider = LocalCrawlProvider(fetch=fetch)
            result = await provider.crawl(
                CrawlRequest(url=f"{base_url}/", max_depth=0, max_pages=5)
            )
        finally:
            await fetch.teardown()

        assert f"{base_url}/" in result.visited_urls
        assert len(result.visited_urls) == 1
