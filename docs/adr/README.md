# ADR index

These architecture decision records explain why the framework looks the way it
looks. New contributors should read the relevant ADR before changing runtime
contracts.

## Accepted ADRs

- ADR-0001 package boundaries
- ADR-0002 discovery and entry points
- ADR-0003 pipeline compiler
- ADR-0004 executor and execution run
- ADR-0005 middleware contract
- ADR-0006 worker contract
- ADR-0007 resource envelope
- ADR-0008 settings authority
- ADR-0009 signals vs middleware
- ADR-0010 error semantics
- ADR-0011 checkpoint and durability
- ADR-0012 project layout
- ADR-0013 storage and blob boundaries
- ADR-0014 scheduler contract
- ADR-0015 crawl persistence
- ADR-0016 sqlite worker backend
- ADR-0017 django control plane
- ADR-0018 celery and redis workers
- ADR-0019 metadata store
- ADR-0020 django control-plane contract
- ADR-0021 control-plane metadata models
- ADR-0022 admin visibility and roles
- ADR-0023 optional Django dependency
- ADR-0024 capability package boundaries
- ADR-0025 execution semantics and runtime policies
- ADR-0026 knowledge infrastructure capability model
- ADR-0027 trusted execution pipeline
- ADR-0028 extension model and plugin lifecycle
- ADR-0029 distributed execution and Celery worker integration
- ADR-0032 distributed execution with Celery, Redis, and PostgreSQL
- ADR-0033 open-source-first provider policy
- ADR-0034 capability expansion and vertical ecosystem model
- ADR-0039 beta certification and interface projection
- ADR-0040 lease reclamation and durable-store certification
- ADR-0041 core test isolation and safe metadata decoding
- ADR-0042 independent swappable database backend
- ADR-0043 framework-neutral interface layer
- ADR-0044 Django as a thin adapter over Mirror's database
- ADR-0045 control-plane operations and security contract
- ADR-0046 provider saturation and industry-grade backend policy
- ADR-0047 knowledge/RAG ecosystem saturation
- ADR-0048 distributed recovery and worker result semantics
- ADR-0049 beta production-readiness gate
- ADR-0050 remaining review hardening

## Future drafts

Proposed ADR drafts preserved for later implementation work live in `docs/adr/future/`:

- ADR-0030 — Metadata Store Architecture
- ADR-0031 — Scheduler Backend Architecture
- ADR-0032 — Distributed Worker Architecture
- ADR-0035 — Certification, Smoke Tests, and Lab Validation Strategy
- ADR-0036 — Operational Development Stack and Deployment Baseline
- ADR-0037 — Enterprise Execution Pipeline & Runtime Semantics
- ADR-0038 — Executor Internal Decomposition
