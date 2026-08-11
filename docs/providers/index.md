# Provider reference

Providers are concrete implementations. Industry-backed providers name their upstream dependency; memory/hash/local/basic providers are explicitly reference implementations.

## Fetch

- [mirror_fetch_httpx](../../packages/mirror_fetch_httpx/README.md) — HTTPX provider for Mirror Fetch
- [mirror_fetch_curl_cffi](../../packages/mirror_fetch_curl_cffi/README.md) — curl_cffi/libcurl provider for Mirror Fetch
- [mirror_fetch_playwright](../../packages/mirror_fetch_playwright/README.md) — Playwright browser provider for Mirror Fetch

## Crawl

- [mirror_crawl_local](../../packages/mirror_crawl_local/README.md) — Local (httpx) crawl provider for Mirror Crawl
- [mirror_crawl_scrapy](../../packages/mirror_crawl_scrapy/README.md) — Scrapy provider for Mirror Crawl
- [mirror_crawl_playwright](../../packages/mirror_crawl_playwright/README.md) — Playwright browser crawl provider

## Archive

- [mirror_archive_warc](../../packages/mirror_archive_warc/README.md) — WARC provider for Mirror Archive capability

## Scrape

- [mirror_scrape_basic](../../packages/mirror_scrape_basic/README.md) — Basic HTML scrape provider for Mirror Scrape

## Analyze / Diff / Dedup / Enrich / Normalize / Chunk / Transform

- [mirror_analyze_basic](../../packages/mirror_analyze_basic/README.md) — Basic provider for Mirror Analyze
- [mirror_diff_text](../../packages/mirror_diff_text/README.md) — Text diff provider for Mirror Diff
- [mirror_dedup_hash](../../packages/mirror_dedup_hash/README.md) — Hash deduplication provider for Mirror Dedup
- [mirror_enrich_text](../../packages/mirror_enrich_text/README.md) — Text enrichment provider for Mirror Enrich
- [mirror_normalize_text](../../packages/mirror_normalize_text/README.md) — Text normalization provider for Mirror Normalize
- [mirror_chunk_text](../../packages/mirror_chunk_text/README.md) — Fixed-size token chunk provider for Mirror Chunk
- [mirror_chunk_semantic](../../packages/mirror_chunk_semantic/README.md) — Embedding-aware semantic chunk provider
- [mirror_transform_map](../../packages/mirror_transform_map/README.md) — Field-mapping transform provider for Mirror Transform

## Embedding / LLM

- [mirror_embedding_hash](../../packages/mirror_embedding_hash/README.md) — Deterministic hash embedding provider
- [mirror_embedding_ollama](../../packages/mirror_embedding_ollama/README.md) — Ollama embedding provider
- [mirror_embedding_transformers](../../packages/mirror_embedding_transformers/README.md) — Sentence-transformers embedding provider
- [mirror_llm_ollama](../../packages/mirror_llm_ollama/README.md) — Ollama LLM generation provider

## Vector store / Retrieval / Search

- [mirror_vectorstore_memory](../../packages/mirror_vectorstore_memory/README.md) — In-memory vector store provider
- [mirror_vectorstore_chroma](../../packages/mirror_vectorstore_chroma/README.md) — Chroma vector store provider
- [mirror_vectorstore_pgvector](../../packages/mirror_vectorstore_pgvector/README.md) — PostgreSQL + pgvector vector store provider
- [mirror_retrieval_memory](../../packages/mirror_retrieval_memory/README.md) — In-memory retrieval provider
- [mirror_retrieval_bm25](../../packages/mirror_retrieval_bm25/README.md) — BM25 lexical retrieval provider
- [mirror_retrieval_hybrid](../../packages/mirror_retrieval_hybrid/README.md) — Hybrid lexical + semantic retrieval provider
- [mirror_search_memory](../../packages/mirror_search_memory/README.md) — In-memory search provider
- [mirror_search_sqlite](../../packages/mirror_search_sqlite/README.md) — SQLite FTS5 search provider
- [mirror_search_opensearch](../../packages/mirror_search_opensearch/README.md) — OpenSearch search provider

## Monitor

- [mirror_monitor_memory](../../packages/mirror_monitor_memory/README.md) — HTTP monitor provider for Mirror Monitor

## Compliance / Provenance / Privacy

- [mirror_compliance_rules](../../packages/mirror_compliance_rules/README.md) — Rules-based compliance provider
- [mirror_provenance_resource](../../packages/mirror_provenance_resource/README.md) — Resource provenance provider
- [mirror_privacy_guard_presidio](../../packages/mirror_privacy_guard_presidio/README.md) — Presidio PII detection/redaction provider

## Database

- [mirror_database_sqlite](../../packages/mirror_database_sqlite/README.md) — SQLite backend for the Mirror database contract
