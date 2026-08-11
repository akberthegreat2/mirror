# ADR-0030: Metadata Store Architecture

**Status:** Accepted

**Ratified:** 2026-08-10 as part of the beta structural phase. The in-kernel
metadata store is implemented in `mirror_core.metadata` and re-exported from
`mirror_core.storage`. ADR-0042 extends this decision with the independent,
swappable `mirror_database` backend family for the operational schema.

## Context

Mirror already treats execution, planning, middleware, discovery, and signals as core-owned concerns. Storage has been discussed as an abstract infrastructure layer, but the repository still needs a clear decision for the metadata store specifically.

The metadata store is not the blob/archive store. It is the system of record for operational and relational data such as:

- pipeline definitions and versions
- execution runs
- step runs
- scheduler state
- worker leases
- retries and terminal outcomes
- resource lineage
- provenance references
- capability/provider resolution metadata
- audit history and replay pointers

Without a dedicated metadata model, this information tends to drift into ad hoc tables, scattered JSON files, or capability-local state.

## Decision

Mirror will define a dedicated Metadata Store abstraction in `mirror_core`.

This abstraction is responsible for persistent operational metadata and must remain independent from blob/content storage.

### Ownership

- `mirror_core` owns the metadata store contract.
- Capability packages do not define their own metadata persistence semantics.
- Providers may implement metadata storage backends, but only through the core contract.
- Applications and services consume metadata through the core abstraction, never through provider-specific APIs.

### Scope

The metadata store covers:

- pipeline/version records
- execution run records
- step execution records
- retry records
- terminal state and outcomes
- scheduler bookkeeping
- worker lease/heartbeat state
- lineage and provenance references
- policy resolution snapshots
- replay and resume pointers
- audit/event history

### Non-scope

The metadata store does **not** own:

- raw payload/blob persistence
- content archive format decisions
- capability domain models
- provider algorithms
- execution planning
- middleware execution

Those remain owned elsewhere.

## Consequences

### Positive

- Execution history becomes queryable and replayable.
- The scheduler and worker subsystems can share one durable state model.
- Metadata storage can be swapped independently from blob storage.
- Observability and auditability become first-class.

### Tradeoffs

- The metadata schema must be carefully versioned.
- The abstraction must remain narrow enough to avoid becoming a second database framework.
- Replay and audit semantics must be stable before distributed execution is finalized.

## Architectural Rules

1. Metadata persistence belongs to `mirror_core`, not to capabilities.
2. Blob/content storage and metadata storage are separate concerns.
3. Providers may implement metadata backends, but they must conform to the core contract.
4. Capability packages must not store operational state directly.
5. Metadata store APIs must not leak provider-specific tables, clients, or ORM details into capability code.

## Relationship to other ADRs

- Supports runtime semantics and execution history.
- Supports distributed execution and worker leasing.
- Supports scheduler bookkeeping.
- Supports replay, audit, and lineage.
- Complements the storage abstraction without replacing it.

## Status Summary

This ADR is Proposed until the codebase contains a concrete metadata store contract in `mirror_core` and at least one implementation validated by integration tests.
