"""SQLite-backed execution stores and lease management for worker runtimes."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from mirror_core.metadata import (
    _decode_metadata_value,
    _encode_metadata_value,
)
from mirror_core.worker_runtime.util import _parse_datetime, _utcnow
from mirror_core.workers import (
    ExecutionRecord,
    WorkerLease,
)


class SQLiteExecutionStore:
    """SQLite-backed execution metadata store for worker outcomes."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def record(self, record: ExecutionRecord) -> None:
        """Store or update an execution record."""
        self._conn.execute(
            """
            INSERT INTO execution_runs(
                run_id, outcome, payload, worker_id, created_at, started_at,
                completed_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                outcome = excluded.outcome,
                payload = excluded.payload,
                worker_id = excluded.worker_id,
                created_at = excluded.created_at,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                metadata = excluded.metadata
            """,
            (
                str(record.run_id),
                record.outcome,
                json.dumps(_encode_metadata_value(record.payload), sort_keys=True),
                record.worker_id,
                record.created_at.isoformat(),
                record.started_at.isoformat()
                if record.started_at is not None
                else None,
                record.completed_at.isoformat()
                if record.completed_at is not None
                else None,
                json.dumps(_encode_metadata_value(record.metadata), sort_keys=True),
            ),
        )
        self._conn.commit()

    def get(self, run_id: UUID) -> ExecutionRecord | None:
        """Return one execution record if present."""
        row = self._conn.execute(
            "SELECT * FROM execution_runs WHERE run_id = ?", (str(run_id),)
        ).fetchone()
        return None if row is None else self._row_to_record(row)

    def list(self) -> list[ExecutionRecord]:
        """Return all stored execution records."""
        rows = self._conn.execute(
            "SELECT * FROM execution_runs ORDER BY created_at, run_id"
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_runs (
                run_id TEXT PRIMARY KEY,
                outcome TEXT NOT NULL,
                payload TEXT NOT NULL,
                worker_id TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                metadata TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ExecutionRecord:
        return ExecutionRecord(
            run_id=UUID(row["run_id"]),
            outcome=row["outcome"],
            payload=_decode_metadata_value(json.loads(row["payload"])),
            worker_id=row["worker_id"],
            created_at=_parse_datetime(row["created_at"]),
            started_at=_parse_datetime(row["started_at"])
            if row["started_at"]
            else None,
            completed_at=_parse_datetime(row["completed_at"])
            if row["completed_at"]
            else None,
            metadata=_decode_metadata_value(json.loads(row["metadata"])),
        )


class SQLiteLeaseManager:
    """SQLite-backed lease manager for durable local workflows."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def acquire(
        self, job_id: UUID, worker_id: str, ttl_seconds: int = 60
    ) -> WorkerLease:
        """Acquire or replace a lease for a job."""
        lease = WorkerLease(
            job_id=job_id,
            worker_id=worker_id,
            expires_at=_utcnow() + timedelta(seconds=ttl_seconds),
        )
        self._conn.execute(
            """
            INSERT INTO leases(job_id, worker_id, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                worker_id = excluded.worker_id,
                expires_at = excluded.expires_at
            """,
            (str(job_id), worker_id, lease.expires_at.isoformat()),
        )
        self._conn.commit()
        return lease

    def renew(self, lease: WorkerLease, ttl_seconds: int = 60) -> WorkerLease:
        """Renew an existing lease."""
        updated = lease.model_copy(
            update={"expires_at": _utcnow() + timedelta(seconds=ttl_seconds)}
        )
        self._conn.execute(
            """
            INSERT INTO leases(job_id, worker_id, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                worker_id = excluded.worker_id,
                expires_at = excluded.expires_at
            """,
            (str(updated.job_id), updated.worker_id, updated.expires_at.isoformat()),
        )
        self._conn.commit()
        return updated

    def release(self, lease: WorkerLease) -> None:
        """Release an existing lease."""
        self._conn.execute("DELETE FROM leases WHERE job_id = ?", (str(lease.job_id),))
        self._conn.commit()

    def get(self, job_id: UUID) -> WorkerLease | None:
        """Return a stored lease if present."""
        row = self._conn.execute(
            "SELECT job_id, worker_id, expires_at FROM leases WHERE job_id = ?",
            (str(job_id),),
        ).fetchone()
        if row is None:
            return None
        return WorkerLease(
            job_id=UUID(row["job_id"]),
            worker_id=row["worker_id"],
            expires_at=_parse_datetime(row["expires_at"]),
        )

    def list(self) -> list[WorkerLease]:
        """Return all active leases."""
        rows = self._conn.execute(
            "SELECT job_id, worker_id, expires_at FROM leases ORDER BY expires_at, job_id"
        ).fetchall()
        return [
            WorkerLease(
                job_id=UUID(row["job_id"]),
                worker_id=row["worker_id"],
                expires_at=_parse_datetime(row["expires_at"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leases (
                job_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
