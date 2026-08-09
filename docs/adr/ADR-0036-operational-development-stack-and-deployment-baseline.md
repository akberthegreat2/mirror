# ADR-0036: Operational Development Stack and Deployment Baseline

- **Status:** Accepted

- **Ratified:** 2026-08-10 as part of the beta structural phase. The Docker
  Compose reference stack (PostgreSQL, Redis, Celery worker, Ollama, Chroma,
  OpenSearch) is the deployment baseline used by the ADR-0049 beta release gate.
- **Date:** 2026-08-07
- **Scope:** Local development stack, Docker Compose, Redis, Celery, PostgreSQL metadata, artifact storage, and deployment baseline
- **Related ADRs:** ADR-0030 Metadata Store Architecture, ADR-0031 Scheduler Backend Architecture, ADR-0052 Distributed Worker Architecture, ADR-0035 Certification, Smoke Tests, and Lab Validation Strategy

## Context

Mirror is approaching the point where the core runtime is no longer the only concern. Beta-grade usage needs a predictable development and deployment environment so that contributors can run the stack, verify the worker/runtime story, and test the metadata path without guessing how to wire the services together.

The recurring operational requirements are:

- a local queue and worker stack,
- a metadata database,
- a blob/artifact store,
- a Redis-backed cache or broker,
- Celery as a worker backend option,
- optional deployment manifests,
- and a reproducible developer environment.

These are not Core concerns, but they are important for a production-grade framework.

## Decision

Mirror will standardize on an optional operational stack around the core contracts.

### 1. Docker Compose reference stack

The repository should document and provide a reference local stack that can start:

- Mirror services,
- Redis,
- Celery worker(s),
- PostgreSQL metadata storage,
- a blob/artifact store or compatible local substitute.

### 2. Deployment manifests are optional

Optional deployment helpers may include:

- Helm charts,
- Kubernetes manifests,
- local dev profiles,
- CI service containers.

These are not required by Core itself, but they help prove the beta runtime story.

### 3. Celery and Redis remain backend choices

Celery and Redis are supported operational backends, not architecture owners.

The core worker and scheduler contracts remain vendor-neutral.

### 4. Metadata and artifact storage are explicit

The operational stack should separate:

- metadata storage,
- blob/content storage,
- queue/broker storage,
- cache storage.

This prevents operational state from collapsing into a single ambiguous database.

### 5. Developer workflow must stay simple

A contributor should be able to:

- install the repo,
- start the local stack,
- run smoke tests,
- execute a worker-backed flow,
- and inspect metadata/state,
without hand-building the environment.

## Non-goals

This ADR does not:

- make Docker a Core dependency,
- force Celery into the framework kernel,
- require Kubernetes for local development,
- hardcode a single storage vendor,
- redefine the worker or scheduler contracts.

## Consequences

### Positive

- Beta-level verification becomes practical.
- Contributors can reproduce the runtime locally.
- Worker and metadata work can be tested in a realistic environment.
- The deployment story becomes less fragile.

### Tradeoffs

- The repo must maintain documentation for the reference stack.
- Compose and deployment examples must stay synchronized with the contracts.
- Optional infra tooling adds maintenance overhead.

## Status Criteria

This ADR is considered implemented when:

- a documented local development stack exists,
- the stack can start Redis, Celery, and PostgreSQL-based metadata storage,
- the runtime can be exercised end-to-end against that stack,
- and the docs explain how to use the stack without implying it is mandatory for Core.
