"""Real-HTTP tests for the memory monitor provider.

These exercise the actual ContentMonitor against a real local HTTP server
on 127.0.0.1 — no fake clients, no mocks (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from mirror_monitor.models import MonitorRequest
from mirror_monitor_memory import ContentMonitor, MemoryMonitorProvider

_BODY_VERSION: list[bytes] = [b"<html><body>version-one</body></html>"]


class _SiteHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = _BODY_VERSION[0]
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
async def test_monitor_checks_real_http_server() -> None:
    with _local_site() as base_url:
        provider = MemoryMonitorProvider()
        result = await provider.check(MonitorRequest(url=f"{base_url}/"))
        assert result.snapshot.status_code == 200
        assert result.snapshot.url == f"{base_url}/"
        assert result.snapshot.body_sha256
        assert result.snapshot.changed is True  # first sight: changed from nothing


@pytest.mark.asyncio
async def test_monitor_detects_change_between_checks() -> None:
    with _local_site() as base_url:
        provider = MemoryMonitorProvider()
        first = await provider.check(MonitorRequest(url=f"{base_url}/"))
        assert first.snapshot.changed is True

        # Second check against unchanged content -> not changed.
        second = await provider.check(MonitorRequest(url=f"{base_url}/"))
        assert second.snapshot.changed is False
        assert second.snapshot.body_sha256 == first.snapshot.body_sha256

        # Server content changes -> next check reports changed.
        _BODY_VERSION[0] = b"<html><body>version-two</body></html>"
        third = await provider.check(MonitorRequest(url=f"{base_url}/"))
        assert third.snapshot.changed is True
        assert third.snapshot.body_sha256 != first.snapshot.body_sha256
        _BODY_VERSION[0] = b"<html><body>version-one</body></html>"
