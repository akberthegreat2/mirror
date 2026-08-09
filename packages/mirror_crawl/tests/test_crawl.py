"""Tests for the crawl capability and local provider."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager

import pytest
from mirror_core.executor import Executor, RunOutcome
from mirror_core.extensions.models import ProviderManifest
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.metadata import InMemoryMetadataStore
from mirror_core.pipeline import Pipeline, Step
from mirror_core.planner import Planner
from mirror_core.storage import FileSystemBlobStore
from mirror_crawl.capability import capability as crawl_capability
from mirror_crawl.models import CrawlRequest, CrawlSettings
from mirror_crawl.runner import crawl_site
from mirror_crawl_local.provider import LocalCrawlProvider
from mirror_crawl_local.provider import provider as crawl_provider_manifest
from mirror_fetch.capability import capability as fetch_capability
from mirror_fetch.models import FetchRequest, FetchResult


class _FakeFetchProvider:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    async def fetch(self, request: FetchRequest) -> FetchResult:
        url = str(request.url)
        body = self.pages[url].encode("utf-8")
        return FetchResult(
            url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=body,
            encoding="utf-8",
            content_type="text/html; charset=utf-8",
            content_length=len(body),
            fetch_duration=0.0,
            timestamp="2026-08-05T00:00:00+00:00",
        )


@asynccontextmanager
async def _local_http_server() -> Callable[[str], str]:
    pages = {
        "/": ('<html><head><title>Home</title></head><body><a href="/about">About</a></body></html>'),
        "/about": ('<html><head><title>About</title></head><body><a href="/">Home</a></body></html>'),
    }

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_line = await reader.readline()
        path = request_line.decode("ascii", errors="ignore").split(" ")[1]
        while True:
            line = await reader.readline()
            if line in {b"\r\n", b"\n", b""}:
                break
        body = pages.get(path, "<html><body>missing</body></html>")
        payload = body.encode("utf-8")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n" + f"Content-Length: {len(payload)}\r\n".encode("ascii") + b"Connection: close\r\n\r\n" + payload)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    base = f"http://{host}:{port}"
    try:
        yield lambda path: f"{base}{path}"
    finally:
        server.close()
        await server.wait_closed()


class _DiscoverySource:
    def iter_entry_points(self, group: str):
        assert group == "mirror"
        return [
            ("fetch", lambda: fetch_capability),
            ("crawl", lambda: crawl_capability),
            (
                "fetch-httpx",
                lambda: ProviderManifest(
                    name="httpx",
                    capability="fetch",
                    capability_api="~=1.0",
                    factory="mirror_fetch_httpx.provider:HTTPXProvider",
                    settings_model="mirror_fetch_httpx.settings:HTTPXSettings",
                    metadata={"version": "1.0.0"},
                ),
            ),
            (
                "crawl-local",
                lambda: ProviderManifest(
                    name="local",
                    capability="crawl",
                    capability_api="~=1.0",
                    factory="mirror_crawl_local.provider:LocalCrawlProvider",
                    settings_model=CrawlSettings,
                    metadata={"version": "1.0.0"},
                ),
            ),
        ]


@pytest.mark.asyncio
async def test_crawl_persists_discovered_urls() -> None:
    provider = LocalCrawlProvider(
        fetch=_FakeFetchProvider(
            {
                "https://example.com/": ('<html><head><title>Home</title></head><body><a href="/about">About</a></body></html>'),
                "https://example.com/about": ('<html><head><title>About</title></head><body><a href="/">Home</a></body></html>'),
            }
        )
    )
    result = await provider.crawl(CrawlRequest(url="https://example.com", max_depth=1, max_pages=5))
    assert result.visited_urls[0] in {"https://example.com", "https://example.com/"}
    assert result.discovered_urls


@pytest.mark.asyncio
async def test_crawl_runner_adapts_provider() -> None:
    provider = LocalCrawlProvider(
        fetch=_FakeFetchProvider(
            {
                "https://example.com/": "<html><body><a href='/about'>About</a></body></html>",
                "https://example.com/about": "<html><body>About</body></html>",
            }
        )
    )
    result = await crawl_site(provider, CrawlRequest(url="https://example.com", max_depth=1, max_pages=5))
    assert result.visited_urls


@pytest.mark.asyncio
async def test_crawl_using_real_local_provider() -> None:
    async with _local_http_server() as url_for:
        provider = LocalCrawlProvider(
            fetch=_FakeFetchProvider(
                {
                    url_for("/"): "<html><body><a href='/about'>About</a></body></html>",
                    url_for("/about"): "<html><body>About</body></html>",
                }
            )
        )
        result = await provider.crawl(CrawlRequest(url=url_for("/"), max_depth=1, max_pages=5))
        assert result.visited_urls


@pytest.mark.asyncio
async def test_local_crawl_persists_when_stores_supplied(tmp_path) -> None:
    metadata_store = InMemoryMetadataStore()
    blob_store = FileSystemBlobStore(tmp_path / "blobs")
    provider = LocalCrawlProvider(
        fetch=_FakeFetchProvider(
            {
                "https://example.com/": ('<html><head><title>Home</title></head><body><a href="/about">About</a></body></html>'),
                "https://example.com/about": ("<html><head><title>About</title></head><body></body></html>"),
            }
        )
    )
    result = await provider.crawl(
        CrawlRequest(url="https://example.com", max_depth=1, max_pages=5),
        metadata_store=metadata_store,
        blob_store=blob_store,
    )
    assert result.stored_urls == 2
    assert result.stored_pages == 2
    records = metadata_store.list(namespace="crawl.urls")
    assert {record.key for record in records} == {
        "https://example.com/",
        "https://example.com/about",
    }
    stored_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(stored_files) == 2


@pytest.mark.asyncio
async def test_crawl_persistence_wired_through_real_composition(tmp_path) -> None:
    registry = ExtensionRegistryManager()
    registry.register_capability(fetch_capability)
    registry.register_capability(crawl_capability)
    registry.register_provider(crawl_provider_manifest)
    pipeline = Pipeline(
        id="crawl-persist",
        inputs={"url": "str"},
        steps=[
            Step(
                id="crawl",
                capability="crawl",
                provider="local",
                input={
                    "url": "$pipeline.url",
                    "max_depth": 1,
                    "max_pages": 5,
                    "persist_discovered_urls": True,
                    "store_pages": True,
                },
                outputs=["result"],
            )
        ],
    )
    plan = Planner(registry).plan(pipeline)
    metadata_store = InMemoryMetadataStore()
    blob_store = FileSystemBlobStore(tmp_path / "blobs")
    executor = Executor(
        {
            ("crawl", "local"): LocalCrawlProvider(
                fetch=_FakeFetchProvider(
                    {
                        "https://example.com/": ('<html><head><title>Home</title></head><body><a href="/about">About</a></body></html>'),
                        "https://example.com/about": ("<html><head><title>About</title></head><body></body></html>"),
                    }
                )
            )
        },
        metadata_store=metadata_store,
        blob_store=blob_store,
    )
    result = await executor.execute_run(plan, inputs={"url": "https://example.com"})
    assert result.outcome is RunOutcome.SUCCEEDED
    payload = result.results["crawl"].payload
    assert payload.stored_urls == 2
    assert payload.stored_pages == 2
    records = metadata_store.list(namespace="crawl.urls")
    assert {record.key for record in records} == {
        "https://example.com/",
        "https://example.com/about",
    }
    stored_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(stored_files) == 2
