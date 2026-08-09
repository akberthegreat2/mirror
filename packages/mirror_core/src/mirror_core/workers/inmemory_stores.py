"""In-memory reference stores for development, tests, and examples."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from mirror_core.workers.models import DeadLetterRecord, ExecutionRecord, WorkerLease


class InMemoryExecutionStore:
    """In-memory execution metadata store for the alpha phase."""

    def __init__(self) -> None:
        self._records: dict[UUID, ExecutionRecord] = {}

    def record(self, record: ExecutionRecord) -> None:
        """Store a run record."""
        self._records[record.run_id] = record

    def get(self, run_id: UUID) -> ExecutionRecord | None:
        """Return a stored run record if present."""
        return self._records.get(run_id)

    def list(self) -> list[ExecutionRecord]:
        """Return all stored run records."""
        return list(self._records.values())


class InMemoryCheckpointStore:
    """In-memory checkpoint store for resumable development workflows."""

    def __init__(self) -> None:
        self._checkpoints: dict[tuple[UUID, str], dict[str, Any]] = {}
        self._latest: dict[UUID, str] = {}

    def save(self, run_id: UUID, step_id: str, payload: Mapping[str, Any]) -> None:
        """Persist a checkpoint snapshot."""
        self._checkpoints[(run_id, step_id)] = dict(payload)
        self._latest[run_id] = step_id

    def load(self, run_id: UUID, step_id: str) -> dict[str, Any] | None:
        """Load a checkpoint snapshot."""
        payload = self._checkpoints.get((run_id, step_id))
        return None if payload is None else dict(payload)

    def latest(self, run_id: UUID) -> tuple[str, dict[str, Any]] | None:
        """Return the most recently stored checkpoint for a run."""
        step_id = self._latest.get(run_id)
        if step_id is None:
            return None
        payload = self._checkpoints.get((run_id, step_id))
        return None if payload is None else (step_id, dict(payload))

    def delete(self, run_id: UUID, step_id: str) -> None:
        """Delete a checkpoint snapshot."""
        self._checkpoints.pop((run_id, step_id), None)
        if self._latest.get(run_id) == step_id:
            remaining = [
                candidate
                for (candidate_run_id, candidate), _ in self._checkpoints.items()
                if candidate_run_id == run_id
            ]
            if remaining:
                self._latest[run_id] = remaining[-1]
            else:
                self._latest.pop(run_id, None)


class InMemoryArtifactStore:
    """In-memory artifact store for small development payloads."""

    def __init__(self) -> None:
        self._artifacts: dict[str, bytes] = {}

    def put_bytes(self, key: str, payload: bytes) -> None:
        """Store an artifact payload under a stable key."""
        self._artifacts[key] = bytes(payload)

    def get_bytes(self, key: str) -> bytes | None:
        """Return an artifact payload if present."""
        payload = self._artifacts.get(key)
        return None if payload is None else bytes(payload)

    def delete(self, key: str) -> None:
        """Delete an artifact payload."""
        self._artifacts.pop(key, None)


class InMemoryDeadLetterQueue:
    """In-memory terminal failure queue for tests and local development."""

    def __init__(self) -> None:
        self._records: dict[UUID, DeadLetterRecord] = {}

    def record(self, record: DeadLetterRecord) -> None:
        self._records[record.run_id] = record

    def get(self, run_id: UUID) -> DeadLetterRecord | None:
        return self._records.get(run_id)

    def replay(self, run_id: UUID) -> DeadLetterRecord | None:
        record = self._records.pop(run_id, None)
        return record

    def list(self) -> list[DeadLetterRecord]:
        """Return dead letters newest-first, matching durable backends."""
        return sorted(
            self._records.values(),
            key=lambda record: (record.created_at, str(record.run_id)),
            reverse=True,
        )


class InMemoryLeaseManager:
    """In-memory lease manager for single-process development."""

    def __init__(self) -> None:
        self._leases: dict[UUID, WorkerLease] = {}

    def acquire(
        self, job_id: UUID, worker_id: str, ttl_seconds: int = 60
    ) -> WorkerLease:
        """Acquire a lease for one job."""
        lease = WorkerLease(
            job_id=job_id,
            worker_id=worker_id,
            expires_at=self._expiry(ttl_seconds),
        )
        self._leases[job_id] = lease
        return lease

    def renew(self, lease: WorkerLease, ttl_seconds: int = 60) -> WorkerLease:
        """Renew an existing lease."""
        updated = lease.model_copy(update={"expires_at": self._expiry(ttl_seconds)})
        self._leases[lease.job_id] = updated
        return updated

    def release(self, lease: WorkerLease) -> None:
        """Release a lease."""
        self._leases.pop(lease.job_id, None)

    def get(self, job_id: UUID) -> WorkerLease | None:
        """Return a lease if present."""
        return self._leases.get(job_id)

    def list(self) -> list[WorkerLease]:
        """Return all stored leases."""
        return list(self._leases.values())

    def _expiry(self, ttl_seconds: int) -> datetime:
        return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

