# Mirror Beta Contract

This document defines the next release stage after the frozen alpha. Beta is the
first stage where Mirror is expected to support real SaaS workloads, not just
prove its architecture.

## Beta means

Mirror beta must provide:

- crawl persistence for discovered URLs and fetched results;
- worker backends suitable for local development and production queues;
- a framework-neutral control layer, with a Django admin interface, for
  metadata, pipeline management, and admin operations;
- docs, ADRs, tests, and PR notes for every user-facing promise.

Scheduler support has already graduated into the stable core package (`mirror_core.scheduler`). Metadata storage now lives in `mirror_core.metadata` and is re-exported from `mirror_core.storage` for compatibility; blob storage remains in `mirror_core.storage`.

## Beta architecture (accepted via ADR-0042 … ADR-0050)

- **Independent swappable database backend (ADR-0042).** Operational state is
  owned by the framework-neutral `mirror_database` contract family with swappable
  backends — SQLite for local development, PostgreSQL for production. The schema
  is owned by Mirror, not by any framework.
- **Framework-neutral interface layer (ADR-0043).** All interfaces (CLI, Django
  admin, DRF, and future FastAPI dashboards) are thin adapters over one
  `ControlService`, so every interface performs identically and none bypasses
  Core execution.
- **Django as a thin adapter (ADR-0044).** Django admin reads over unmanaged
  models via a DB router; writes delegate to `ControlService`; a custom user
  model lives on a separate auth database. Django never owns or migrates the
  operational schema.
- **Control-plane operations and security (ADR-0045).** Every advertised
  operation is implemented once in `ControlService`; the REST surface defaults
  to fail-closed authentication and permissions.
- **Provider saturation (ADR-0033, ADR-0034, ADR-0046).** Mirror wraps
  industry-grade tools; it does not invent libraries from scratch. Each flagship
  capability has at least three swappable providers, and production providers
  MUST wrap an existing industry-grade tool.
- **Knowledge/RAG ecosystem (ADR-0047).** The RAG pipeline runs end-to-end
  against real backends (Ollama embeddings + LLM, pgvector/Chroma, hybrid
  retrieval, OpenSearch, Presidio privacy guard, Tesseract OCR).

## Beta runtime guarantees

- Crawlers MUST save discovered URLs when configured to do so, through the real
  runtime composition path (ADR-0050).
- Workers MUST be able to resume work from persisted state.
- Scheduler jobs MUST be repeatable and observable.
- Distributed recovery MUST establish the complete path: expired lease → durable
  job reclaimable → job republished → worker claims it → execution resumes
  (ADR-0048, CLAUDE.md §8).
- Worker terminal state MUST reflect the execution outcome — SUCCEEDED / FAILED /
  CANCELLED, never inferred from the absence of an exception (ADR-0048).
- Metadata and blob storage MUST use the stable core backends documented in
  `mirror_core.metadata` and `mirror_core.storage`.
- Checkpoint payloads MUST round-trip through the safe metadata encoding; no
  arbitrary module path may be imported from persisted data (ADR-0050,
  CLAUDE.md §18).
- Redis MAY be used for cache, queue, and lease coordination.
- Django admin MUST be able to read and manage stored metadata.
- A release MAY be marked beta only after the legal-test-site and Docker-lab
  gates in ADR-0049 pass.

## Deferred to later releases

- advanced SaaS tenancy and billing
- higher-level search products
- integration with multiple external task systems beyond the supported beta
  backends
- live-lab certification of every provider in every deployment environment
