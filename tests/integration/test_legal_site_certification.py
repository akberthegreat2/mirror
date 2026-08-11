"""Live certification against legal reference sites (ADR-0049 gate).

These tests exercise the real Mirror providers (httpx, curl_cffi, Playwright
fetch/crawl, Scrapy crawl, WARC archive, knowledge and RAG pipelines) against
the Tier 1/2 sites in docs/testing/LEGAL_TEST_SITES.md. They are opt-in: run
with
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


def _ollama_ready() -> bool:
    import httpx

    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        r.raise_for_status()
        return bool(r.json().get("models"))
    except Exception:
        return False


def _sentence_transformers_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


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

    async def test_scrapethissite_index(self, scrapethissite_index: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_html

        assert_ok(scrapethissite_index)
        html = assert_html(scrapethissite_index)
        assert "scrape" in html.lower() or "learn web scraping" in html.lower()

    async def test_scrapethissite_simple(self, scrapethissite_simple: object) -> None:
        from mirror_testing.legal_sites import assert_ok, assert_html

        assert_ok(scrapethissite_simple)
        html = assert_html(scrapethissite_simple)
        assert "countries" in html.lower() or "capital" in html.lower()


class TestProviderCompositionCertification:
    """Real Mirror providers against legal sites."""

    async def test_httpx_fetch_provider(self, live_httpx_fetch: object) -> None:
        """The actual HTTPXProvider fetches a legal site end-to-end."""
        from mirror_fetch.models import FetchRequest

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

    async def test_curl_cffi_fetch_provider(self, live_curl_fetch: object) -> None:
        """The real curl_cffi/libcurl stack fetches a legal site."""
        from mirror_fetch.models import FetchRequest

        provider = live_curl_fetch
        result = await provider.fetch(FetchRequest(url="https://httpbin.org/get"))
        assert result.status_code == 200
        assert result.content

    async def test_curl_cffi_fetch_books(self, live_curl_fetch: object) -> None:
        from mirror_fetch.models import FetchRequest

        provider = live_curl_fetch
        result = await provider.fetch(FetchRequest(url="http://books.toscrape.com/"))
        assert result.status_code == 200
        assert result.content
        assert b"books" in result.content.lower()

    async def test_playwright_fetch_renders_js_site(self, live_playwright_fetch: object) -> None:
        """Playwright fetch renders a legal site in a real browser."""
        from mirror_fetch.models import FetchRequest

        provider = live_playwright_fetch
        result = await provider.fetch(FetchRequest(url="https://scrapethissite.com/"))
        assert result.status_code == 200
        assert result.content
        assert len(result.content) > 0

    async def test_local_crawl_provider(self, live_local_crawl: object) -> None:
        """Local crawl provider (real httpx fetch) crawls a legal site."""
        from mirror_crawl.models import CrawlRequest

        provider = live_local_crawl
        result = await provider.crawl(
            CrawlRequest(url="http://books.toscrape.com/", max_pages=3, max_depth=1)
        )
        assert result.discovered_urls
        assert len(result.visited_urls) >= 1
        assert result.seed_url == "http://books.toscrape.com/"

    async def test_scrapy_crawl_provider(self, live_scrapy_crawl: object) -> None:
        """The real Scrapy engine crawls a legal site."""
        import pytest as _pytest

        scrapy = _pytest.importorskip("scrapy")
        from mirror_crawl.models import CrawlRequest

        provider = live_scrapy_crawl
        result = await provider.crawl(
            CrawlRequest(url="http://quotes.toscrape.com/", max_pages=3, max_depth=1)
        )
        assert result.discovered_urls
        assert len(result.visited_urls) >= 1

    async def test_playwright_crawl_provider(self, live_playwright_crawl: object) -> None:
        """Playwright crawl drives a real browser over a legal site."""
        from mirror_crawl.models import CrawlRequest

        provider = live_playwright_crawl
        result = await provider.crawl(
            CrawlRequest(url="http://books.toscrape.com/", max_pages=3, max_depth=1)
        )
        assert result.discovered_urls
        assert len(result.visited_urls) >= 1


class TestArchiveCertification:
    """WARC archive of real fetched content (LAB Level 5)."""

    async def test_warc_archive_of_real_page(
        self, live_httpx_fetch: object, live_warc_archive: object
    ) -> None:
        """Fetch a legal site then archive the response with real warcio."""
        from mirror_archive.models import ArchivePayload, ArchiveRequest
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        assert fetch_result.status_code == 200

        provider = live_warc_archive
        result = await provider.archive(
            ArchiveRequest(
                resource_id=__import__("uuid").uuid4(),
                payload=ArchivePayload(
                    content=fetch_result.content,
                    target_uri="http://books.toscrape.com/",
                    media_type=fetch_result.content_type,
                    headers={"Content-Type": fetch_result.content_type},
                ),
                metadata={"source": "legal-site-certification", "url": "http://books.toscrape.com/"},
            )
        )
        assert result.path

        # Read the WARC back with real warcio.
        import pathlib

        from warcio.archiveiterator import ArchiveIterator

        warc_path = pathlib.Path(result.path)
        with open(warc_path, "rb") as handle:
            records = [
                (record.rec_type, record.content_stream().read())
                for record in ArchiveIterator(handle)
            ]
        assert len(records) == 1
        rec_type, payload = records[0]
        assert rec_type == "resource"
        assert fetch_result.content in payload


class TestContentPipelineCertification:
    """Deterministic knowledge capabilities over real fetched content."""

    async def test_scrape_basic_on_books(self, live_httpx_fetch: object) -> None:
        from mirror_fetch.models import FetchRequest
        from mirror_scrape.models import ScrapeRequest
        from mirror_scrape_basic.provider import BasicScrapeProvider

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        assert fetch_result.status_code == 200

        result = await BasicScrapeProvider().scrape(
            ScrapeRequest(
                html=fetch_result.content.decode("utf-8", errors="replace"),
                url="http://books.toscrape.com/",
            )
        )
        assert result.document
        assert result.document.text
        assert "book" in result.document.text.lower()

    async def test_diff_on_real_versions(self, live_httpx_fetch: object) -> None:
        from mirror_diff.models import DiffRequest
        from mirror_diff_text.provider import TextDiffProvider
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")

        result = await TextDiffProvider().diff(
            DiffRequest(before=text, after=text.replace("A Light in the Attic", "Changed Title"))
        )
        assert result.summary.changed is True
        assert result.summary.added_lines
        assert result.summary.removed_lines

    async def test_dedup_on_real_text(self, live_httpx_fetch: object) -> None:
        from mirror_dedup.models import DedupDocument, DedupRequest
        from mirror_dedup_hash.provider import HashDedupProvider
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")

        docs = [
            DedupDocument(document_id="a", text=text),
            DedupDocument(document_id="b", text=text),
            DedupDocument(document_id="c", text="completely different text"),
        ]
        result = await HashDedupProvider().dedup(DedupRequest(documents=docs))
        assert result.removed_count == 1
        assert len(result.documents) == 2

    async def test_analyze_on_real_content(self, live_httpx_fetch: object) -> None:
        from mirror_analyze.models import AnalyzeRequest
        from mirror_analyze_basic.provider import BasicAnalyzeProvider
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")

        result = await BasicAnalyzeProvider().analyze(AnalyzeRequest(text=text))
        assert result.analysis
        assert result.analysis.token_count > 0

    async def test_enrich_on_real_content(self, live_httpx_fetch: object) -> None:
        from mirror_enrich.models import EnrichmentDocument, EnrichmentRequest
        from mirror_enrich_text.provider import TextEnrichmentProvider
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")

        result = await TextEnrichmentProvider().enrich(
            EnrichmentRequest(
                documents=[EnrichmentDocument(document_id="books", text=text)]
            )
        )
        assert result.documents
        assert result.documents[0].enriched_text

    async def test_transform_on_real_content(self, live_httpx_fetch: object) -> None:
        from mirror_fetch.models import FetchRequest
        from mirror_transform.models import TransformRequest
        from mirror_transform_map.provider import MapTransformProvider

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")
        result = await MapTransformProvider().transform(
            TransformRequest(
                value={"url": "http://books.toscrape.com/", "content": text},
                output_type="mirror_transform_map.test_outputs:MappedDocument",
                mapping={"document_id": "url", "text": "content"},
            )
        )
        assert result.value.document_id == "http://books.toscrape.com/"
        assert result.value.text

    async def test_compliance_on_real_content(self, live_httpx_fetch: object) -> None:
        from mirror_compliance.models import ComplianceDocument, ComplianceRequest, ComplianceRule
        from mirror_compliance_rules.provider import RulesComplianceProvider
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")

        result = await RulesComplianceProvider().check(
            ComplianceRequest(
                documents=[
                    ComplianceDocument(document_id="books", text=text, metadata={"source": "books"})
                ],
                rules=[
                    ComplianceRule(
                        rule_id="has-source",
                        required_metadata_keys=("source",),
                    )
                ],
            )
        )
        assert result.assessments[0].compliant is True

    async def test_provenance_on_real_fetch(self, live_httpx_fetch: object) -> None:
        from mirror_fetch.models import FetchRequest
        from mirror_provenance.models import ProducerRef, ProvenanceInput, ProvenanceRequest
        from mirror_provenance_resource.provider import ResourceProvenanceProvider
        from pydantic import BaseModel

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        assert fetch_result.status_code == 200

        class PagePayload(BaseModel):
            url: str
            status_code: int
            content_type: str | None

        result = await ResourceProvenanceProvider().provenance(
            ProvenanceRequest(
                envelopes=[
                    ProvenanceInput(
                        resource_type="page",
                        schema_version="1.0",
                        payload=PagePayload(
                            url="http://books.toscrape.com/",
                            status_code=fetch_result.status_code,
                            content_type=fetch_result.content_type,
                        ),
                        producer=ProducerRef(
                            capability="fetch",
                            capability_version="1.0",
                            provider="httpx",
                            provider_version="1.0",
                        ),
                    )
                ]
            )
        )
        assert result.envelopes
        assert result.envelopes[0].resource_id
        assert result.envelopes[0].payload.url == "http://books.toscrape.com/"


class TestReferenceProviderCertification:
    """Deterministic reference providers exercised on real fetched content."""

    async def test_hash_embedding_on_real_text(self, live_httpx_fetch: object) -> None:
        from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
        from mirror_embedding_hash.provider import HashEmbeddingProvider
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")

        result = await HashEmbeddingProvider().embed(
            EmbeddingRequest(
                items=[EmbeddingInput(item_id="books", text=text[:5000])]
            )
        )
        assert result.vectors
        assert len(result.vectors[0].values) > 0

    async def test_bm25_on_real_chunks(self, live_httpx_fetch: object) -> None:
        from mirror_chunk.models import ChunkDocument, ChunkRequest
        from mirror_chunk_text.provider import TextChunkProvider
        from mirror_fetch.models import FetchRequest
        from mirror_retrieval.models import RetrievalRequest
        from mirror_retrieval_bm25.provider import Bm25RetrievalProvider
        from mirror_retrieval_bm25.settings import Bm25Document, Bm25RetrievalSettings

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        html_text = fetch_result.content.decode("utf-8", errors="replace")
        chunked = await TextChunkProvider().chunk(
            ChunkRequest(
                documents=[ChunkDocument(document_id="books", text=html_text, metadata={})]
            )
        )
        assert chunked.chunks

        documents = [
            Bm25Document(
                record_id=c.chunk_id,
                document_id="books",
                text=c.text,
                metadata={},
            )
            for c in chunked.chunks
        ]
        provider = Bm25RetrievalProvider(
            Bm25RetrievalSettings(documents=documents, default_top_k=5)
        )
        result = await provider.retrieve(RetrievalRequest(query="catalogue price book"))
        assert result.matches

    async def test_memory_search_on_real_text(self, live_httpx_fetch: object) -> None:
        from mirror_fetch.models import FetchRequest
        from mirror_search.models import SearchRequest
        from mirror_search_memory.provider import SearchMemoryProvider

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        text = fetch_result.content.decode("utf-8", errors="replace")

        provider = SearchMemoryProvider()
        provider._index.add("books-index", text=text, title="Books catalogue")
        result = await provider.search(SearchRequest(query="book catalogue"))
        assert result.hits
        assert result.total > 0

    async def test_hybrid_retrieval_on_real_chunks(
        self, live_httpx_fetch: object
    ) -> None:
        from mirror_chunk.models import ChunkDocument, ChunkRequest
        from mirror_chunk_text.provider import TextChunkProvider
        from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
        from mirror_embedding_hash.provider import HashEmbeddingProvider
        from mirror_fetch.models import FetchRequest
        from mirror_retrieval.models import RetrievalRequest
        from mirror_retrieval_bm25.provider import Bm25RetrievalProvider
        from mirror_retrieval_bm25.settings import Bm25Document, Bm25RetrievalSettings
        from mirror_retrieval_hybrid.provider import HybridRetrievalProvider, _VectorRetriever
        from mirror_vectorstore.models import VectorRecord, VectorUpsertRequest
        from mirror_vectorstore_memory.provider import MemoryVectorStoreProvider

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        html_text = fetch_result.content.decode("utf-8", errors="replace")
        chunked = await TextChunkProvider().chunk(
            ChunkRequest(
                documents=[ChunkDocument(document_id="books", text=html_text, metadata={})]
            )
        )
        assert chunked.chunks

        embedder = HashEmbeddingProvider()
        embedded = await embedder.embed(
            EmbeddingRequest(
                items=[
                    EmbeddingInput(item_id=c.chunk_id, text=c.text)
                    for c in chunked.chunks[:20]
                ]
            )
        )
        store = MemoryVectorStoreProvider()
        await store.upsert(
            VectorUpsertRequest(
                namespace="books",
                records=[
                    VectorRecord(
                        record_id=v.item_id,
                        vector=v.values,
                        document_id="books",
                        text=next(c.text for c in chunked.chunks[:20] if c.chunk_id == v.item_id),
                    )
                    for v in embedded.vectors
                ],
            )
        )

        lexical = Bm25RetrievalProvider(
            Bm25RetrievalSettings(
                documents=[
                    Bm25Document(
                        record_id=c.chunk_id,
                        document_id="books",
                        text=c.text,
                        metadata={},
                    )
                    for c in chunked.chunks[:20]
                ],
                default_top_k=5,
            )
        )
        semantic = _VectorRetriever(embedder, store, settings=None)
        hybrid = HybridRetrievalProvider(lexical=lexical, semantic=semantic)
        result = await hybrid.retrieve(RetrievalRequest(query="books catalogue", top_k=5))
        assert result.matches

    @pytest.mark.skipif(
        not _sentence_transformers_available(), reason="sentence-transformers not installed"
    )
    async def test_semantic_chunk_on_real_text(self, live_httpx_fetch: object) -> None:
        from mirror_chunk.models import ChunkDocument, ChunkRequest
        from mirror_chunk_semantic.provider import SemanticChunkProvider
        from mirror_fetch.models import FetchRequest

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
        html_text = fetch_result.content.decode("utf-8", errors="replace")
        # Bound the corpus so real model inference stays quick.
        text = html_text[:4000]

        result = await SemanticChunkProvider().chunk(
            ChunkRequest(
                documents=[ChunkDocument(document_id="books", text=text, metadata={})]
            )
        )
        assert result.chunks
        assert any(c.text for c in result.chunks)

    async def test_monitor_provider_real_httpbin(self) -> None:
        """The actual MemoryMonitorProvider checks a live legal site."""
        from mirror_monitor.models import MonitorRequest
        from mirror_monitor_memory.provider import MemoryMonitorProvider

        provider = MemoryMonitorProvider()
        first = await provider.check(MonitorRequest(url="https://httpbin.org/get"))
        assert first.snapshot.status_code == 200
        assert first.snapshot.body_sha256
        assert first.snapshot.changed is True  # first sight of the resource

        second = await provider.check(MonitorRequest(url="https://httpbin.org/get"))
        assert second.snapshot.changed is False


class TestRagPipelineCertification:
    """End-to-end RAG pipeline against real content and real backends."""

    @pytest.mark.skipif(not _ollama_ready(), reason="Ollama with models not reachable")
    async def test_rag_pipeline_ollama(self, live_httpx_fetch: object) -> None:
        """Fetch -> normalize -> chunk -> embed (Ollama) -> vectorstore -> retrieve -> LLM."""
        from mirror_chunk.models import ChunkDocument, ChunkRequest
        from mirror_chunk_text.provider import TextChunkProvider
        from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
        from mirror_embedding_ollama.provider import OllamaEmbeddingProvider
        from mirror_fetch.models import FetchRequest
        from mirror_llm.models import LLMRequest
        from mirror_llm_ollama.provider import OllamaLLMProvider
        from mirror_normalize.models import NormalizationDocument, NormalizationRequest
        from mirror_normalize_text.provider import TextNormalizationProvider
        from mirror_retrieval.models import RetrievalRequest
        from mirror_retrieval_memory.provider import MemoryRetrievalProvider
        from mirror_vectorstore.models import (
            VectorQueryRequest,
            VectorRecord,
            VectorUpsertRequest,
        )
        from mirror_vectorstore_memory.provider import MemoryVectorStoreProvider

        fetch_result = await live_httpx_fetch.fetch(
            FetchRequest(url="http://books.toscrape.com/")
        )
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
        text = normalized.documents[0].normalized_text

        chunker = TextChunkProvider()
        chunked = await chunker.chunk(
            ChunkRequest(
                documents=[ChunkDocument(document_id="books-index", text=text, metadata={})]
            )
        )
        assert chunked.chunks

        embedder = OllamaEmbeddingProvider()
        embedded = await embedder.embed(
            EmbeddingRequest(
                items=[
                    EmbeddingInput(item_id=c.chunk_id, text=c.text)
                    for c in chunked.chunks[:5]
                ]
            )
        )
        assert embedded.vectors

        store = MemoryVectorStoreProvider()
        await store.upsert(
            VectorUpsertRequest(
                namespace="books",
                records=[
                    VectorRecord(
                        record_id=v.item_id,
                        vector=v.values,
                        document_id=v.item_id,
                        text=next(
                            c.text for c in chunked.chunks if c.chunk_id == v.item_id
                        ),
                    )
                    for v in embedded.vectors
                ],
            )
        )
        query_result = await store.query(
            VectorQueryRequest(namespace="books", vector=list(embedded.vectors[0].values), top_k=3)
        )
        assert query_result.matches

        retrieval = MemoryRetrievalProvider(vector_store=store, embedder=embedder)
        retrieved = await retrieval.retrieve(
            RetrievalRequest(query="books catalogue", top_k=3, namespace="books")
        )
        assert retrieved.matches

        llm = OllamaLLMProvider()
        generated = await llm.generate(
            LLMRequest(text="Summarize this catalogue: " + retrieved.matches[0].text[:500])
        )
        await llm._close()
        assert generated.text
