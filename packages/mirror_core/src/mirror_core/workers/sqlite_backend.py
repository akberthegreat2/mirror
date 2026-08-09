"""SQLite-backed worker backend for durable local workflows."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from mirror_core.workers._sqlite_worker_base import _SQLiteWorkerBackendBase
from mirror_core.workers._util import _utcnow
from mirror_core.workers.models import JobState, WorkerJob


class SQLiteWorkerBackend(_SQLiteWorkerBackendBase):
    """SQLite-backed worker backend for durable local workflows.

    The backend stores jobs, state transitions, and heartbeats in a single
    SQLite database so local development and smoke tests exercise a
    production-like queue lifecycle without needing Redis or Celery.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._conn: sqlite3.Connection | None = None
        self._started = False

    async def start(self) -> None:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._ensure_schema()
        self._started = True

    async def stop(self) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None
        self._started = False

    async def submit(self, job: WorkerJob) -> WorkerJob:
        self._ensure_started()
        now = _utcnow()
        stored = job.model_copy(
            update={
                "state": JobState.QUEUED,
                "error": None,
                "submitted_at": now,
                "claimed_at": None,
                "completed_at": None,
                "cancelled_at": None,
                "lease_expires_at": None,
            }
        )
        conn = self._connection()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, kind, run_id, pipeline_id, step_id, execution_class, payload, state, worker_id, error, metadata,
                created_at, updated_at, claimed_at, completed_at, cancelled_at, lease_expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id)
            DO UPDATE SET
                kind = excluded.kind,
                run_id = excluded.run_id,
                pipeline_id = excluded.pipeline_id,
                step_id = excluded.step_id,
                execution_class = excluded.execution_class,
                payload = excluded.payload,
                state = excluded.state,
                worker_id = excluded.worker_id,
                error = excluded.error,
                metadata = excluded.metadata,
                updated_at = excluded.updated_at,
                claimed_at = excluded.claimed_at,
                completed_at = excluded.completed_at,
                cancelled_at = excluded.cancelled_at,
                lease_expires_at = excluded.lease_expires_at
            """,
            (
                str(stored.job_id),
                stored.kind,
                str(stored.run_id),
                stored.pipeline_id,
                stored.step_id,
                stored.execution_class,
                json.dumps(stored.payload, sort_keys=True),
                stored.state.value,
                stored.worker_id,
                stored.error,
                json.dumps(stored.metadata, sort_keys=True),
                now.isoformat(),
                now.isoformat(),
                None,
                None,
                None,
                None,
            ),
        )
        conn.commit()
        return stored

    async def claim(
        self, worker_id: str, execution_class: str = "default"
    ) -> WorkerJob | None:
        self._ensure_started()
        conn = self._connection()
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE state = ? AND execution_class = ?
            ORDER BY created_at, kind, job_id
            LIMIT 1
            """,
            (JobState.QUEUED.value, execution_class),
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        claimed_at = _utcnow()
        lease_expires_at = claimed_at + timedelta(seconds=60)
        conn.execute(
            """
            UPDATE jobs
            SET state = ?, worker_id = ?, updated_at = ?, claimed_at = ?, completed_at = NULL, cancelled_at = NULL, lease_expires_at = ?
            WHERE job_id = ?
            """,
            (
                JobState.RUNNING.value,
                worker_id,
                claimed_at.isoformat(),
                claimed_at.isoformat(),
                lease_expires_at.isoformat(),
                row["job_id"],
            ),
        )
        conn.commit()
        claimed = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)
        ).fetchone()
        return self._row_to_job(claimed)

    async def claim_job(self, job_id: UUID, worker_id: str) -> WorkerJob | None:
        self._ensure_started()
        conn = self._connection()
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ? AND state = ?",
            (str(job_id), JobState.QUEUED.value),
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        now = _utcnow()
        expires = now + timedelta(seconds=60)
        conn.execute(
            "UPDATE jobs SET state=?, worker_id=?, updated_at=?, claimed_at=?, lease_expires_at=? WHERE job_id=?",
            (
                JobState.RUNNING.value,
                worker_id,
                now.isoformat(),
                now.isoformat(),
                expires.isoformat(),
                str(job_id),
            ),
        )
        conn.commit()
        return self._row_to_job(
            conn.execute("SELECT * FROM jobs WHERE job_id=?", (str(job_id),)).fetchone()
        )

    async def get(self, job_id: UUID) -> WorkerJob | None:
        self._ensure_started()
        row = (
            self._connection()
            .execute("SELECT * FROM jobs WHERE job_id=?", (str(job_id),))
            .fetchone()
        )
        return None if row is None else self._row_to_job(row)

    async def heartbeat(self, worker_id: str, job_id: UUID | None = None) -> None:
        self._ensure_started()
        conn = self._connection()
        now = _utcnow()
        conn.execute(
            "INSERT INTO heartbeats(worker_id, job_id, at) VALUES (?, ?, ?)",
            (worker_id, str(job_id) if job_id is not None else None, now.isoformat()),
        )
        if job_id is not None:
            lease_expires_at = now + timedelta(seconds=60)
            conn.execute(
                """
                UPDATE jobs
                SET updated_at = ?, lease_expires_at = ?
                WHERE job_id = ?
                """,
                (now.isoformat(), lease_expires_at.isoformat(), str(job_id)),
            )
        conn.commit()

    async def complete(self, job_id: UUID) -> WorkerJob:
        self._ensure_started()
        return self._transition(job_id, JobState.SUCCEEDED, error=None)

    async def fail(self, job_id: UUID, error: str) -> WorkerJob:
        self._ensure_started()
        return self._transition(job_id, JobState.FAILED, error=error)

    async def cancel(self, job_id: UUID, reason: str | None = None) -> WorkerJob:
        self._ensure_started()
        return self._transition(
            job_id, JobState.CANCELLED, error=reason, cancelled=True
        )

    def requeue_expired(self, *, now: datetime | None = None) -> list[WorkerJob]:
        """Move expired running jobs back to the queue."""
        self._ensure_started()
        conn = self._connection()
        now = _utcnow() if now is None else _utcnow() if now.tzinfo is None else now
        rows = conn.execute(
            "SELECT job_id FROM jobs WHERE state = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?",
            (JobState.RUNNING.value, now.isoformat()),
        ).fetchall()
        requeued: list[WorkerJob] = []
        for row in rows:
            conn.execute(
                """
                UPDATE jobs
                SET state = ?, worker_id = NULL, updated_at = ?, claimed_at = NULL, completed_at = NULL, cancelled_at = NULL, lease_expires_at = NULL
                WHERE job_id = ?
                """,
                (JobState.QUEUED.value, now.isoformat(), row["job_id"]),
            )
            updated = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)
            ).fetchone()
            requeued.append(self._row_to_job(updated))
        conn.commit()
        return requeued

    @property
    def jobs(self) -> list[WorkerJob]:
        self._ensure_started()
        conn = self._connection()
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at, kind, job_id"
        ).fetchall()
        return [self._row_to_job(row) for row in rows]
