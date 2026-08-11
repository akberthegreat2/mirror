# ADR-0031: Scheduler Backend Architecture

**Status:** Accepted

**Ratified:** 2026-08-10 as part of the beta structural phase. The scheduler
graduated into the stable core package (`mirror_core.scheduler`); workers execute
runs, and schedulers only create/enqueue them, per this decision.

## Context

Mirror already treats scheduling as a core concern rather than a capability concern. However, the repository still needs an explicit architectural decision for how scheduling backends are modeled.

Scheduling must support more than one execution style:

- one-shot/manual runs
- delayed runs
- recurring cron-style schedules
- dependency-triggered runs
- backfills and catch-up jobs
- future external orchestrators

The scheduler must remain vendor-neutral. It must not depend on a single system such as Celery Beat or Airflow as its architectural truth.

## Decision

Mirror will define a Scheduler Backend contract in `mirror_core`.

The scheduler is responsible for deciding when a run should be created and enqueued. It does not execute work itself.

### Ownership

- `mirror_core` owns scheduling semantics and the scheduler contract.
- Capability packages do not define scheduling logic.
- Providers may implement scheduler backends.
- Workers execute runs; schedulers only create or enqueue them.
- Interfaces may expose scheduling controls, but only through the core contract.

### Scope

The scheduler backend covers:

- schedule definitions
- trigger evaluation
- cron-like recurrence
- delayed execution
- one-shot scheduling
- backfill/catch-up rules
- concurrency limits
- queue handoff
- run creation metadata
- schedule pause/resume state
- next-run calculation
- disabled/expired schedule handling

### Non-scope

The scheduler backend does **not** own:

- execution planning
- provider invocation
- middleware execution
- worker runtime
- queue internals
- metadata schema details beyond what it needs to schedule safely

Those are owned by their respective core subsystems.

## Consequences

### Positive

- Mirror can support multiple scheduling implementations without changing the framework contract.
- Scheduling can evolve independently from workers and execution.
- External orchestrators such as Airflow can be integrated as backends rather than hard dependencies.

### Tradeoffs

- The scheduler contract must be explicit about timing, state transitions, and idempotency.
- The schedule model must be versioned carefully to avoid drift.
- There must be a clear boundary between schedule state and execution state.

## Architectural Rules

1. Scheduling semantics belong to `mirror_core`.
2. Schedulers create or enqueue runs; they do not execute them.
3. Capability packages must not own their own scheduler logic.
4. Scheduler backends must be interchangeable.
5. Scheduler implementations must use the same metadata store contract as the rest of core runtime state.

## Relationship to other ADRs

- Uses the metadata store for schedule state and run bookkeeping.
- Depends on runtime semantics for run creation and terminal states.
- Works with distributed execution and worker backends.
- Can be surfaced through interfaces such as CLI, REST, or admin dashboards.

## Status Summary

Ratified 2026-08-10. The scheduler contract exists in `mirror_core`
(`SchedulerBackend` protocol) with a coordinator integrated with the metadata
store and worker backend.
