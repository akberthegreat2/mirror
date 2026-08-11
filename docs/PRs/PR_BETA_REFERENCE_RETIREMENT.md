# PR: Beta — reference provider retirement and industry-grade replacement

## Problem

Fifteen capability providers were deterministic, in-memory, or hash-based
own-implementations shipped as providers of record: hash embedding, memory
vector store, memory search, memory retrieval, memory monitor, basic scrape,
basic analyze, text diff, text normalize, text enrich, text chunk, hash dedup,
resource provenance, rules compliance, and map transform. They read as capability
coverage without providing the real behavior a user expects — a hash-space
vector is not an embedding model, and an in-memory dict is not a vector database.
The user requirement is that Mirror never invents libraries from scratch and that
every production provider wraps an industry-grade tool; shipping reference
stand-ins violates that promise.

## Decision

Retire the fifteen reference providers from the first-party catalog and replace
each with industry-grade providers that wrap existing tools (ADR-0051). The
decision:

- Reference provider packages are removed as shipped provider-of-record
  packages. The capability/provider registry stops presenting them.
- Deterministic doubles survive only as test-only helpers inside the test suite
  or `mirror_testing` — never as registry providers.
- Local composed providers are retained when they wrap a real tool:
  `mirror_crawl_local` (composed httpx `fetch`, real HTTP) stays.
- Each retired provider is replaced per the migration table in ADR-0051 and the
  provider-saturation matrix.
- Every capability is re-certified against its real backend after replacement
  (ADR-0049). "Certified" requires a passing real-backend test.

## What changed

- Removed the fifteen reference provider packages from the shipped catalog.
- Added the replacement industry-grade provider packages (see
  `PR_BETA_PROVIDER_SATURATION.md` and `PR_BETA_RAG_ECOSYSTEM.md` for the
  package catalog).
- Migrated tests that used reference providers to real local backends (local
  HTTP server, real SQLite/PostgreSQL, Docker containers) or to test-only
  doubles in `mirror_testing`.
- Updated the capability/provider registry and the saturation matrix to reflect
  the retired and replacement providers.

## Validation

- Architecture tests still enforce Core → capability → provider ownership for
  every package.
- No retired reference package is discoverable in the capability/provider
  registry.
- Every capability has its industry-grade providers and at least one passing
  real-backend test before it is listed as certified.

## Deferred

- Retiring the packages is coordinated with the flagship saturation work
  (`PR_BETA_PROVIDER_SATURATION.md`) and the knowledge/RAG ecosystem work
  (`PR_BETA_RAG_ECOSYSTEM.md`), which ship the replacement providers.
