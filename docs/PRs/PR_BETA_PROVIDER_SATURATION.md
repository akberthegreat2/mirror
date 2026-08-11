# PR: Beta — provider saturation and industry-grade backend policy

## Problem

Not every flagship capability had enough swappable providers, and several
production paths were reference-only implementations rather than wrappers around
industry-grade tools. The user's requirement is explicit: Mirror never invents
libraries from scratch; it wraps pre-existing industry-grade tools. Some
capabilities had only one or two providers, which is insufficient to prove that
the provider model is genuinely swappable.

## Decision

Ratify the open-source-first policy and capability-ecosystem model (ADR-0033,
ADR-0034) and require provider saturation (ADR-0046):

- Every flagship capability (fetch, crawl, embedding, vectorstore, retrieval,
  search) must have at least three swappable providers.
- Production providers MUST wrap an existing industry-grade tool — no
  from-scratch production backends. Reference/deterministic providers are still
  allowed but must be labeled as reference.
- Core remains capability-agnostic; providers stay in their own packages and
  never bypass Core execution.

Target provider set per flagship capability:

- fetch: httpx, playwright, curl-impersonate (`curl_cffi`)
- crawl: local, scrapy, playwright
- embedding: sentence-transformers, ollama, reference hash
- vectorstore: pgvector, chroma, reference in-memory
- retrieval: hybrid, vector, lexical reference
- search: opensearch, postgres FTS reference, elasticsearch

## What changed

- Added the missing production providers listed above.
- Updated the capability/provider catalog in `docs/` to distinguish reference
  providers from industry-grade providers.
- Cross-referenced ADR-0033 and ADR-0034 as ratified.

## Validation

- Architecture tests enforce the provider rules (no provider imports another
  provider; no provider creates a second runtime).
- Real-backend tests are added for each industry-grade provider; reference
  providers are only exercised against their own contract tests.
- Provider-saturation tests assert each flagship capability resolves to at least
  three distinct providers.

## Deferred

- The knowledge/RAG provider families and the distilled-model lab tests are
  covered in `PR_BETA_RAG_ECOSYSTEM.md`.
