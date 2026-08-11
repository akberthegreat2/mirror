"""Real-backend tests for the curl_cffi provider.

These tests exercise the actual curl_cffi/libcurl HTTP stack against a real
local HTTP server on 127.0.0.1 — nothing is mocked (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar

import pytest
from mirror_fetch.exceptions import FetchError
from mirror_fetch.models import FetchRequest
from mirror_fetch_curl_cffi.provider import CurlCFFIProvider


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    """Echoes method, path, and body back with a content-type header."""

    def _respond(self, payload: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._respond(b"hello from mirror test server")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self._respond(b"echo:" + body)

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def local_http_server(handler: type[http.server.BaseHTTPRequestHandler] = _EchoHandler) -> Iterator[str]:
    """Yield a base URL served by a real local HTTP server on 127.0.0.1."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


class _HeaderCapturingHandler(_EchoHandler):
    """Captures request headers for assertions."""

    seen: ClassVar[dict[str, str]] = {}

    def do_GET(self) -> None:
        self.seen["ua"] = self.headers.get("User-Agent", "")
        self.seen["x-custom"] = self.headers.get("X-Custom", "")
        super().do_GET()


@pytest.mark.asyncio
async def test_fetch_get_real_server() -> None:
    with local_http_server() as base_url:
        provider = CurlCFFIProvider()
        result = await provider.fetch(FetchRequest(url=f"{base_url}/hello"))
        assert result.status_code == 200
        assert result.content == b"hello from mirror test server"
        assert result.content_type == "text/plain"
        assert result.url == f"{base_url}/hello"
        assert result.fetch_duration >= 0.0
        await provider.teardown()


@pytest.mark.asyncio
async def test_fetch_post_body_real_server() -> None:
    with local_http_server() as base_url:
        provider = CurlCFFIProvider()
        result = await provider.fetch(
            FetchRequest(url=f"{base_url}/echo", method="POST", body=b"payload")
        )
        assert result.status_code == 200
        assert result.content == b"echo:payload"
        await provider.teardown()


@pytest.mark.asyncio
async def test_fetch_sends_user_agent_and_headers() -> None:
    _HeaderCapturingHandler.seen = {}
    with local_http_server(_HeaderCapturingHandler) as base_url:
        provider = CurlCFFIProvider()
        await provider.fetch(
            FetchRequest(url=f"{base_url}/", headers={"X-Custom": "mirror-test"})
        )
        assert _HeaderCapturingHandler.seen["ua"] == "Mirror/0.1"
        assert _HeaderCapturingHandler.seen["x-custom"] == "mirror-test"
        await provider.teardown()


@pytest.mark.asyncio
async def test_fetch_connection_error_becomes_fetch_error() -> None:
    provider = CurlCFFIProvider()
    # Nothing is listening on this port; curl_cffi must surface a transport error.
    with pytest.raises(FetchError) as exc:
        await provider.fetch(FetchRequest(url="http://127.0.0.1:1/"))
    assert "Failed to fetch" in str(exc.value)
    assert exc.value.cause is not None
    await provider.teardown()


@pytest.mark.asyncio
async def test_fetch_custom_timeout_is_passed() -> None:
    with local_http_server() as base_url:
        provider = CurlCFFIProvider()
        result = await provider.fetch(FetchRequest(url=f"{base_url}/", timeout=7.0))
        assert result.status_code == 200
        await provider.teardown()
