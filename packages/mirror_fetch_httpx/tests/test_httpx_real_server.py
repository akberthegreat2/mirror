"""Real-backend tests for the HTTPX provider.

These exercise the actual HTTPX stack against a real local HTTP server on
127.0.0.1 — nothing is mocked (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from mirror_fetch.exceptions import FetchError
from mirror_fetch.models import FetchRequest
from mirror_fetch_httpx.provider import HTTPXProvider


class _SiteHandler(http.server.BaseHTTPRequestHandler):
    def _respond(self, payload: bytes, content_type: str = "text/html") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/data":
            self._respond(b'{"name": "mirror", "value": 42}', "application/json")
        else:
            self._respond(b"<html><body>hello httpx</body></html>")

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self._respond(b"echo:" + body, "text/plain")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@contextmanager
def local_server() -> Iterator[str]:
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
async def test_fetch_get_real_server() -> None:
    with local_server() as base_url:
        provider = HTTPXProvider()
        await provider.setup()
        try:
            result = await provider.fetch(FetchRequest(url=f"{base_url}/"))
        finally:
            await provider.teardown()
        assert result.status_code == 200
        assert b"hello httpx" in result.content


@pytest.mark.asyncio
async def test_fetch_json_real_server() -> None:
    with local_server() as base_url:
        provider = HTTPXProvider()
        await provider.setup()
        try:
            result = await provider.fetch(FetchRequest(url=f"{base_url}/data"))
        finally:
            await provider.teardown()
        assert result.status_code == 200
        assert result.content_type == "application/json"
        assert b'"name": "mirror"' in result.content


@pytest.mark.asyncio
async def test_fetch_post_real_server() -> None:
    with local_server() as base_url:
        provider = HTTPXProvider()
        await provider.setup()
        try:
            result = await provider.fetch(
                FetchRequest(url=f"{base_url}/submit", method="POST", body=b"payload")
            )
        finally:
            await provider.teardown()
        assert result.status_code == 200
        assert result.content == b"echo:payload"


@pytest.mark.asyncio
async def test_fetch_connection_error_becomes_fetch_error() -> None:
    provider = HTTPXProvider()
    await provider.setup()
    try:
        with pytest.raises(FetchError) as exc:
            await provider.fetch(FetchRequest(url="http://127.0.0.1:1/"))
        assert exc.value.cause is not None
    finally:
        await provider.teardown()
