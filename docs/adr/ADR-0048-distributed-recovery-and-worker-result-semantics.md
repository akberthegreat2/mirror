# ADR-0048: Distributed Recovery and Worker Result Semantics

## Status

Accepted

## Context

Two distributed-correctness defects were confirmed live (review findings F5 /
P0.1 / Red#1 and P1.1 / Red#2).

### Recovery is incomplete

`PostgresWorkerBackend.requeue_expired()` flips an expired job back to `queued`
in PostgreSQL, but the Celery reaper task (`mirror.requeue_expired`) counts the
returned jobs and discards them. It never republishes a Celery task message, so
a lease-expired job is never delivered again:

```text
worker dies -> lease expires -> PG marks queued -> NO NEW CELERY MESSAGE
```

`docs/WORKER_CONTRACT.md` promises automatic reclamation, so the documented
recovery path is not met. CLAUDE.md §8 treats recovery as a correctness
boundary: the complete path is `expired lease -> reclaimable -> republished ->
claimed -> resumes/retries`.

### Worker result mapping is wrong

`_execute_job()` runs `await app.execute_worker_job(job)` (returns an
`ExecutionResult`) and then unconditionally calls
`await runtime.complete(job.job_id)`. A failed execution that does not raise is
therefore recorded as a successful durable job:

```text
ExecutionResult = FAILED, worker job state = SUCCEEDED
```

CLAUDE.md §9 requires terminal mappings to distinguish SUCCEEDED, FAILED, and
CANCELLED explicitly, and forbids inferring success from the absence of an
exception.

## Decision

### 1. Reaper republishes requeued jobs

The Celery reaper, after `requeue_expired()`, republishes every returned job ID
to the correct execution-class queue by reusing the existing
`queue_name(execution_class)` mapping and the transport `publish` path. The
reaper must be idempotent under duplicate delivery (a job published twice is
still only claimed once, per the backend's atomic claim).

### 2. Worker terminal mapping

`_execute_job()` inspects the returned `ExecutionResult` and maps it explicitly:

```text
ExecutionResult.SUCCEEDED -> runtime.complete(job_id)
ExecutionResult.FAILED    -> runtime.fail(job_id, error, terminal=True)
ExecutionResult.CANCELLED -> runtime.cancel(job_id, reason)
```

The durable worker job terminal state MUST match the execution outcome. A
successful worker-function return without a SUCCEEDED result is never treated
as success.

### 3. Recovery test matrix

The distributed test suite covers the complete recovery path per CLAUDE.md §8:
worker crash, lease expiry, requeue, republish, duplicate delivery, stale
worker, heartbeat loss, cancellation, and checkpoint recovery — against real
PostgreSQL + Redis + Celery in the Docker lab (ADR-0049).

## Consequences

- Lease-expired jobs are actually re-delivered and resume, satisfying the
  documented recovery promise.
- Worker job state no longer disagrees with execution outcome.
- The recovery test matrix becomes a mandatory external gate before beta.
- The transport change and reaper change are tracked in
  PR_BETA_DISTRIBUTED_RECOVERY.
