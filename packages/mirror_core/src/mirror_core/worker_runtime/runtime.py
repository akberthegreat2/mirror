"""Worker runtime coordination for backends, leases, and durable state."""

from __future__ import annotations

from uuid import UUID

from mirror_core.metadata import (
    MetadataRecord,
    MetadataStore,
)
from mirror_core.worker_runtime.util import _utcnow
from mirror_core.workers import (
    CheckpointStore,
    DeadLetterQueue,
    DeadLetterRecord,
    ExecutionRecord,
    ExecutionStore,
    LeaseManager,
    WorkerBackend,
    WorkerJob,
)


class WorkerRuntime:
    """Core-owned coordination layer for worker backends and durable state."""

    def __init__(
        self,
        backend: WorkerBackend,
        *,
        execution_store: ExecutionStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        dead_letter_queue: DeadLetterQueue | None = None,
        metadata_store: MetadataStore | None = None,
        lease_manager: LeaseManager | None = None,
    ) -> None:
        self.backend = backend
        self.execution_store = execution_store
        self.checkpoint_store = checkpoint_store
        self.dead_letter_queue = dead_letter_queue
        self.metadata_store = metadata_store
        self.lease_manager = lease_manager

    async def start(self) -> None:
        """Start the underlying backend."""
        await self.backend.start()

    async def stop(self) -> None:
        """Stop the underlying backend."""
        await self.backend.stop()

    async def submit(self, job: WorkerJob) -> WorkerJob:
        """Submit a new worker job and persist the audit trail."""
        stored = await self.backend.submit(job)
        self._record(
            MetadataRecord.audit_event(
                stored.job_id,
                "worker.job.submitted",
                payload={
                    "kind": stored.kind,
                    "state": stored.state.value,
                    "run_id": str(stored.run_id),
                    "pipeline_id": stored.pipeline_id,
                    "step_id": stored.step_id,
                    "metadata": dict(stored.metadata),
                },
            )
        )
        return stored

    async def claim(
        self, worker_id: str, execution_class: str = "default"
    ) -> WorkerJob | None:
        """Claim the next queued job for a worker in one execution class."""
        job = await self.backend.claim(worker_id, execution_class)
        if job is None:
            self._record(
                MetadataRecord.worker(
                    worker_id,
                    payload={"state": "idle", "at": _utcnow().isoformat()},
                )
            )
            return None
        if self.lease_manager is not None:
            lease = self.lease_manager.acquire(job.job_id, worker_id)
            self._record(
                MetadataRecord.worker_lease(
                    job.job_id,
                    worker_id,
                    payload={"expires_at": lease.expires_at.isoformat()},
                )
            )
        self._record(
            MetadataRecord.worker(
                worker_id,
                payload={
                    "state": "running",
                    "job_id": str(job.job_id),
                    "run_id": str(job.run_id),
                    "pipeline_id": job.pipeline_id,
                    "step_id": job.step_id,
                    "kind": job.kind,
                },
            )
        )
        return job

    async def claim_job(self, job_id: UUID, worker_id: str) -> WorkerJob | None:
        """Claim one specific job through the backend contract."""
        job = await self.backend.claim_job(job_id, worker_id)
        if job is not None and self.lease_manager is not None:
            lease = self.lease_manager.acquire(job.job_id, worker_id)
            self._record(
                MetadataRecord.worker_lease(
                    job.job_id,
                    worker_id,
                    payload={"expires_at": lease.expires_at.isoformat()},
                )
            )
        return job

    async def heartbeat(self, worker_id: str, job_id: UUID | None = None) -> None:
        """Mark a worker as alive and refresh the lease if possible."""
        await self.backend.heartbeat(worker_id, job_id)
        if job_id is not None and self.lease_manager is not None:
            lease = (
                self.lease_manager.get(job_id)
                if hasattr(self.lease_manager, "get")
                else None
            )
            if lease is not None:
                renewed = self.lease_manager.renew(lease)
                self._record(
                    MetadataRecord.worker_lease(
                        job_id,
                        worker_id,
                        payload={"expires_at": renewed.expires_at.isoformat()},
                    )
                )
        self._record(
            MetadataRecord.worker(
                worker_id,
                payload={
                    "state": "heartbeat",
                    "job_id": str(job_id) if job_id is not None else None,
                    "at": _utcnow().isoformat(),
                },
            )
        )

    async def complete(self, job_id: UUID) -> WorkerJob:
        """Mark a job as completed and persist the execution record."""
        job = await self.backend.complete(job_id)
        self._release_lease(job)
        self._record_execution(job, outcome="succeeded")
        return job

    async def fail(
        self, job_id: UUID, error: str, *, terminal: bool = True
    ) -> WorkerJob:
        """Mark a job as failed and optionally route it to the DLQ."""
        job = await self.backend.fail(job_id, error)
        self._release_lease(job)
        self._record_execution(job, outcome="failed", error=error)
        if terminal and self.dead_letter_queue is not None:
            self.dead_letter_queue.record(
                DeadLetterRecord(
                    run_id=job.run_id,
                    pipeline_id=job.pipeline_id or job.kind,
                    step_id=job.step_id or job.metadata.get("step_id"),
                    reason=error,
                    original_inputs=dict(job.payload),
                    policy_state=dict(job.metadata),
                    provenance={
                        "worker_id": job.worker_id,
                        "job_id": str(job.job_id),
                        "run_id": str(job.run_id),
                    },
                    retry_count=int(job.metadata.get("retry_count", 0) or 0),
                    terminal_status="failed",
                    worker_id=job.worker_id,
                    lease_id=str(job.job_id),
                )
            )
            self._record(
                MetadataRecord.audit_event(
                    job.job_id,
                    "worker.job.dead_lettered",
                    payload={
                        "kind": job.kind,
                        "error": error,
                        "worker_id": job.worker_id,
                        "run_id": str(job.run_id),
                        "pipeline_id": job.pipeline_id,
                        "step_id": job.step_id,
                    },
                )
            )
        return job

    async def cancel(self, job_id: UUID, reason: str | None = None) -> WorkerJob:
        """Cancel a job cooperatively."""
        job = await self.backend.cancel(job_id, reason)
        self._release_lease(job)
        self._record_execution(job, outcome="cancelled", error=reason)
        self._record(
            MetadataRecord.audit_event(
                job.job_id,
                "worker.job.cancelled",
                payload={
                    "kind": job.kind,
                    "reason": reason,
                    "worker_id": job.worker_id,
                    "run_id": str(job.run_id),
                    "pipeline_id": job.pipeline_id,
                    "step_id": job.step_id,
                },
            )
        )
        return job

    async def requeue_expired(self) -> list[WorkerJob]:
        """Requeue any jobs whose leases have expired."""
        jobs = self.backend.requeue_expired()
        for job in jobs:
            self._record(
                MetadataRecord.audit_event(
                    job.job_id,
                    "worker.job.requeued",
                    payload={"kind": job.kind, "worker_id": job.worker_id},
                )
            )
        return jobs

    def _release_lease(self, job: WorkerJob) -> None:
        if self.lease_manager is None:
            return
        lease = (
            self.lease_manager.get(job.job_id)
            if hasattr(self.lease_manager, "get")
            else None
        )
        if lease is not None:
            self.lease_manager.release(lease)

    def _record_execution(
        self, job: WorkerJob, *, outcome: str, error: str | None = None
    ) -> None:
        if self.execution_store is not None:
            self.execution_store.record(
                ExecutionRecord(
                    run_id=job.run_id,
                    outcome=outcome,
                    payload=dict(job.payload),
                    worker_id=job.worker_id,
                    created_at=job.submitted_at,
                    started_at=job.claimed_at,
                    completed_at=job.completed_at or job.cancelled_at or _utcnow(),
                    metadata={
                        **dict(job.metadata),
                        **({"error": error} if error else {}),
                        "run_id": str(job.run_id),
                        "pipeline_id": job.pipeline_id,
                        "step_id": job.step_id,
                    },
                )
            )
        run_id = job.run_id or job.job_id
        self._record(
            MetadataRecord.execution_run(
                run_id,
                payload={
                    "kind": job.kind,
                    "outcome": outcome,
                    "worker_id": job.worker_id,
                    "error": error,
                    "run_id": str(job.run_id),
                    "pipeline_id": job.pipeline_id,
                    "step_id": job.step_id,
                    "metadata": dict(job.metadata),
                },
            )
        )

    def _record(self, record: MetadataRecord) -> None:
        if self.metadata_store is not None:
            self.metadata_store.put(record)
