"""In-memory worker backend for development and tests."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from uuid import UUID

from mirror_core.workers._util import _utcnow
from mirror_core.workers.models import JobState, WorkerJob


class InlineWorker:
    """In-memory worker backend for development and tests."""

    def __init__(self) -> None:
        self._jobs: deque[WorkerJob] = deque()
        self._jobs_by_id: dict[UUID, WorkerJob] = {}
        self._started = False
        self._heartbeats: list[tuple[str, UUID | None]] = []

    async def start(self) -> None:
        """Mark the backend as ready to accept jobs."""
        self._started = True

    async def stop(self) -> None:
        """Mark the backend as stopped."""
        self._started = False

    async def submit(self, job: WorkerJob) -> WorkerJob:
        """Enqueue a new job."""
        self._ensure_started()
        stored = job.model_copy(
            update={"state": JobState.QUEUED, "submitted_at": _utcnow()}
        )
        self._jobs.append(stored)
        self._jobs_by_id[stored.job_id] = stored
        return stored

    async def claim(
        self, worker_id: str, execution_class: str = "default"
    ) -> WorkerJob | None:
        """Claim the next queued job for a worker in one execution class."""
        self._ensure_started()
        while self._jobs:
            job = self._jobs.popleft()
            if (
                job.state is not JobState.QUEUED
                or job.execution_class != execution_class
            ):
                continue
            now = _utcnow()
            claimed = job.model_copy(
                update={
                    "state": JobState.RUNNING,
                    "worker_id": worker_id,
                    "claimed_at": now,
                    "lease_expires_at": now + timedelta(seconds=60),
                }
            )
            self._jobs_by_id[claimed.job_id] = claimed
            return claimed
        return None

    async def claim_job(self, job_id: UUID, worker_id: str) -> WorkerJob | None:
        """Claim one specific queued job."""
        self._ensure_started()
        job = self._jobs_by_id.get(job_id)
        if job is None or job.state is not JobState.QUEUED:
            return None
        now = _utcnow()
        claimed = job.model_copy(
            update={
                "state": JobState.RUNNING,
                "worker_id": worker_id,
                "claimed_at": now,
                "lease_expires_at": now + timedelta(seconds=60),
            }
        )
        self._jobs_by_id[job_id] = claimed
        return claimed

    async def get(self, job_id: UUID) -> WorkerJob | None:
        self._ensure_started()
        return self._jobs_by_id.get(job_id)

    async def heartbeat(self, worker_id: str, job_id: UUID | None = None) -> None:
        """Record a worker heartbeat."""
        self._ensure_started()
        self._heartbeats.append((worker_id, job_id))

    async def complete(self, job_id: UUID) -> WorkerJob:
        """Mark a job as succeeded."""
        self._ensure_started()
        job = self._require_job(job_id)
        completed = job.model_copy(
            update={
                "state": JobState.SUCCEEDED,
                "error": None,
                "completed_at": _utcnow(),
                "lease_expires_at": None,
            }
        )
        self._jobs_by_id[job_id] = completed
        return completed

    async def fail(self, job_id: UUID, error: str) -> WorkerJob:
        """Mark a job as failed."""
        self._ensure_started()
        job = self._require_job(job_id)
        failed = job.model_copy(
            update={
                "state": JobState.FAILED,
                "error": error,
                "completed_at": _utcnow(),
                "lease_expires_at": None,
            }
        )
        self._jobs_by_id[job_id] = failed
        return failed

    async def cancel(self, job_id: UUID, reason: str | None = None) -> WorkerJob:
        """Mark a job as cancelled."""
        self._ensure_started()
        job = self._require_job(job_id)
        cancelled = job.model_copy(
            update={
                "state": JobState.CANCELLED,
                "error": reason or job.error,
                "cancelled_at": _utcnow(),
                "lease_expires_at": None,
            }
        )
        self._jobs_by_id[job_id] = cancelled
        return cancelled

    def requeue_expired(self, *, now: datetime | None = None) -> list[WorkerJob]:
        """Requeue running jobs whose leases have expired."""
        self._ensure_started()
        now = _utcnow() if now is None else _utcnow() if now.tzinfo is None else now
        requeued: list[WorkerJob] = []
        for job in list(self._jobs_by_id.values()):
            if job.state is not JobState.RUNNING:
                continue
            if job.lease_expires_at is None or job.lease_expires_at > now:
                continue
            updated = job.model_copy(
                update={
                    "state": JobState.QUEUED,
                    "worker_id": None,
                    "claimed_at": None,
                    "lease_expires_at": None,
                }
            )
            self._jobs_by_id[job.job_id] = updated
            self._jobs.append(updated)
            requeued.append(updated)
        return requeued

    @property
    def jobs(self) -> list[WorkerJob]:
        """Return the current in-memory queue snapshot."""
        return list(self._jobs_by_id.values())

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("Worker backend is not started")

    def _require_job(self, job_id: UUID) -> WorkerJob:
        try:
            return self._jobs_by_id[job_id]
        except KeyError as exc:
            raise KeyError(f"Unknown job: {job_id}") from exc
