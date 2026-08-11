# PR: Beta — distributed recovery and worker result semantics

## Problem

Two correctness defects in distributed execution:

1. **Reaper never republishes (F5 / P0.1 / Red#1).** When a lease expires, the
   reaper flips the PostgreSQL job to a reclaimable state but never republishes
   the job to the Celery broker. The job is orphaned forever — there is no
   complete recovery path as required by CLAUDE.md §8.
2. **Worker marks jobs SUCCEEDED regardless of outcome (P1.1 / Red#2).** The
   worker calls `runtime.complete` unconditionally, so a failed
   `ExecutionResult` is recorded as a successful durable job. Terminal mappings
   must distinguish SUCCEEDED / FAILED / CANCELLED per CLAUDE.md §9.

## Decision

Establish the complete recovery path and explicit terminal semantics (ADR-0048):

- The reaper republishes requeued job IDs to the correct execution-class queue
  by reusing the existing `queue_name(execution_class)` / `publish` mechanism,
  instead of only mutating PostgreSQL state.
- The worker maps the `ExecutionResult` outcome to the durable job terminal state
  (SUCCEEDED / FAILED / CANCELLED); success is never inferred from the absence of
  an exception.
- Duplicate-delivery and fencing behavior is tested under at-least-once delivery
  (CLAUDE.md §10).

## What changed

- Reworked the reaper to republish requeued jobs to the right queue.
- Reworked the worker completion path to map `ExecutionResult` to the correct
  terminal state.
- Added the recovery test matrix: worker crash, lease expiry, requeue,
  republish, duplicate delivery, stale worker, heartbeat loss, cancellation,
  checkpoint recovery.

## Validation

- Recovery tests prove the full path: expired lease -> durable job reclaimable ->
  job republished -> worker claims it -> execution resumes/retries.
- Terminal-mapping tests prove FAILED and CANCELLED results are never recorded as
  SUCCEEDED.
- Duplicate-delivery tests confirm idempotency/fencing is respected.

## Deferred

- The beta release gate that certifies distributed execution against a real
  Docker lab is covered in `PR_BETA_RELEASE_GATE.md`.
