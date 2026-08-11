"""Real-browser fetch tests against a local HTTP site.

These drive an actual Playwright Chromium browser against a real local HTTP
server — no browser, page, or server is mocked (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from mirror_fetch.models import FetchRequest
from mirror_fetch_playwright.provider import PlaywrightProvider

_SITE = {
    "/": b"<html><head><title>Home</title></head><body><p>hello playwright</p></body></html>",
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


@pytest.fixture(scope="module")
def _browser_available() -> bool:
    try:
        from playwright.async_api import async_playwright  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.asyncio
async def test_fetch_renders_real_browser_page() -> None:
    with _local_site() as base_url:
        provider = PlaywrightProvider()
        await provider.setup()
        try:
            result = await provider.fetch(FetchRequest(url=f"{base_url}/"))
        finally:
            await provider.teardown()
        assert result.status_code == 200
        assert b"hello playwright" in result.content
        assert result.url == f"{base_url}/"
        assert result.fetch_duration >= 0.0
