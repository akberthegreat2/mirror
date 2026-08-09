from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from mirror_core.metadata import (
    MetadataRecord,
    MetadataStore,
    decode_metadata_value,
    encode_metadata_value,
)
from mirror_core.workers import (
    DeadLetterRecord,
    ExecutionRecord,
    JobState,
    LeaseManager,
    WorkerJob,
    WorkerLease,
)

from mirror_worker_postgres.backend.connection import _dt, _PostgresConnection, _utcnow


class PostgresMetadataStore(MetadataStore):
    """PostgreSQL structured metadata store."""

    def __init__(self, dsn: str) -> None:
        self._db = _PostgresConnection(dsn)

    def put(self, record: MetadataRecord) -> None:
        self._db.execute(
            "INSERT INTO mirror_metadata(namespace,key,payload,created_at) VALUES (%s,%s,%s::jsonb,%s) ON CONFLICT(namespace,key) DO UPDATE SET payload=EXCLUDED.payload,created_at=EXCLUDED.created_at",
            (
                record.namespace,
                record.key,
                json.dumps(encode_metadata_value(record.payload)),
                record.created_at,
            ),
        )

    def get(self, namespace: str, key: str) -> MetadataRecord | None:
        rows = self._db.execute(
            "SELECT * FROM mirror_metadata WHERE namespace=%s AND key=%s",
            (namespace, key),
        )
        if not rows:
            return None
        row = rows[0]
        return MetadataRecord(
            namespace=row["namespace"],
            key=row["key"],
            payload=decode_metadata_value(row["payload"]),
            created_at=_dt(row["created_at"]) or _utcnow(),
        )

    def list(self, namespace: str | None = None) -> list[MetadataRecord]:
        if namespace is None:
            rows = self._db.execute(
                "SELECT * FROM mirror_metadata ORDER BY namespace,key"
            )
        else:
            rows = self._db.execute(
                "SELECT * FROM mirror_metadata WHERE namespace=%s ORDER BY namespace,key",
                (namespace,),
            )
        return [
            MetadataRecord(
                namespace=row["namespace"],
                key=row["key"],
                payload=decode_metadata_value(row["payload"]),
                created_at=_dt(row["created_at"]) or _utcnow(),
            )
            for row in rows
        ]

    def close(self) -> None:
        self._db.close()


class PostgresLeaseManager(LeaseManager):
    """PostgreSQL lease manager used as the authoritative lease record."""

    def __init__(self, dsn: str, *, ttl_seconds: int = 60) -> None:
        self._db = _PostgresConnection(dsn)
        self.ttl_seconds = ttl_seconds

    def acquire(
        self, job_id: UUID, worker_id: str, ttl_seconds: int = 60
    ) -> WorkerLease:
        expires = _utcnow() + timedelta(seconds=ttl_seconds or self.ttl_seconds)
        rows = self._db.execute(
            """
            INSERT INTO mirror_leases(job_id,worker_id,expires_at)
            VALUES (%s,%s,%s)
            ON CONFLICT(job_id) DO UPDATE SET worker_id=EXCLUDED.worker_id, expires_at=EXCLUDED.expires_at
            WHERE mirror_leases.expires_at <= %s OR mirror_leases.worker_id = EXCLUDED.worker_id
            RETURNING job_id,worker_id,expires_at
            """,
            (str(job_id), worker_id, expires, _utcnow()),
        )
        if not rows:
            raise RuntimeError(
                f"Lease for {job_id} is currently owned by another live worker"
            )
        return _lease_from_row(rows[0])

    def renew(self, lease: WorkerLease, ttl_seconds: int = 60) -> WorkerLease:
        expires = _utcnow() + timedelta(seconds=ttl_seconds or self.ttl_seconds)
        rows = self._db.execute(
            "UPDATE mirror_leases SET expires_at=%s WHERE job_id=%s AND worker_id=%s RETURNING job_id,worker_id,expires_at",
            (expires, str(lease.job_id), lease.worker_id),
        )
        if not rows:
            raise RuntimeError(
                f"Lease for {lease.job_id} is no longer owned by {lease.worker_id}"
            )
        return _lease_from_row(rows[0])

    def release(self, lease: WorkerLease) -> None:
        self._db.execute(
            "DELETE FROM mirror_leases WHERE job_id=%s AND worker_id=%s",
            (str(lease.job_id), lease.worker_id),
        )

    def get(self, job_id: UUID) -> WorkerLease | None:
        rows = self._db.execute(
            "SELECT job_id,worker_id,expires_at FROM mirror_leases WHERE job_id=%s",
            (str(job_id),),
        )
        return None if not rows else _lease_from_row(rows[0])

    def list(self) -> list[WorkerLease]:
        return [
            _lease_from_row(row)
            for row in self._db.execute(
                "SELECT job_id,worker_id,expires_at FROM mirror_leases ORDER BY expires_at,job_id"
            )
        ]

    def close(self) -> None:
        self._db.close()


def _job_from_row(row: dict[str, Any]) -> WorkerJob:
    return WorkerJob(
        job_id=UUID(str(row["job_id"])),
        kind=row["kind"],
        run_id=UUID(str(row["run_id"])) if row["run_id"] else None,
        pipeline_id=row["pipeline_id"],
        step_id=row["step_id"],
        execution_class=row["execution_class"],
        payload=decode_metadata_value(row["payload"]),
        state=JobState(row["state"]),
        worker_id=row["worker_id"],
        error=row["error"],
        metadata=decode_metadata_value(row["metadata"]),
        submitted_at=_dt(row["submitted_at"]) or _utcnow(),
        claimed_at=_dt(row["claimed_at"]),
        completed_at=_dt(row["completed_at"]),
        cancelled_at=_dt(row["cancelled_at"]),
        lease_expires_at=_dt(row["lease_expires_at"]),
    )


def _execution_from_row(row: dict[str, Any]) -> ExecutionRecord:
    return ExecutionRecord(
        run_id=UUID(str(row["run_id"])),
        outcome=row["outcome"],
        payload=decode_metadata_value(row["payload"]),
        worker_id=row["worker_id"],
        created_at=_dt(row["created_at"]) or _utcnow(),
        started_at=_dt(row["started_at"]),
        completed_at=_dt(row["completed_at"]),
        metadata=decode_metadata_value(row["metadata"]),
    )


def _dead_letter_from_row(row: dict[str, Any]) -> DeadLetterRecord:
    return DeadLetterRecord(
        run_id=UUID(str(row["run_id"])),
        pipeline_id=row["pipeline_id"],
        step_id=row["step_id"],
        reason=row["reason"],
        original_inputs=decode_metadata_value(row["original_inputs"]),
        policy_state=decode_metadata_value(row["policy_state"]),
        provenance=decode_metadata_value(row["provenance"]),
        retry_count=row["retry_count"],
        terminal_status=row["terminal_status"],
        worker_id=row["worker_id"],
        lease_id=row["lease_id"],
        created_at=_dt(row["created_at"]) or _utcnow(),
    )


def _lease_from_row(row: dict[str, Any]) -> WorkerLease:
    return WorkerLease(
        job_id=UUID(str(row["job_id"])),
        worker_id=row["worker_id"],
        expires_at=_dt(row["expires_at"]) or _utcnow(),
    )
