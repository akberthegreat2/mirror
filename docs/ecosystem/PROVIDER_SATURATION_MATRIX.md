# Provider Saturation Matrix

This is the authoritative list of every Mirror capability and the industry-grade
providers that implement it. It is the saturation contract behind ADR-0046,
ADR-0047, and ADR-0051 (reference provider retirement), and it is the checklist
we implement before the beta release gate (ADR-0049).

The rule is the user's promise and the kernel's:

> Mirror does not invent libraries from scratch. Every production provider wraps
> an existing, industry-grade tool through its published interface.

Reference providers (deterministic, in-memory, or hash-based) are retired from
the shipped catalog (ADR-0051): they are no longer provider-of-record packages.
Deterministic doubles exist only as test-only helpers inside the test suite or
`mirror_testing`.

## Legend

| Mark | Meaning |
|---|---|
| ✅ | provider implemented in the repo today |
| 🔧 | provider exists but has a known defect being fixed in ADR-0050 |
| 🟦 | provider specified in ADR-0046 / ADR-0047, to be implemented (new package) |
| 🚫 | reference/deterministic provider — retired, replaced by the industry-grade rows below it (ADR-0051) |
| **★** | flagship capability (needs ≥3 swappable providers by the beta gate, ADR-0046 §3) |

Each industry-grade provider row names the wrapped tool in parentheses.

The retired reference rows remain in the matrix only to document what was
replaced. They are no longer shipped as provider-of-record packages.

---

## Web infrastructure

### fetch ★
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_fetch_httpx` | httpx (async HTTP client) | ✅ |
| `mirror_fetch_playwright` | Playwright (real browser) | ✅ |
| `mirror_fetch_curl_cffi` | curl_cffi / curl-impersonate (TLS-fingerprint HTTP) | 🟦 |

### crawl ★
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_crawl_local` | httpx (composed fetch; real HTTP crawler) | 🔧 F6 persistence wiring |
| `mirror_crawl_scrapy` | Scrapy (real crawl engine) | 🔧 F9 async `start` |
| `mirror_crawl_playwright` | Playwright (browser crawl) | 🟦 |

### archive
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_archive_warc` | warcio (WARC read/write) | ✅ |
| `mirror_archive_singlefile` | single-file (complete-page HTML snapshot) | 🟦 |
| `mirror_archive_playwright` | Playwright (PDF / screenshot / MHTML capture) | 🟦 |

### scrape
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_scrape_basic` | — (own parser) | 🚫 retired (ADR-0051) |
| `mirror_scrape_bs4` | beautifulsoup4 (HTML parsing) | 🟦 |
| `mirror_scrape_parsel` | parsel (XPath/CSS selectors) | 🟦 |
| `mirror_scrape_selectolax` | selectolax (fast HTML parsing) | 🟦 |

### analyze
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_analyze_basic` | — (own heuristics) | 🚫 retired (ADR-0051) |
| `mirror_analyze_spacy` | spaCy (NLP / linguistic analysis) | 🟦 |
| `mirror_analyze_readability` | readability-lxml (main-content extraction) | 🟦 |
| `mirror_analyze_trafilatura` | trafilatura (web text extraction) | 🟦 |

### diff
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_diff_text` | — (own line diff) | 🚫 retired (ADR-0051) |
| `mirror_diff_deepdiff` | deepdiff (deep object diff) | 🟦 |
| `mirror_diff_matchpatch` | diff-match-patch (Google, patch/diff) | 🟦 |
| `mirror_diff_jsondiff` | jsondiff (JSON diff) | 🟦 |

### monitor
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_monitor_memory` | httpx + in-memory state | 🚫 retired (ADR-0051) |
| `mirror_monitor_httpx` | httpx (real HTTP checks + change detection) | 🟦 |
| `mirror_monitor_playwright` | Playwright (browser checks) | 🟦 |
| `mirror_monitor_otel` | OpenTelemetry (metrics exporter) | 🟦 |

### transform
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_transform_map` | — (own mapping) | 🚫 retired (ADR-0051) |
| `mirror_transform_jmespath` | jmespath (JSON query) | 🟦 |
| `mirror_transform_jsonpath` | jsonpath-ng (JSONPath) | 🟦 |
| `mirror_transform_jinja` | Jinja2 (template rendering) | 🟦 |

---

## Knowledge / RAG

### normalize
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_normalize_text` | — (own rules) | 🚫 retired (ADR-0051) |
| `mirror_normalize_ftfy` | ftfy (mojibake/encoding repair) | 🟦 |
| `mirror_normalize_html2text` | html2text (HTML → text) | 🟦 |
| `mirror_normalize_html_text` | html-text (tag-aware text extraction) | 🟦 |

### enrich
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_enrich_text` | — (own keyword rules) | 🚫 retired (ADR-0051) |
| `mirror_enrich_spacy` | spaCy (NER / entity enrichment) | 🟦 |
| `mirror_enrich_keybert` | keybert (keyphrase extraction) | 🟦 |
| `mirror_enrich_llm` | Ollama / OpenAI-compatible LLM (extraction) | 🟦 |

### chunk
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_chunk_text` | — (own splitter) | 🚫 retired (ADR-0051) |
| `mirror_chunk_semantic` | embedding model (semantic chunking, ADR-0047) | 🟦 |
| `mirror_chunk_token` | tiktoken (token-aware splitting) | 🟦 |
| `mirror_chunk_langchain` | langchain-text-splitters (recursive/document) | 🟦 |

### dedup
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_dedup_hash` | — (own content hash) | 🚫 retired (ADR-0051) |
| `mirror_dedup_simhash` | simhash (near-duplicate detection) | 🟦 |
| `mirror_dedup_minhash` | datasketch (MinHash LSH) | 🟦 |
| `mirror_dedup_embedding` | embedding model (semantic similarity dedup) | 🟦 |

### embedding ★
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_embedding_hash` | — (own hash vectors) | 🚫 retired (ADR-0051) |
| `mirror_embedding_ollama` | Ollama (nomic-embed-text class) | 🟦 |
| `mirror_embedding_sentence_transformers` | sentence-transformers | 🟦 |
| `mirror_embedding_openai` | OpenAI-compatible embedding API (optional plugin) | 🟦 |

### vectorstore ★
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_vectorstore_memory` | — (in-memory) | 🚫 retired (ADR-0051) |
| `mirror_vectorstore_pgvector` | pgvector (PostgreSQL) | 🟦 |
| `mirror_vectorstore_chroma` | Chroma | 🟦 |
| `mirror_vectorstore_qdrant` | Qdrant | 🟦 |

### retrieval ★
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_retrieval_memory` | — (in-memory, composed) | 🚫 retired (ADR-0051) |
| `mirror_retrieval_bm25` | rank_bm25 (lexical retrieval) | 🟦 |
| `mirror_retrieval_hybrid` | BM25 + vector fusion (ADR-0047) | 🟦 |
| `mirror_retrieval_rerank` | sentence-transformers CrossEncoder (reranking) | 🟦 |

### search ★
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_search_memory` | — (in-memory inverted index) | 🚫 retired (ADR-0051) |
| `mirror_search_opensearch` | OpenSearch (opensearch-py) | 🟦 + P1.5 extra |
| `mirror_search_elasticsearch` | Elasticsearch (elasticsearch-py) | 🟦 |
| `mirror_search_postgres_fts` | PostgreSQL full-text search | 🟦 |

### provenance
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_provenance_resource` | — (immutable resource envelope) | 🚫 retired (ADR-0051) |
| `mirror_provenance_w3c` | W3C PROV serialization | 🟦 |
| `mirror_provenance_warc` | warcio (tie provenance to archive records) | 🟦 |
| `mirror_provenance_openlineage` | OpenLineage (data lineage events) | 🟦 |

### compliance
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_compliance_rules` | — (own rule engine) | 🚫 retired (ADR-0051) |
| `mirror_compliance_presidio` | Microsoft Presidio (PII detection) | 🟦 |
| `mirror_compliance_robots` | reppy / robotexclusionrulesparser (robots.txt policy) | 🟦 |
| `mirror_compliance_license` | scancode / license-expression (license detection) | 🟦 |

---

## New capabilities (ADR-0047)

### llm
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_llm_ollama` | Ollama (qwen2.5:0.5b class) | 🟦 |
| `mirror_llm_openai` | OpenAI-compatible chat API (optional plugin) | 🟦 |
| `mirror_llm_transformers` | HuggingFace transformers | 🟦 |

### privacy_guard
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_privacy_guard_presidio` | Microsoft Presidio (analyzer + anonymizer) | 🟦 |
| `mirror_privacy_guard_scrubadub` | scrubadub (regex PII scrubber) | 🟦 |
| `mirror_privacy_guard_llm` | LLM-based redaction | 🟦 |

### ocr
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_ocr_tesseract` | Tesseract (pytesseract) | 🟦 |
| `mirror_ocr_easyocr` | EasyOCR | 🟦 |
| `mirror_ocr_paddle` | PaddleOCR | 🟦 |

---

## Infrastructure (not capabilities)

Provider families that back the runtime rather than a domain capability:

| Family | Local / reference | Production |
|---|---|---|
| database backend (ADR-0042) | `mirror_database_sqlite` | `mirror_database_postgres` (psycopg3) |
| worker backend | SQLite (core) | `mirror_worker_postgres` (psycopg3) |
| execution transport | inline / SQLite | `mirror_execution_celery` (Celery + Redis) |
| control plane | — | Django admin / DRF over `mirror_control` (ADR-0043/0044/0045) |

---

## Current vs target count

Counts are industry-grade providers only — retired reference providers are not
counted (ADR-0051).

| Capability | Industry-grade today | Target (≥3) |
|---|---|---|
| fetch ★ | 2 (httpx, playwright) | 3 |
| crawl ★ | 2 (local httpx-composed, scrapy) | 3 |
| archive | 1 (warc) | 3 |
| scrape | 0 | 4 |
| analyze | 0 | 4 |
| diff | 0 | 4 |
| monitor | 0 | 4 |
| transform | 0 | 4 |
| normalize | 0 | 4 |
| enrich | 0 | 4 |
| chunk | 0 | 4 |
| dedup | 0 | 4 |
| embedding ★ | 0 | 4 |
| vectorstore ★ | 0 | 4 |
| retrieval ★ | 0 | 4 |
| search ★ | 0 | 4 |
| provenance | 0 | 4 |
| compliance | 0 | 4 |
| llm | 0 | 3 |
| privacy_guard | 0 | 3 |
| ocr | 0 | 3 |

---

## Implementation order (tied to the beta gate)

The sequence is: implement the new provider packages (wrapping the tools above),
then test the new providers against their real backends, then pass the release
gate (ADR-0049). This mirrors the milestone: **implement after `docs/testing`,
then test the new providers — that is what makes beta certifiable.**

1. **Fix the two wired defects** that make existing industry-grade providers
   non-functional on the real path: crawl persistence (F6) and Scrapy async
   start (F9) — ADR-0050.
2. **Retire the reference providers** — remove the fifteen reference packages
   from the shipped catalog and migrate their tests to real local backends or
   test-only doubles (ADR-0051).
3. **Flagship saturation first** (ADR-0046 §3): fetch, crawl, embedding,
   vectorstore, retrieval, search. These six gate the certified-beta claim.
4. **Web infrastructure** (archive, scrape, analyze, diff, monitor, transform).
5. **Knowledge preparation** (normalize, enrich, chunk, dedup).
6. **New capabilities** (llm, privacy_guard, ocr) — ADR-0047.
7. **Real-backend testing** per provider: local HTTP server, Docker containers
   (PostgreSQL, Redis, Chroma, OpenSearch, Ollama), Tesseract/PaddleOCR engines,
   and the legal test sites in `docs/testing/LEGAL_TEST_SITES.md`. Distilled
   models (`nomic-embed-text`, `qwen2.5:0.5b`) keep the lab cheap.
8. **Beta gate**: fresh-venv install, `pytest -q`, `pytest -q -m integration`,
   live legal-site certification, evidence recorded in the release handover.

Only providers with a verified real-backend test are listed as "certified"; the
rest are documented as "implemented but not externally certified" (CLAUDE.md §13,
ADR-0049 §5).
