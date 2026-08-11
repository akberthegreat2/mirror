# Capability and provider packages

Mirror is split into separate packages. Each package owns one small role:
a **capability** package owns a domain contract, a **provider** package owns
one concrete implementation of a contract. The full repository catalog is
below.

## How to think about them

A capability package should answer one question only:

> What does this domain mean?

A provider package should answer one question only:

> How do I implement that domain?

`mirror_core` answers the framework question:

> How do all of these pieces run together safely?

## The kernel

| Package | Role |
| --- | --- |
| `mirror_core` | Framework kernel: planner, executor, registry, discovery, lifecycle, signals, middleware, storage, scheduler, workers |

## Infrastructure packages

| Package | Role |
| --- | --- |
| `mirror_worker_postgres` | Durable worker/storage backend on PostgreSQL |
| `mirror_execution_celery` | Celery execution mechanism (Redis broker) |
| `mirror_control` | Framework-neutral `ControlService` application layer (ADR-0043) |
| `mirror_control_django` | Django control-plane adapter (unmanaged models over Mirror's schema) |
| `mirror_control_api` | REST control-plane adapter sharing the same `ControlService` |
| `mirror_cli` | Command-line interface |
| `mirror_testing` | Testing helpers and the legal-site certification harness |

## Capability packages (domain contracts)

| Package | Role |
| --- | --- |
| `mirror_fetch` | Fetch contract and request/result models |
| `mirror_crawl` | Crawl contract and crawl-specific orchestration |
| `mirror_archive` | Archive contract and archive-specific orchestration |
| `mirror_scrape` | Scrape contract and extraction models |
| `mirror_search` | Search contract and search models |
| `mirror_analyze` | Analyze contract and analysis models |
| `mirror_diff` | Diff contract and comparison models |
| `mirror_monitor` | Monitor contract and monitoring models |
| `mirror_normalize` | Normalization contract and text canonicalization models |
| `mirror_enrich` | Enrichment contract and derived metadata models |
| `mirror_chunk` | Chunking contract and chunk models |
| `mirror_dedup` | Deduplication contract and duplicate-resolution models |
| `mirror_embedding` | Embedding contract and vector models |
| `mirror_llm` | LLM generation contract and completion models |
| `mirror_vectorstore` | Vector store contract and query models |
| `mirror_retrieval` | Retrieval contract and ranked-match models |
| `mirror_provenance` | Provenance contract and resource-envelope models |
| `mirror_compliance` | Compliance contract and policy-check models |
| `mirror_privacy_guard` | PII detection/redaction contract |
| `mirror_transform` | Transform contract and field-mapping models |
| `mirror_database` | Framework-neutral database backend contract family (ADR-0042) |

## Provider packages (concrete implementations)

### Fetch

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_fetch_httpx` | HTTPX | Industry-backed synchronous/asynchronous HTTP fetch |
| `mirror_fetch_curl_cffi` | curl_cffi / libcurl | Industry-backed fetch with TLS/browser fingerprint support |
| `mirror_fetch_playwright` | Playwright | Industry-backed headless-browser fetch |

### Crawl

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_crawl_local` | HTTPX (composed fetch) | Local reference crawl provider |
| `mirror_crawl_scrapy` | Scrapy | Industry-backed crawl engine |
| `mirror_crawl_playwright` | Playwright | Industry-backed browser crawl |

### Archive

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_archive_warc` | warcio | WARC archive provider |

### Scrape

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_scrape_basic` | — | Basic HTML scrape provider |

### Search / Analyze / Diff / Monitor / Normalize / Enrich / Dedup / Transform

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_search_memory` | — | In-memory search reference provider |
| `mirror_search_sqlite` | SQLite FTS5 | Industry-backed full-text search provider |
| `mirror_search_opensearch` | OpenSearch | Industry-backed search provider |
| `mirror_analyze_basic` | — | Basic analyze reference provider |
| `mirror_diff_text` | — | Text diff reference provider |
| `mirror_monitor_memory` | — | HTTP monitor reference provider |
| `mirror_normalize_text` | — | Text normalization reference provider |
| `mirror_enrich_text` | — | Text enrichment reference provider |
| `mirror_dedup_hash` | — | Hash deduplication reference provider |
| `mirror_transform_map` | — | Field-mapping transform reference provider |

### Chunk / Embedding / LLM

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_chunk_text` | — | Fixed-size token chunk reference provider |
| `mirror_chunk_semantic` | sentence-transformers | Embedding-aware semantic chunk provider |
| `mirror_embedding_hash` | — | Deterministic hash embedding reference provider |
| `mirror_embedding_ollama` | Ollama | Industry-backed embedding provider |
| `mirror_embedding_transformers` | sentence-transformers | Industry-backed embedding provider |
| `mirror_llm_ollama` | Ollama | Industry-backed LLM generation provider |

### Vector store / Retrieval

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_vectorstore_memory` | — | In-memory vector store reference provider |
| `mirror_vectorstore_chroma` | Chroma | Industry-backed vector store provider |
| `mirror_vectorstore_pgvector` | PostgreSQL + pgvector | Industry-backed vector store provider |
| `mirror_retrieval_memory` | — | In-memory retrieval reference provider |
| `mirror_retrieval_bm25` | rank-bm25 | Industry-backed lexical retrieval provider |
| `mirror_retrieval_hybrid` | BM25 + embeddings | Hybrid lexical + semantic retrieval provider |

### Compliance / Provenance / Privacy

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_compliance_rules` | — | Rules-based compliance reference provider |
| `mirror_provenance_resource` | — | Resource provenance reference provider |
| `mirror_privacy_guard_presidio` | Microsoft Presidio | Industry-backed PII detection/redaction provider |

### Database

| Package | Backend | Role |
| --- | --- | --- |
| `mirror_database_sqlite` | SQLite | SQLite backend for the Mirror database contract |

## Where to find more

- `docs/capabilities/` — capability-by-capability index linking every package README.
- `docs/providers/` — provider index linking every provider package README.
- `docs/adr/ADR-0024` (capability package boundaries), `docs/adr/ADR-0026`
  (knowledge-infrastructure capability model), `docs/adr/ADR-0033`
  (open-source-first provider policy), `docs/adr/ADR-0034` (capability
  expansion), `docs/adr/ADR-0042` (independent database backend).
