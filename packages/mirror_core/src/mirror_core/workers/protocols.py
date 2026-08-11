"""Worker protocol contracts for backends, stores, queues, and leases."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from mirror_core.workers.models import (
    DeadLetterRecord,
    ExecutionRecord,
    WorkerJob,
    WorkerLease,
)


@runtime_checkable
class WorkerBackend(Protocol):
    """Backend contract for worker transports."""

    async def start(self) -> None:
        """Prepare the backend for job submission."""
        ...

    async def stop(self) -> None:
        """Release backend resources."""
        ...

    async def probe(self) -> bool:
        """Check if the backend is reachable without full startup.

        Returns True if the backend infrastructure is available,
        False if it's not configured or unreachable.
        """
        ...

    async def submit(self, job: WorkerJob) -> WorkerJob:
        """Submit a job and return its stored representation."""
        ...

    async def claim(
        self, worker_id: str, execution_class: str = "default"
    ) -> WorkerJob | None:
        """Claim the next queued job for a worker."""
        ...

    async def claim_job(self, job_id: UUID, worker_id: str) -> WorkerJob | None:
        """Claim one specific queued job atomically."""
        ...

    async def get(self, job_id: UUID) -> WorkerJob | None:
        """Return one job without changing its state."""
        ...

    async def heartbeat(self, worker_id: str, job_id: UUID | None = None) -> None:
        """Mark a worker as alive for observability and leasing."""
        ...

    async def complete(self, job_id: UUID) -> WorkerJob:
        """Mark a job as completed."""
        ...

    async def fail(self, job_id: UUID, error: str) -> WorkerJob:
        """Mark a job as failed."""
        ...

    async def cancel(self, job_id: UUID, reason: str | None = None) -> WorkerJob:
        """Mark a job as cancelled."""
        ...

    def requeue_expired(self, *, now: datetime | None = None) -> list[WorkerJob]:
        """Requeue jobs whose leases have expired."""
        ...


@runtime_checkable
class ExecutionStore(Protocol):
    """Persistence contract for execution metadata."""

    def record(self, record: ExecutionRecord) -> None: ...

    def get(self, run_id: UUID) -> ExecutionRecord | None: ...

    def list(self) -> list[ExecutionRecord]: ...


@runtime_checkable
class DeadLetterQueue(Protocol):
    """Persistence contract for terminal failures."""

    def record(self, record: DeadLetterRecord) -> None: ...

    def get(self, run_id: UUID) -> DeadLetterRecord | None: ...

    def replay(self, run_id: UUID) -> DeadLetterRecord | None: ...

    def list(self) -> list[DeadLetterRecord]: ...


@runtime_checkable
class CheckpointStore(Protocol):
    """Persistence contract for resumable step checkpoints."""

    def save(self, run_id: UUID, step_id: str, payload: Mapping[str, Any]) -> None: ...

    def load(self, run_id: UUID, step_id: str) -> dict[str, Any] | None: ...

    def latest(self, run_id: UUID) -> tuple[str, dict[str, Any]] | None: ...

    def delete(self, run_id: UUID, step_id: str) -> None: ...


@runtime_checkable
class ArtifactStore(Protocol):
    """Persistence contract for binary or large artifacts."""

    def put_bytes(self, key: str, payload: bytes) -> None: ...

    def get_bytes(self, key: str) -> bytes | None: ...

    def delete(self, key: str) -> None: ...


@runtime_checkable
class LeaseManager(Protocol):
    """Lease contract used to coordinate workers."""

    def acquire(
        self, job_id: UUID, worker_id: str, ttl_seconds: int = 60
    ) -> WorkerLease: ...

    def renew(self, lease: WorkerLease, ttl_seconds: int = 60) -> WorkerLease: ...

    def release(self, lease: WorkerLease) -> None: ...

    def get(self, job_id: UUID) -> WorkerLease | None: ...

    def list(self) -> list[WorkerLease]: ...

