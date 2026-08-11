# Provider Saturation Matrix

This is the authoritative list of every Mirror capability and the providers that
implement it. It is the saturation contract behind ADR-0046, ADR-0047, and
ADR-0051 (reference provider retention).

The rule is the user's promise and the kernel's:

> Mirror does not invent libraries from scratch. Every production provider wraps
> an existing, industry-grade tool through its published interface.

Reference providers (deterministic, in-memory, or hash-based) are retained as
first-party packages under ADR-0051: they provide real, useful, deterministic
behavior for tests, local development, and framework verification. They are
documented as "reference" — not production-grade.

## Legend

| Mark | Meaning |
|---|---|
| ✅ | industry-grade provider — wraps an existing tool, verified against real backend |
| 📗 | reference provider — deterministic, in-memory, or hash-based (retained for tests/local dev) |
| 🟦 | planned provider — specified in ADR-0046/0047, not yet implemented |
| **★** | flagship capability — needs ≥3 swappable providers (ADR-0046 §3) |

---

## Web infrastructure

### fetch ★ (saturated: 3/3)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_fetch_httpx` | httpx (async HTTP client) | ✅ |
| `mirror_fetch_playwright` | Playwright (real browser) | ✅ |
| `mirror_fetch_curl_cffi` | curl_cffi / curl-impersonate (TLS-fingerprint HTTP) | ✅ |

### crawl ★ (2/3)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_crawl_local` | httpx (composed fetch; real HTTP crawler) | ✅ |
| `mirror_crawl_scrapy` | Scrapy (real crawl engine) | ✅ |
| `mirror_crawl_playwright` | Playwright (browser crawl) | 🟦 |

### archive (1/3)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_archive_warc` | warcio (WARC read/write) | ✅ |
| `mirror_archive_singlefile` | single-file (complete-page HTML snapshot) | 🟦 |
| `mirror_archive_playwright` | Playwright (PDF / screenshot / MHTML) | 🟦 |

### scrape (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_scrape_basic` | — (own parser) | 📗 reference |

### analyze (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_analyze_basic` | — (own heuristics) | 📗 reference |

### diff (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_diff_text` | — (own line diff) | 📗 reference |

### monitor (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_monitor_memory` | httpx + in-memory state | 📗 reference |

### transform (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_transform_map` | — (own mapping) | 📗 reference |

---

## Knowledge / RAG

### normalize (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_normalize_text` | — (own rules) | 📗 reference |

### enrich (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_enrich_text` | — (own keyword rules) | 📗 reference |

### chunk (2: 1 reference, 1 industry)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_chunk_text` | — (fixed-size splitter) | 📗 reference |
| `mirror_chunk_semantic` | embedding model (semantic chunking) | ✅ |

### dedup (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_dedup_hash` | — (own content hash) | 📗 reference |

### embedding ★ (2: 1 reference, 1 industry)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_embedding_hash` | — (own hash vectors) | 📗 reference |
| `mirror_embedding_ollama` | Ollama (nomic-embed-text class) | ✅ |
| `mirror_embedding_transformers` | sentence-transformers | ✅ |

### vectorstore ★ (3: 1 reference, 2 industry)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_vectorstore_memory` | — (in-memory) | 📗 reference |
| `mirror_vectorstore_pgvector` | pgvector (PostgreSQL) | ✅ |
| `mirror_vectorstore_chroma` | Chroma | ✅ |

### retrieval ★ (3: 1 reference, 2 industry)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_retrieval_memory` | — (in-memory composed) | 📗 reference |
| `mirror_retrieval_bm25` | rank_bm25 (lexical retrieval) | ✅ |
| `mirror_retrieval_hybrid` | BM25 + vector fusion | ✅ |

### search ★ (3: 1 reference, 2 industry)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_search_memory` | — (in-memory inverted index) | 📗 reference |
| `mirror_search_sqlite` | SQLite FTS5 | ✅ |
| `mirror_search_opensearch` | OpenSearch (opensearch-py) | ✅ |

### provenance (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_provenance_resource` | — (immutable resource envelope) | 📗 reference |

### compliance (1 reference)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_compliance_rules` | — (own rule engine) | 📗 reference |

---

## New capabilities (ADR-0047)

### llm (1 industry)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_llm_ollama` | Ollama (qwen2.5:0.5b class) | ✅ |

### privacy_guard (1 industry)
| Provider package | Wrapped tool | Status |
|---|---|---|
| `mirror_privacy_guard_presidio` | Microsoft Presidio (analyzer + anonymizer) | ✅ |

### ocr (none yet)
Planned: `mirror_ocr_tesseract`, `mirror_ocr_easyocr`.

---

## Infrastructure (not capabilities)

Provider families that back the runtime rather than a domain capability:

| Family | Local / reference | Production |
|---|---|---|
| database backend (ADR-0042) | `mirror_database_sqlite` | 🟦 `mirror_database_postgres` |
| worker backend | SQLite (core) | `mirror_worker_postgres` |
| execution transport | inline / SQLite | `mirror_execution_celery` |
| control plane | — | Django admin / DRF over `mirror_control` |

---

## Saturation summary

Counts include both industry-grade and reference providers. Reference providers
count toward coverage but are documented as reference.

| Capability | Total | Industry | Reference | Target | Status |
|---|---|---|---|---|---|
| fetch ★ | 3 | 3 | 0 | 3 | **saturated** |
| crawl ★ | 2 | 2 | 0 | 3 | 2/3 |
| archive | 1 | 1 | 0 | 3 | 1/3 |
| scrape | 1 | 0 | 1 | 3 | reference-only |
| analyze | 1 | 0 | 1 | 3 | reference-only |
| diff | 1 | 0 | 1 | 3 | reference-only |
| monitor | 1 | 0 | 1 | 3 | reference-only |
| transform | 1 | 0 | 1 | 3 | reference-only |
| normalize | 1 | 0 | 1 | 3 | reference-only |
| enrich | 1 | 0 | 1 | 3 | reference-only |
| chunk | 2 | 1 | 1 | 3 | 2/3 |
| dedup | 1 | 0 | 1 | 3 | reference-only |
| embedding ★ | 3 | 2 | 1 | 3 | 3/3 |
| vectorstore ★ | 3 | 2 | 1 | 3 | 3/3 |
| retrieval ★ | 3 | 2 | 1 | 3 | 3/3 |
| search ★ | 3 | 2 | 1 | 3 | 3/3 |
| provenance | 1 | 0 | 1 | 3 | reference-only |
| compliance | 1 | 0 | 1 | 3 | reference-only |
| llm | 1 | 1 | 0 | 3 | 1/3 |
| privacy_guard | 1 | 1 | 0 | 3 | 1/3 |
| ocr | 0 | 0 | 0 | 3 | 0/3 |

**Flagship capabilities (★):** fetch, crawl, embedding, vectorstore, retrieval,
search. Fetch is saturated (3/3). Crawl, embedding, vectorstore, retrieval, and
search have 2–3 providers each. The beta gate (ADR-0049) requires live
certification against legal test sites.

---

## Certification status

Providers are tested against real backends where noted. Reference providers are
deterministic and verified through contract tests.

| Provider | Backend | Certification |
|---|---|---|
| `mirror_fetch_httpx` | httpx | ✅ live legal sites |
| `mirror_fetch_playwright` | Playwright | ✅ live legal sites |
| `mirror_fetch_curl_cffi` | curl_cffi | ✅ live legal sites |
| `mirror_crawl_local` | httpx composed | ✅ live legal sites |
| `mirror_crawl_scrapy` | Scrapy | ✅ live legal sites |
| `mirror_embedding_ollama` | Ollama | ✅ live (nomic-embed-text) |
| `mirror_embedding_transformers` | sentence-transformers | ✅ live |
| `mirror_vectorstore_pgvector` | pgvector | ✅ live (Docker) |
| `mirror_vectorstore_chroma` | Chroma | ✅ live (Docker) |
| `mirror_retrieval_bm25` | rank_bm25 | ✅ unit |
| `mirror_retrieval_hybrid` | composed | ✅ live |
| `mirror_search_sqlite` | SQLite FTS5 | ✅ live |
| `mirror_search_opensearch` | OpenSearch | ✅ live (Docker) |
| `mirror_llm_ollama` | Ollama | ✅ live (qwen2.5:0.5b) |
| `mirror_privacy_guard_presidio` | Presidio | ✅ live |
| `mirror_chunk_semantic` | embedding model | ✅ live |
| `mirror_archive_warc` | warcio | ✅ unit |

Reference providers are verified through contract tests in the suite. Live
certification results are recorded in `docs/testing/LIVE_TEST_AUDIT.md`.
