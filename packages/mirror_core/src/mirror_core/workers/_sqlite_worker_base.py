"""Private SQLite persistence helpers for the SQLite worker backend."""

from __future__ import annotations

import json
import sqlite3
from uuid import UUID

from mirror_core.workers._util import _parse_datetime, _utcnow
from mirror_core.workers.models import JobState, WorkerJob


class _SQLiteWorkerBackendBase:
    """Private SQLite storage helpers for the SQLite worker backend.

    The backend subclass inherits these helpers so schema, row, and
    transition logic stays co-located with the public API while keeping
    each module under the repository line limit.
    """

    _conn: sqlite3.Connection | None
    _started: bool

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._started = False

    def _transition(
        self,
        job_id: UUID,
        state: JobState,
        *,
        error: str | None,
        cancelled: bool = False,
    ) -> WorkerJob:
        conn = self._connection()
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (str(job_id),)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown job: {job_id}")
        updated_at = _utcnow().isoformat()
        completed_at = (
            updated_at
            if state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}
            else None
        )
        cancelled_at = updated_at if cancelled else None
        conn.execute(
            """
            UPDATE jobs
            SET state = ?, error = ?, updated_at = ?, completed_at = ?, cancelled_at = ?, lease_expires_at = NULL
            WHERE job_id = ?
            """,
            (state.value, error, updated_at, completed_at, cancelled_at, str(job_id)),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (str(job_id),)
        ).fetchone()
        return self._row_to_job(updated)

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Worker backend is not started")
        return self._conn

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("Worker backend is not started")

    def _ensure_schema(self) -> None:
        conn = self._connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                run_id TEXT NOT NULL,
                pipeline_id TEXT NOT NULL,
                step_id TEXT,
                execution_class TEXT NOT NULL DEFAULT 'default',
                payload TEXT NOT NULL,
                state TEXT NOT NULL,
                worker_id TEXT,
                error TEXT,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                claimed_at TEXT,
                completed_at TEXT,
                cancelled_at TEXT,
                lease_expires_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id TEXT NOT NULL,
                job_id TEXT,
                at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_state_class_created ON jobs(state, execution_class, created_at)"
        )
        conn.commit()

    def _row_to_job(self, row: sqlite3.Row | None) -> WorkerJob:
        if row is None:
            raise RuntimeError("Expected a job row")
        return WorkerJob(
            job_id=UUID(row["job_id"]),
            kind=row["kind"],
            run_id=UUID(row["run_id"]),
            pipeline_id=row["pipeline_id"],
            step_id=row["step_id"],
            execution_class=row["execution_class"],
            payload=json.loads(row["payload"]),
            state=JobState(row["state"]),
            worker_id=row["worker_id"],
            error=row["error"],
            metadata=json.loads(row["metadata"]),
            submitted_at=_parse_datetime(row["created_at"]),
            claimed_at=_parse_datetime(row["claimed_at"])
            if row["claimed_at"]
            else None,
            completed_at=_parse_datetime(row["completed_at"])
            if row["completed_at"]
            else None,
            cancelled_at=_parse_datetime(row["cancelled_at"])
            if row["cancelled_at"]
            else None,
            lease_expires_at=_parse_datetime(row["lease_expires_at"])
            if row["lease_expires_at"]
            else None,
        )
