# Mirror Roadmap

## Phase 1 — Frozen alpha core

- [x] Capability-agnostic core
- [x] Discovery and registry
- [x] Middleware contract
- [x] Worker contracts
- [x] Signals
- [x] Fresh-install smoke test
- [x] `mirror startproject`
- [x] `mirror doctor`
- [x] Alpha contract and release checklist

## Phase 2 — Modularity proof

- [x] One capability with two providers
- [x] Provider swap integration test
- [x] `mirror_fetch_playwright` package
- [x] Provider documentation
- [x] Extension-system migration audit from legacy registry language to the canonical extension API

## Phase 3 — Django control plane

- [x] `mirror startapp`
- [x] Project template polish
- [x] Better CLI help and diagnostics
- [x] Workspace bootstrap docs (`conftest.py`, `sitecustomize.py`)
- [x] End-to-end developer guide
- [x] Django control-plane package
- [x] Django admin metadata models
- [x] Django migrations and admin registrations
- [x] REST control-plane package
- [x] Pipeline blob repository and immutable versions
- [ ] Application-specific auth/role policy beyond Django model permissions
- [x] Admin views for runs, workers, crawled URLs, and archives

## Phase 4 — Beta runtime

- [x] Crawl persistence contracts
- [x] Scheduler backend
- [x] SQLite worker backend
- [x] PostgreSQL durable worker/metadata stores
- [ ] MySQL metadata store
- [x] Core blob storage boundary
- [x] Redis broker through Celery execution backend
- [x] Generic distributed workers and execution-class routing
- [x] Import/discovery/manifest certification tests
- [ ] Full live lab certification (requires live PostgreSQL/Redis/Celery environment)
- [ ] Compatibility matrix suite
- [x] Beta release checklist and certification documentation

## Phase 5 — Knowledge infrastructure (initial slice)

- [x] Normalization capability family
- [x] Enrichment capability family
- [x] Chunking capability family
- [x] Deduplication capability family
- [x] Embedding providers
- [x] Vector store providers
- [x] Retrieval capability family
- [x] Provenance contracts
- [x] Compliance and policy contracts
- [x] LLMs stay outside Mirror Core; only optional providers and consumers are allowed

## Phase 6 — Ecosystem catalog and optional plugin growth

- [ ] OCR and document parsing providers
- [ ] Stealth and proxy providers
- [ ] RPA and agentic crawl providers
- [ ] Geospatial and maps providers
- [ ] Monitoring and webhook providers
- [ ] AI/ML training and serving providers
- [ ] Domain-specific long-tail capability catalogs
- [x] Open-source-first default provider guidance

## Phase 7 — Beta structural phase

The beta release plan specified in the ADRs and PR notes under `docs/adr/` and
`docs/PRs/`. The structure is documented and accepted; implementation proceeds
in follow-up passes after review.

- [x] ADR-0042 independent swappable database backend (`PR_BETA_DB_BACKEND.md`)
- [x] ADR-0043 framework-neutral interface layer (`PR_BETA_INTERFACE_LAYER.md`)
- [x] ADR-0044 Django as a thin adapter over Mirror's database
      (`PR_BETA_DJANGO_ADAPTER.md`)
- [x] ADR-0045 control-plane operations and security contract
      (`PR_BETA_CONTROL_OPS_AND_SECURITY.md`)
- [x] ADR-0046 provider saturation and industry-grade backend policy
      (`PR_BETA_PROVIDER_SATURATION.md`); the per-capability provider list is
      `docs/ecosystem/PROVIDER_SATURATION_MATRIX.md`
- [x] ADR-0047 knowledge/RAG ecosystem saturation (`PR_BETA_RAG_ECOSYSTEM.md`)
- [x] ADR-0048 distributed recovery and worker result semantics
      (`PR_BETA_DISTRIBUTED_RECOVERY.md`)
- [x] ADR-0049 beta production-readiness gate
- [x] ADR-0050 remaining review hardening
- [x] ADR-0051 reference provider retirement and industry-grade replacement
      (`PR_BETA_REFERENCE_RETIREMENT.md`)
- [ ] Implement the `mirror_database` contract family and SQLite/Postgres
      backends
- [ ] Implement the `mirror_control` service and the CLI/admin/DRF adapters
- [ ] Rework Django onto unmanaged models, DB router, and custom user model
- [ ] Implement control-plane operations and fail-closed REST security
- [ ] Add the industry-grade providers (fetch/crawl/embedding/vectorstore/
      retrieval/search saturation)
- [ ] Add the knowledge/RAG providers and distilled-model lab tests
- [ ] Fix reaper republication and worker terminal-state mapping
- [ ] Pass the legal-test-site and Docker-lab release gate

## Proposed architecture directions

The following ideas are tracked as proposed ADRs rather than alpha commitments:

- trusted execution pipeline;
- extension model and plugin lifecycle;
- distributed execution and Celery worker integration (implemented; certification remains a deployment test);
- executor internal decomposition.

Accepted since the alpha roadmap was written: the open-source-first provider
policy (ADR-0033), the capability expansion and vertical ecosystem model
(ADR-0034, ratified by ADR-0046), the knowledge-infrastructure capability model
(ADR-0026), and the trusted execution pipeline (ADR-0027). During the beta
structural phase the remaining proposed drafts were promoted to accepted as
their decisions were already implemented: ADR-0030 (metadata store),
ADR-0031 (scheduler backend), ADR-0035 (certification/lab validation),
ADR-0036 (operational stack), ADR-0037 (enterprise execution semantics),
ADR-0038 (executor decomposition), and ADR-0052 (distributed worker
architecture). The ADR record is now complete: ADR-0001 through ADR-0052, no
open drafts.

## Phase D — Certification and interface convergence

- [x] Interface-neutral manifest projection
- [x] CLI manifest inspection
- [x] Dashboard and REST interface manifests
- [x] Immutable managed pipeline versions
- [x] Repository-wide ruff gate
- [x] Repository-wide mypy gate
- [x] Django migration smoke
- [x] Capability/provider manifest certification
- [x] Final documentation and handover review
