# ADR-0052: Distributed Worker Architecture

**Status:** Accepted

**Ratified:** 2026-08-10 as part of the beta structural phase. This ADR was
originally drafted as ADR-0032 and renumbered to 0052 to avoid collision with
the accepted ADR-0032 (Distributed execution with Celery, Redis, and
PostgreSQL). The worker abstraction is implemented as the `WorkerBackend`
contract in Core, with SQLite, PostgreSQL, and Celery/Redis backends. See also
ADR-0006 and ADR-0048.

## Context

Mirror already has a canonical execution kernel in `mirror_core`:

- `Planner` produces immutable `ExecutionPlan` objects.
- `Executor` consumes plans and performs execution.
- Middleware, signals, registries, lifecycle, and discovery are owned by Core.

The remaining gap is distributed execution.

Today, Mirror can execute locally, but the framework still needs a clean worker architecture so that runs can be delegated to background workers without changing the meaning of a pipeline, a step, or a resource. This is necessary for beta-grade usage, especially for long-running crawls, durable pipelines, and future SaaS workflows.

A worker architecture must not become a second framework. It must remain a transport/backend layer under Core.

## Decision

Mirror will define a single worker abstraction in `mirror_core`, and all worker backends will implement that abstraction.

The worker layer is responsible for:

- accepting execution units from Core,
- running them to completion or failure,
- reporting lifecycle events back to Core,
- participating in lease/heartbeat semantics,
- supporting cancellation and graceful shutdown,
- returning structured results and failures,
- coordinating retry and dead-letter behavior when instructed by Core.

The worker layer is **not** responsible for:

- planning,
- provider selection,
- graph compilation,
- middleware insertion,
- discovery,
- registry ownership,
- capability logic,
- capability-to-capability orchestration,
- runtime policy design.

Those concerns remain in Core.

## Design Goals

1. **Preserve the one-owner rule**
   - Core owns execution semantics.
   - Workers own execution transport.

2. **Keep worker backends interchangeable**
   - Local execution, in-process execution, thread/process pools, Celery, and future queue systems must all satisfy the same contract.

3. **Avoid worker-specific framework drift**
   - No worker backend may define its own planner, middleware system, registry, or lifecycle model.

4. **Make distributed execution observable**
   - Worker registration, heartbeats, leases, state transitions, and terminal failures must be visible to Core and the metadata layer.

5. **Support durable execution**
   - Long-running or interrupted executions must be resumable or at least replayable at the Core level once the worker reports a terminal or retryable state.

## Worker Contract

`mirror_core` will define a worker contract that can be satisfied by multiple backends.

At minimum, a worker backend must support:

- `submit(execution_unit)`
- `cancel(run_id)` or equivalent cancellation request
- `heartbeat(worker_id)`
- `acquire_lease(execution_unit)`
- `renew_lease(lease_id)`
- `release_lease(lease_id)`
- `report_started(run_id)`
- `report_step_started(run_id, step_id)`
- `report_step_finished(run_id, step_id)`
- `report_failed(run_id, error)`
- `report_completed(run_id, result)`

The exact naming can evolve, but the semantics must remain stable.

## Required Cleanup Before Beta

The following items are considered beta-critical. If any are missing, the distributed worker architecture is incomplete:

### 1. Queue abstraction

Mirror must not hardcode a specific transport in Core.

The worker contract must be backend-agnostic enough to support:

- in-memory queues,
- database-backed queues,
- Redis-backed queues,
- message brokers,
- future cloud queue systems.

### 2. Local worker backend

Mirror should ship at least one non-network worker backend for verification:

- inline worker, or
- thread pool worker, or
- process pool worker

This backend is necessary to prove the contract before adding a distributed implementation.

### 3. Lease and heartbeat semantics

Distributed execution must include:

- worker identity,
- lease acquisition,
- lease renewal,
- lease expiry,
- worker heartbeat,
- work requeue after lease loss.

Without this, dead worker recovery is undefined.

### 4. Cancellation and shutdown semantics

Workers must support:

- cooperative cancellation,
- graceful shutdown,
- terminal cancellation reporting,
- cancellation visibility in execution context.

### 5. Terminal failure handling

A failed worker execution must end in a structured terminal state, not an untyped crash.

The core runtime must be able to classify:

- retryable failure,
- terminal failure,
- cancelled run,
- dead-lettered run.

### 6. Dead Letter Queue (DLQ)

If retry limits are exceeded or a run becomes non-recoverable, the system must support a DLQ path or an equivalent terminal quarantine state.

The DLQ must preserve:

- run identity,
- step identity,
- original payload,
- failure classification,
- retry history,
- provenance.

### 7. Metadata store integration

Worker execution state must be recorded in the metadata store.

At minimum, the metadata layer should persist:

- run state,
- step state,
- worker identity,
- queue/lease metadata,
- retry count,
- failure classification,
- timestamps,
- provenance links.

### 8. Architecture tests

CI must fail if worker code introduces framework drift.

Tests should reject:

- worker packages defining their own planner,
- worker packages defining their own middleware system,
- worker packages defining their own registry or discovery model,
- provider packages importing worker internals,
- capability packages importing worker backends directly,
- Core depending on a specific worker vendor.

## Local vs Distributed Execution

Mirror must support both modes through the same runtime model.

### Local execution

Useful for:

- development,
- tests,
- single-process usage,
- quick validation.

### Distributed execution

Useful for:

- long-running pipelines,
- crawl workloads,
- SaaS workflows,
- queue-backed background jobs,
- retries and fault tolerance,
- operational separation between plan generation and run execution.

The difference is the backend, not the meaning of execution.

## Celery as a provider, not a dependency

Celery may be implemented as one worker backend, but Celery is not the worker architecture.

The architecture is:

- Core defines worker semantics,
- worker backends implement them,
- Celery is one implementation.

This avoids locking the framework to any single task queue or background job system.

## Failure Semantics

Worker failures must be classified consistently.

At minimum:

- **retryable failure** — Core may reschedule according to policy.
- **terminal failure** — execution stops and fails definitively.
- **cancelled** — execution ended due to an explicit cancellation request.
- **dead-lettered** — execution exceeded retry/repair limits and is quarantined.

The worker backend must not invent its own failure taxonomy.

## Requeue and Retry Semantics

Retry ownership remains with Core.

Worker backends may report failure or lease loss, but retry policy is decided by Core and execution policies.

Workers do not choose when to retry a run. They only report facts that Core can use to decide.

## Observability

Worker execution should emit structured events suitable for:

- logs,
- metrics,
- tracing,
- audit trails,
- run history,
- operational dashboards.

Minimum observable entities:

- worker registered,
- worker heartbeat,
- lease acquired,
- lease renewed,
- lease lost,
- execution submitted,
- execution started,
- step started,
- step finished,
- execution completed,
- execution failed,
- execution cancelled,
- execution dead-lettered.

## Non-Goals

This ADR does **not** define:

- scheduler policy,
- cron semantics,
- Airflow semantics,
- metadata schema details,
- dashboard implementation,
- REST/GraphQL interfaces,
- provider-specific task logic,
- capability logic.

Those belong to other ADRs or implementation docs.

## Consequences

### Positive
- Mirror gains durable and distributed execution without fragmenting architecture.
- Local and distributed execution remain behaviorally consistent.
- Beta becomes realistic for long-running workflows.

### Negative
- The worker abstraction must be implemented carefully to avoid leaking backend assumptions into Core.
- DLQ and lease semantics increase operational complexity.
- Metadata persistence must be sufficiently robust to support retry, cancellation, and recovery.

## Implementation Notes

This ADR is considered satisfied only when:

- worker backends are replaceable,
- Core remains the sole owner of execution semantics,
- no worker backend introduces a hidden runtime or planner,
- local execution is proven before distributed execution,
- Celery or any other backend remains one implementation of the worker contract,
- DLQ and terminal failure handling are available for unrecoverable runs,
- metadata records enough state to reconstruct or inspect execution outcomes.

## Related ADRs

- ADR-0025: Execution Semantics and Runtime Policies
- ADR-0027: Trusted Execution Pipeline
- ADR-0028: Extension & Ecosystem Model
- ADR-0030: Metadata Store Architecture
- ADR-0031: Scheduler Backend Architecture
- ADR-0026: Knowledge Infrastructure Capability Model
