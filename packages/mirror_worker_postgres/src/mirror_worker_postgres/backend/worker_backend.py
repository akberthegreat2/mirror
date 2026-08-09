from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from mirror_core.metadata import encode_metadata_value
from mirror_core.workers import JobState, WorkerBackend, WorkerJob

from mirror_worker_postgres.backend.connection import _PostgresConnection, _utcnow
from mirror_worker_postgres.backend.metadata_store import _job_from_row

_MIGRATION = Path(__file__).parent.parent / "migrations" / "001_initial.sql"


class PostgresWorkerBackend(WorkerBackend):
    """Durable PostgreSQL queue with transactional claim and lease recovery."""

    def __init__(self, dsn: str, *, lease_seconds: int = 60) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self.dsn = dsn
        self.lease_seconds = lease_seconds
        self._db = _PostgresConnection(dsn)
        self._started = False

    async def start(self) -> None:
        await asyncio.to_thread(self._start_sync)

    def _start_sync(self) -> None:
        self._db.connect()
        migration = _MIGRATION.read_text(encoding="utf-8")
        statements = [
            statement.strip() for statement in migration.split(";") if statement.strip()
        ]
        for statement in statements:
            self._db.execute(statement)
        self._started = True

    async def stop(self) -> None:
        await asyncio.to_thread(self._db.close)
        self._started = False

    async def submit(self, job: WorkerJob) -> WorkerJob:
        self._ensure_started()
        stored = job.model_copy(
            update={
                "state": JobState.QUEUED,
                "error": None,
                "submitted_at": _utcnow(),
                "claimed_at": None,
                "completed_at": None,
                "cancelled_at": None,
                "lease_expires_at": None,
            }
        )
        await asyncio.to_thread(self._submit_sync, stored)
        return stored

    def _submit_sync(self, job: WorkerJob) -> None:
        self._db.execute(
            """
            INSERT INTO mirror_jobs(
                job_id, kind, run_id, pipeline_id, step_id, execution_class,
                payload, state, worker_id, error, metadata, submitted_at,
                claimed_at, completed_at, cancelled_at, lease_expires_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
            ON CONFLICT(job_id) DO UPDATE SET
                kind=EXCLUDED.kind, run_id=EXCLUDED.run_id, pipeline_id=EXCLUDED.pipeline_id,
                step_id=EXCLUDED.step_id, execution_class=EXCLUDED.execution_class,
                payload=EXCLUDED.payload, state=EXCLUDED.state, worker_id=EXCLUDED.worker_id,
                error=EXCLUDED.error, metadata=EXCLUDED.metadata, submitted_at=EXCLUDED.submitted_at,
                claimed_at=EXCLUDED.claimed_at, completed_at=EXCLUDED.completed_at,
                cancelled_at=EXCLUDED.cancelled_at, lease_expires_at=EXCLUDED.lease_expires_at
            """,
            (
                str(job.job_id),
                job.kind,
                str(job.run_id) if job.run_id else None,
                job.pipeline_id,
                job.step_id,
                job.execution_class,
                json.dumps(encode_metadata_value(job.payload)),
                job.state.value,
                job.worker_id,
                job.error,
                json.dumps(encode_metadata_value(job.metadata)),
                job.submitted_at,
                job.claimed_at,
                job.completed_at,
                job.cancelled_at,
                job.lease_expires_at,
            ),
        )

    async def get(self, job_id: UUID) -> WorkerJob | None:
        self._ensure_started()
        rows = await asyncio.to_thread(
            self._db.execute,
            "SELECT * FROM mirror_jobs WHERE job_id=%s",
            (str(job_id),),
        )
        return None if not rows else _job_from_row(rows[0])

    async def claim(
        self, worker_id: str, execution_class: str = "default"
    ) -> WorkerJob | None:
        self._ensure_started()
        rows = await asyncio.to_thread(
            self._claim_sync, worker_id, execution_class, None
        )
        return None if not rows else _job_from_row(rows[0])

    async def claim_job(self, job_id: UUID, worker_id: str) -> WorkerJob | None:
        self._ensure_started()
        rows = await asyncio.to_thread(self._claim_sync, worker_id, None, job_id)
        return None if not rows else _job_from_row(rows[0])

    def _claim_sync(
        self, worker_id: str, execution_class: str | None, job_id: UUID | None
    ) -> list[dict[str, Any]]:
        now = _utcnow()
        expires = now + timedelta(seconds=self.lease_seconds)
        class_filter = "AND execution_class = %s" if execution_class else ""
        id_filter = "AND job_id = %s" if job_id else ""
        params: list[Any] = [now]
        if execution_class:
            params.append(execution_class)
        if job_id:
            params.append(str(job_id))
        params.extend([worker_id, now, expires])
        with self._db._lock:
            self._db.connect()
            assert self._db._connection is not None
            connection = self._db._connection
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    f"""
                        WITH candidate AS (
                            SELECT job_id FROM mirror_jobs
                            WHERE state = 'queued'
                              AND (lease_expires_at IS NULL OR lease_expires_at <= %s)
                              {class_filter}
                              {id_filter}
                            ORDER BY submitted_at, job_id
                            FOR UPDATE SKIP LOCKED
                            LIMIT 1
                        )
                        UPDATE mirror_jobs AS j
                        SET state='running', worker_id=%s, claimed_at=%s, lease_expires_at=%s
                        FROM candidate
                        WHERE j.job_id = candidate.job_id
                        RETURNING j.*
                        """,
                    tuple(params),
                )
                if cursor.description is None:
                    return []
                return list(cursor.fetchall())

    async def heartbeat(self, worker_id: str, job_id: UUID | None = None) -> None:
        self._ensure_started()
        await asyncio.to_thread(self._heartbeat_sync, worker_id, job_id)

    def _heartbeat_sync(self, worker_id: str, job_id: UUID | None) -> None:
        expires = _utcnow() + timedelta(seconds=self.lease_seconds)
        if job_id is None:
            self._db.execute(
                "INSERT INTO mirror_worker_heartbeats(worker_id, heartbeat_at) VALUES (%s,%s) ON CONFLICT(worker_id) DO UPDATE SET heartbeat_at=EXCLUDED.heartbeat_at",
                (worker_id, _utcnow()),
            )
            return
        self._db.execute(
            "UPDATE mirror_jobs SET lease_expires_at=%s WHERE job_id=%s AND state='running' AND worker_id=%s",
            (expires, str(job_id), worker_id),
        )
        self._db.execute(
            "INSERT INTO mirror_worker_heartbeats(worker_id, heartbeat_at) VALUES (%s,%s) ON CONFLICT(worker_id) DO UPDATE SET heartbeat_at=EXCLUDED.heartbeat_at",
            (worker_id, _utcnow()),
        )

    async def complete(self, job_id: UUID) -> WorkerJob:
        return await self._transition(job_id, JobState.SUCCEEDED, None)

    async def fail(self, job_id: UUID, error: str) -> WorkerJob:
        return await self._transition(job_id, JobState.FAILED, error)

    async def cancel(self, job_id: UUID, reason: str | None = None) -> WorkerJob:
        return await self._transition(job_id, JobState.CANCELLED, reason)

    async def _transition(
        self, job_id: UUID, state: JobState, error: str | None
    ) -> WorkerJob:
        self._ensure_started()
        rows = await asyncio.to_thread(
            self._db.execute,
            """
            UPDATE mirror_jobs SET state=%s, error=%s, completed_at=%s,
                cancelled_at=CASE WHEN %s='cancelled' THEN %s ELSE cancelled_at END,
                lease_expires_at=NULL
            WHERE job_id=%s AND state='running'
            RETURNING *
            """,
            (state.value, error, _utcnow(), state.value, _utcnow(), str(job_id)),
        )
        if not rows:
            raise RuntimeError(f"Job {job_id} is not running or does not exist")
        return _job_from_row(rows[0])

    def requeue_expired(self, *, now: datetime | None = None) -> list[WorkerJob]:
        self._ensure_started()
        now = now or _utcnow()
        rows = self._db.execute(
            """
            UPDATE mirror_jobs SET state='queued', worker_id=NULL, claimed_at=NULL, lease_expires_at=NULL
            WHERE state='running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= %s
            RETURNING *
            """,
            (now,),
        )
        return [_job_from_row(row) for row in rows]

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("PostgreSQL worker backend is not started")
