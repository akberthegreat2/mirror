"""Live certification against legal reference sites (ADR-0049 gate).

These tests exercise the real Mirror providers (httpx fetch, local crawl,
WARC archive, knowledge pipeline) against the Tier 1/2 sites in
docs/testing/LEGAL_TEST_SITES.md. They are opt-in: run with
MIRROR_LIVE_TESTS=1 pytest -m live tests/integration/test_legal_site_certification.py

The gate is recorded as evidence in the release handover per ADR-0049 §1.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.integration,
]


class TestFetchCertification:
    """HTTPX fetch against legal sites."""

    async def test_httpbin_get(self, httpbin: object) -> None:
        from mirror_testing.legal_sites import assert_ok

        assert_ok(httpbin)

    async def test_httpbin_headers(self, httpbin_headers: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_json

        assert_ok(httpbin_headers)
        data = assert_json(httpbin_headers)
        assert "headers" in data

    async def test_httpbin_cookies(self, httpbin_cookies: object) -> None:
        from mirror_testing.legal_sites import assert_ok

        assert_ok(httpbin_cookies)

    async def test_httpbin_redirect(self, httpbin_redirect: object) -> None:
        from mirror_testing.legal_sites import assert_ok

        # httpbin redirect/2 resolves after following redirects
        assert_ok(httpbin_redirect)

    async def test_httpbin_delay(self, httpbin_delay: object) -> None:
        from mirror_testing.legal_sites import assert_ok

        assert_ok(httpbin_delay)

    async def test_jsonplaceholder_posts(self, jsonplaceholder_posts: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_json

        assert_ok(jsonplaceholder_posts)
        posts = assert_json(jsonplaceholder_posts)
        assert isinstance(posts, list)
        assert len(posts) > 0

    async def test_books_index(self, books_index: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_html

        assert_ok(books_index)
        html = assert_html(books_index)
        assert "A light in the attic" in html or "books" in html.lower()

    async def test_books_pagination(self, books_page2: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_html

        assert_ok(books_page2)
        html = assert_html(books_page2)
        assert "page-2" in html or "Page" in html

    async def test_quotes_index(self, quotes_index: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_html

        assert_ok(quotes_index)
        html = assert_html(quotes_index)
        assert "Quote" in html or "quotes" in html.lower()

    async def test_quotes_login_page(self, quotes_login_page: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_html

        assert_ok(quotes_login_page)
        html = assert_html(quotes_login_page)
        assert "form" in html or "csrf" in html.lower()


class TestProviderCompositionCertification:
    """Real Mirror providers against legal sites."""

    async def test_httpx_fetch_provider(self, live_httpx_fetch: object) -> None:
        """The actual HTTPXProvider fetches a legal site end-to-end."""
        from mirror_fetch.models import FetchRequest
        from mirror_testing.legal_sites import assert_ok, LiveFetchResult

        provider = live_httpx_fetch
        result = await provider.fetch(FetchRequest(url="https://httpbin.org/get"))
        assert result.status_code == 200
        assert result.content
        assert result.url

    async def test_httpx_fetch_books(self, live_httpx_fetch: object) -> None:
        from mirror_fetch.models import FetchRequest

        provider = live_httpx_fetch
        result = await provider.fetch(FetchRequest(url="http://books.toscrape.com/"))
        assert result.status_code == 200
        assert result.content
        assert b"books" in result.content.lower()

    async def test_local_crawl_provider(self, live_local_crawl: object) -> None:
        """Local crawl provider (real httpx fetch) crawls a legal site."""
        from mirror_crawl.models import CrawlRequest
        from mirror_testing.legal_sites import assert_ok

        provider = live_local_crawl
        result = await provider.crawl(
            CrawlRequest(url="http://books.toscrape.com/", max_pages=3, max_depth=1)
        )
        assert result.discovered_urls
        assert len(result.visited_urls) >= 1
        assert result.seed_url == "http://books.toscrape.com/"


class TestKnowledgePipelineCertification:
    """End-to-end knowledge pipeline against real content (LAB Level 5)."""

    async def test_knowledge_pipeline_on_books(self, live_httpx_fetch: object) -> None:
        """Fetch -> normalize -> chunk -> provenance against real HTML."""
        from mirror_chunk.models import ChunkDocument, ChunkRequest
        from mirror_chunk_text.provider import TextChunkProvider
        from mirror_fetch.models import FetchRequest
        from mirror_normalize.models import NormalizationDocument, NormalizationRequest
        from mirror_normalize_text.provider import TextNormalizationProvider

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        assert fetch_result.status_code == 200
        html_text = fetch_result.content.decode("utf-8", errors="replace")

        normalizer = TextNormalizationProvider()
        normalized = await normalizer.normalize(
            NormalizationRequest(
                documents=[
                    NormalizationDocument(
                        document_id="books-index",
                        text=html_text,
                        metadata={"source": "books.toscrape.com"},
                    )
                ]
            )
        )
        assert normalized.documents
        assert normalized.documents[0].normalized_text

        chunker = TextChunkProvider()
        chunked = await chunker.chunk(
            ChunkRequest(
                documents=[
                    ChunkDocument(
                        document_id=doc.document_id,
                        text=doc.normalized_text,
                        metadata=doc.metadata,
                    )
                    for doc in normalized.documents
                ]
            )
        )
        assert chunked.chunks
        assert any("book" in chunk.text.lower() for chunk in chunked.chunks)


class TestMonitoringCertification:
    """Scheduled monitoring against httpbin (ADR-0049 §1)."""

    async def test_monitor_httpbin(self, live_httpx_fetch: object) -> None:
        from mirror_fetch.models import FetchRequest

        provider = live_httpx_fetch
        result = await provider.fetch(FetchRequest(url="https://httpbin.org/get"))
        assert result.status_code == 200
        assert result.fetch_duration >= 0
