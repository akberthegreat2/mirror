# PR: Beta — knowledge/RAG ecosystem saturation

## Problem

The knowledge/RAG slice lacked real production providers: there was no LLM
capability at all, no local embedding provider, and the vector/retrieval side had
no industry-grade backends. Without an Ollama provider the RAG pipeline could not
be exercised end-to-end. The user requirement is to saturate the ecosystem,
especially for RAG, using industry-grade tools wrapped by Mirror — and to test
the pipeline with distilled small models so the lab stays cheap.

## Decision

Introduce the knowledge/RAG ecosystem documented in ADR-0047:

- `mirror_embedding_ollama` — local embeddings via Ollama
  (`nomic-embed-text`-class models).
- `mirror_llm` — new capability, with `mirror_llm_ollama` as the provider.
- `mirror_vectorstore_pgvector` and `mirror_vectorstore_chroma` — two
  industry-grade vector backends.
- `mirror_retrieval_hybrid` — hybrid lexical + vector retrieval.
- `mirror_search_opensearch` — OpenSearch-backed search.
- `mirror_privacy_guard` — new capability, with `mirror_privacy_guard_presidio`
  (Microsoft Presidio) as the PII provider.
- `mirror_chunk_semantic` — semantic chunking provider.
- `mirror_ocr` — new capability, with `mirror_ocr_tesseract` as the provider.
- `mirror_crawl_playwright` — browser crawl provider.

The canonical pipeline is:

```text
fetch -> normalize -> chunk -> embed -> upsert -> retrieve -> llm answer
```

with privacy guard applied where required. Every provider wraps an existing tool
(Ollama, pgvector, Chroma, OpenSearch, Presidio, Tesseract); nothing is written
from scratch.

## What changed

- Added the capability and provider packages listed above.
- Wired the RAG pipeline end-to-end through Core.
- Added lab tests against distilled small models (`nomic-embed-text`,
  `qwen2.5:0.5b`) so certification is reproducible without large infrastructure.

## Validation

- End-to-end pipeline test: fetch real content, normalize, chunk, embed, upsert
  into a real vector backend, retrieve, and produce an LLM answer.
- Real-backend tests for pgvector, Chroma, OpenSearch, Ollama, Presidio, and
  Tesseract.
- Distilled-model lab tests are labeled accurately (CLAUDE.md §11/§13); they are
  real-backend tests, not mocks.

## Deferred

- The beta release gate (legal test sites, Docker lab, fresh-venv install) is
  covered in `PR_BETA_RELEASE_GATE.md`.
