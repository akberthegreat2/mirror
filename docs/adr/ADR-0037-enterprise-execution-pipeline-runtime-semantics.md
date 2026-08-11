# ADR-0037: Enterprise Execution Pipeline & Runtime Semantics

**Status:** Accepted

**Ratified:** 2026-08-10 as part of the beta structural phase. The runtime
semantics in this ADR are implemented in `mirror_core` (compiled-plan execution,
DAG pipelines, middleware boundary, policy invocation). See also ADR-0025.
Date: 2026-08-07
Scope: Pipeline compilation, execution semantics, middleware behavior, retries, cancellation, provenance, and runtime policy contracts
Related ADRs: ADR-0001 Entry Points, ADR-0002 DAG Pipeline, ADR-0003 Resource Envelope, ADR-0004 Capability / Provider Model

## Context

Mirror has already converged on a single framework kernel in `mirror_core`. Capabilities own domain logic. Providers implement contracts. `mirror_core` owns orchestration, execution, lifecycle, discovery, registries, middleware contracts, signals, and scheduling.

This ADR defines the runtime semantics that sit on top of that architecture. The goal is not to introduce a new framework layer. The goal is to make execution behavior deterministic, auditable, and enterprise-grade without moving ownership away from `mirror_core`.

## Decision

Mirror will treat pipeline execution as a compiled plan executed by a core-owned runtime.

### 1. Planner and executor are separate responsibilities

- The planner validates and compiles a pipeline into an immutable `ExecutionPlan`.
- The executor only executes an `ExecutionPlan`.
- The executor must not parse pipeline definitions, resolve providers, build dependency graphs, or perform planning-time validation.

### 2. Pipelines are DAGs, not implicit chains

- A pipeline is a directed acyclic graph of steps.
- The planner must detect cycles.
- The planner must validate typed step bindings and resource compatibility.
- The planner may compute parallel groups for concurrent execution.
- The executor consumes the resulting execution order and dependency structure.

### 3. Middleware is a first-class execution boundary

Middleware may:

- continue execution,
- modify input,
- modify output,
- terminate execution early,
- raise,
- retry.

Middleware is allowed to short-circuit execution when the middleware contract permits it. Middleware does not own the framework runtime. It participates in execution through core-owned contracts.

### 4. Execution policies are distinct from middleware implementations

Execution policy is the architectural contract. Middleware is one implementation strategy.

Policies include:

- RetryPolicy
- TimeoutPolicy
- CancellationPolicy
- FallbackPolicy
- CheckpointPolicy (future)
- CompensationPolicy (future)

The system must not hardcode these policies into individual capabilities. They belong to the execution model and are owned by core.

### 5. ExecutionContext is the standard runtime boundary

Every step and middleware invocation should receive the same execution context shape.

A context may include:

- run_id
- step_id
- inputs
- outputs
- settings
- logger
- metrics
- signals
- storage
- clock
- cancellation token
- trace metadata
- execution metadata

The context should be stable enough that new runtime features can be added without changing every capability signature.

### 6. ResourceEnvelope is the canonical runtime payload

Resources exchanged between steps should be represented by `ResourceEnvelope` or by strongly typed capability models embedded in it.

Requirements:

- resources must preserve provenance,
- resource lineage must be traceable,
- resource identity should remain stable across execution,
- resource mutation should be avoided where practical,
- derived resources should be represented as new values rather than in-place mutation.

### 7. Signals observe; they do not control

Signals are emitted for lifecycle and execution visibility. They must not become a second middleware system and must not control execution order or retry behavior.

Signals should be available for:

- pipeline lifecycle,
- step lifecycle,
- provider lifecycle,
- storage lifecycle,
- worker lifecycle,
- execution lifecycle.

### 8. Cancellation must propagate through the runtime

Cancellation is a first-class runtime concern.

Requirements:

- a run may be cancelled at the framework level,
- cancellation must be visible to middleware,
- cancellation must be visible to providers,
- cancellation must be respected by the executor and workers,
- cancellation must not be implemented as a timeout alias.

### 9. Dead Letter Queue is part of distributed runtime semantics

A dead letter queue (DLQ) is required for terminal failures in distributed execution.

The DLQ must preserve:

- the failed execution reference,
- the reason for failure,
- the original inputs,
- the relevant policy state,
- provenance metadata,
- retry count,
- terminal status.

The DLQ is a runtime concern, not a capability concern.

### 10. Determinism is the default expectation

Given the same:

- pipeline definition,
- input resources,
- provider selection,
- settings,
- middleware configuration,

Mirror should produce the same execution plan and equivalent runtime behavior unless a policy explicitly introduces nondeterminism.

## Non-goals

This ADR does not define:

- a specific worker backend,
- a specific queue backend,
- a specific scheduler backend,
- a specific storage implementation,
- a specific DLQ implementation,
- a specific middleware implementation,
- capability-specific business logic,
- AI / RAG / embedding capabilities,
- interface-layer features such as CLI, REST, or dashboards.

Those concerns are handled by other ADRs, provider packages, or interface packages.

## Consequences

### Positive

- Execution behavior becomes predictable.
- Planner and executor responsibilities remain cleanly separated.
- Middleware can evolve without reintroducing architecture drift.
- Workers and distributed backends can be swapped without rewriting capabilities.
- Failure handling can be modeled consistently.
- Debugging, tracing, and provenance become practical.

### Negative

- The runtime contract becomes stricter.
- Capability authors must conform to stable invocation semantics.
- New runtime features must be added through the core execution model instead of ad hoc per-capability logic.

## Open Questions

- Should checkpoint/resume be implemented before or after distributed worker support?
- Should the DLQ live in metadata storage or as a dedicated queue abstraction?
- Should fallback resolve to a provider, a step, or an alternate pipeline by default?
- Which runtime metrics are mandatory versus optional?

## Status Criteria

This ADR is considered implemented when:

- the planner produces immutable execution plans,
- the executor does not perform planning,
- middleware can short-circuit safely,
- cancellation is propagated end-to-end,
- resource provenance is preserved,
- signals remain observational,
- terminal failures can be routed to a DLQ in distributed mode,
- the implementation is verified by tests and architecture checks.
