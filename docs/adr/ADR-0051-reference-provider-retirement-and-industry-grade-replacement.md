# ADR-0051: Reference Provider Retirement and Industry-Grade Replacement

## Status

Accepted

## Context

The catalog still ships fifteen deterministic, in-memory, or hash-based
"reference" providers:

```text
analyze/basic, chunk/text, compliance/rules, dedup/hash, diff/text,
embedding/hash, enrich/text, monitor/memory, normalize/text,
provenance/resource, retrieval/memory, scrape/basic, search/memory,
transform/map, vectorstore/memory
```

These are own-implementation stand-ins for production systems. A hash-space
vector is not an embedding model. An in-memory dictionary is not a vector
database. An in-memory inverted index is not search. CLAUDE.md §16 and
ADR-0046 §2 have so far permitted them when labeled "reference", but they are
not production software, and shipping them in the first-party catalog as
providers of record is misleading — they read as capability coverage while
providing none of the real behavior a user of that capability expects.

The user requirement is explicit and changes the policy: reference providers
must be removed and replaced with industry-grade providers that wrap existing,
established tools. Mirror's promise is that it never invents libraries from
scratch and that every production provider implements an industry-grade tool.

The one genuine "local" provider is different: `mirror_crawl_local` composes the
httpx `fetch` provider and performs real HTTP crawling (fetch, HTML parse, link
discovery, depth, same-host rules). It is a real, composed provider, not a
reference stand-in, and is retained.

## Decision

### 1. Reference providers are retired from the first-party catalog

The fifteen reference provider packages above are retired as shipped providers.
Each capability they served is served instead by industry-grade providers that
wrap an existing tool (see the migration table below and
`docs/ecosystem/PROVIDER_SATURATION_MATRIX.md`).

### 2. Local composed providers may remain

A provider that composes a real industry-grade tool through the public contract
is real, not reference. `mirror_crawl_local` (composed httpx `fetch`) is
retained. Other local/in-process providers are evaluated on the same rule: they
must wrap a real tool or be replaced.

### 3. No own-implementation production providers

A provider is production-grade only if it implements an existing, industry-grade
tool or service through its published interface (ADR-0046 §2). This is now
unconditional: no deterministic stand-in may be the provider of record for a
capability.

### 4. Test doubles live in the test suite, not the registry

Deterministic doubles are allowed only inside the test suite — fixtures,
`mirror_testing` helpers, or local in-process servers. They are never shipped as
capability/provider packages and never appear in the capability/provider
registry.

### 5. Re-certification is required

After replacement, every capability is re-certified against its real backend:
local servers, Docker containers, or the legal test sites in
`docs/testing/LEGAL_TEST_SITES.md` (ADR-0049). A capability is "certified" only
when an industry-grade provider passes its real-backend test. Providers that
are not yet certified are documented as "implemented but not externally
certified" (CLAUDE.md §13).

## Migration table

| Retired reference provider | Replaced by industry-grade providers (wrapped tool) |
|---|---|
| `mirror_analyze_basic` | `mirror_analyze_spacy` (spaCy), `mirror_analyze_readability` (readability-lxml), `mirror_analyze_trafilatura` (trafilatura) |
| `mirror_chunk_text` | `mirror_chunk_semantic` (embedding model), `mirror_chunk_token` (tiktoken), `mirror_chunk_langchain` (langchain-text-splitters) |
| `mirror_compliance_rules` | `mirror_compliance_presidio` (Presidio), `mirror_compliance_robots` (reppy), `mirror_compliance_license` (license-expression) |
| `mirror_dedup_hash` | `mirror_dedup_simhash` (simhash), `mirror_dedup_minhash` (datasketch), `mirror_dedup_embedding` (embedding model) |
| `mirror_diff_text` | `mirror_diff_deepdiff` (deepdiff), `mirror_diff_matchpatch` (diff-match-patch), `mirror_diff_jsondiff` (jsondiff) |
| `mirror_embedding_hash` | `mirror_embedding_ollama` (Ollama), `mirror_embedding_sentence_transformers` (sentence-transformers), `mirror_embedding_openai` (OpenAI-compatible API) |
| `mirror_enrich_text` | `mirror_enrich_spacy` (spaCy), `mirror_enrich_keybert` (keybert), `mirror_enrich_llm` (Ollama / OpenAI-compatible) |
| `mirror_monitor_memory` | `mirror_monitor_httpx` (httpx), `mirror_monitor_playwright` (Playwright), `mirror_monitor_otel` (OpenTelemetry) |
| `mirror_normalize_text` | `mirror_normalize_ftfy` (ftfy), `mirror_normalize_html2text` (html2text), `mirror_normalize_html_text` (html-text) |
| `mirror_provenance_resource` | `mirror_provenance_w3c` (W3C PROV), `mirror_provenance_warc` (warcio), `mirror_provenance_openlineage` (OpenLineage) |
| `mirror_retrieval_memory` | `mirror_retrieval_bm25` (rank_bm25), `mirror_retrieval_hybrid` (BM25 + vector), `mirror_retrieval_rerank` (CrossEncoder) |
| `mirror_scrape_basic` | `mirror_scrape_bs4` (beautifulsoup4), `mirror_scrape_parsel` (parsel), `mirror_scrape_selectolax` (selectolax) |
| `mirror_search_memory` | `mirror_search_opensearch` (OpenSearch), `mirror_search_elasticsearch` (Elasticsearch), `mirror_search_postgres_fts` (PostgreSQL FTS) |
| `mirror_transform_map` | `mirror_transform_jmespath` (jmespath), `mirror_transform_jsonpath` (jsonpath-ng), `mirror_transform_jinja` (Jinja2) |
| `mirror_vectorstore_memory` | `mirror_vectorstore_pgvector` (pgvector), `mirror_vectorstore_chroma` (Chroma), `mirror_vectorstore_qdrant` (Qdrant) |

## Consequences

- The capability/provider registry stops shipping deterministic stand-ins; every
  capability's providers wrap a real, industry-grade tool.
- The offline suite's deterministic tests migrate to industry-grade providers
  with real local backends (local HTTP server, real SQLite/PostgreSQL, Docker
  containers) or to test-only doubles inside `mirror_testing`.
- ADR-0046 §2/§3 and CLAUDE.md §16 are amended by this ADR: reference providers
  are no longer shipped first-party; the three-provider saturation rule is met
  by industry-grade providers (reference providers no longer count toward it).
- The provider-saturation matrix
  (`docs/ecosystem/PROVIDER_SATURATION_MATRIX.md`) becomes the retirement and
  replacement checklist.
- Certification honesty improves: "implemented" now means a real tool is wired,
  and "certified" means it was verified against the real backend.

## Relationship to other ADRs

Amends ADR-0046 (reference-provider allowance, saturation counting). Ratifies
the migration table in the provider-saturation matrix. Execution of the
replacement is gated by ADR-0049 (beta release gate) and detailed in
`PR_BETA_REFERENCE_RETIREMENT.md`.
