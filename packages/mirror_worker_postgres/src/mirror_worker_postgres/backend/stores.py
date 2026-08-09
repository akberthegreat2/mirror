from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from mirror_core.metadata import decode_metadata_value, encode_metadata_value
from mirror_core.workers import (
    ArtifactStore,
    CheckpointStore,
    DeadLetterQueue,
    DeadLetterRecord,
    ExecutionRecord,
    ExecutionStore,
)

from mirror_worker_postgres.backend.connection import _PostgresConnection, _utcnow
from mirror_worker_postgres.backend.metadata_store import (
    _dead_letter_from_row,
    _execution_from_row,
)


class PostgresExecutionStore(ExecutionStore):
    """PostgreSQL execution history store."""

    def __init__(self, dsn: str) -> None:
        self._db = _PostgresConnection(dsn)

    def record(self, record: ExecutionRecord) -> None:
        self._db.execute(
            """
            INSERT INTO mirror_execution_runs(run_id,outcome,payload,worker_id,created_at,started_at,completed_at,metadata)
            VALUES (%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT(run_id) DO UPDATE SET outcome=EXCLUDED.outcome,payload=EXCLUDED.payload,
              worker_id=EXCLUDED.worker_id,started_at=EXCLUDED.started_at,completed_at=EXCLUDED.completed_at,metadata=EXCLUDED.metadata
            """,
            (
                str(record.run_id),
                record.outcome,
                json.dumps(encode_metadata_value(record.payload)),
                record.worker_id,
                record.created_at,
                record.started_at,
                record.completed_at,
                json.dumps(encode_metadata_value(record.metadata)),
            ),
        )

    def get(self, run_id: UUID) -> ExecutionRecord | None:
        rows = self._db.execute(
            "SELECT * FROM mirror_execution_runs WHERE run_id=%s", (str(run_id),)
        )
        return None if not rows else _execution_from_row(rows[0])

    def list(self) -> list[ExecutionRecord]:
        return [
            _execution_from_row(row)
            for row in self._db.execute(
                "SELECT * FROM mirror_execution_runs ORDER BY created_at, run_id"
            )
        ]

    def close(self) -> None:
        self._db.close()


class PostgresCheckpointStore(CheckpointStore):
    """PostgreSQL checkpoint store using JSONB snapshots."""

    def __init__(self, dsn: str) -> None:
        self._db = _PostgresConnection(dsn)

    def save(self, run_id: UUID, step_id: str, payload: Mapping[str, Any]) -> None:
        self._db.execute(
            "INSERT INTO mirror_checkpoints(run_id,step_id,payload,created_at) VALUES (%s,%s,%s::jsonb,%s) ON CONFLICT(run_id,step_id) DO UPDATE SET payload=EXCLUDED.payload,created_at=EXCLUDED.created_at",
            (
                str(run_id),
                step_id,
                json.dumps(encode_metadata_value(payload)),
                _utcnow(),
            ),
        )

    def load(self, run_id: UUID, step_id: str) -> dict[str, Any] | None:
        rows = self._db.execute(
            "SELECT payload FROM mirror_checkpoints WHERE run_id=%s AND step_id=%s",
            (str(run_id), step_id),
        )
        return None if not rows else decode_metadata_value(rows[0]["payload"])

    def latest(self, run_id: UUID) -> tuple[str, dict[str, Any]] | None:
        rows = self._db.execute(
            "SELECT step_id,payload FROM mirror_checkpoints WHERE run_id=%s ORDER BY created_at DESC LIMIT 1",
            (str(run_id),),
        )
        return (
            None
            if not rows
            else (rows[0]["step_id"], decode_metadata_value(rows[0]["payload"]))
        )

    def delete(self, run_id: UUID, step_id: str) -> None:
        self._db.execute(
            "DELETE FROM mirror_checkpoints WHERE run_id=%s AND step_id=%s",
            (str(run_id), step_id),
        )

    def close(self) -> None:
        self._db.close()


class PostgresArtifactStore(ArtifactStore):
    """PostgreSQL bytea artifact store for small durable artifacts."""

    def __init__(self, dsn: str) -> None:
        self._db = _PostgresConnection(dsn)

    def put_bytes(self, key: str, payload: bytes) -> None:
        self._db.execute(
            "INSERT INTO mirror_artifacts(key,payload,created_at) VALUES (%s,%s,%s) ON CONFLICT(key) DO UPDATE SET payload=EXCLUDED.payload",
            (key, payload, _utcnow()),
        )

    def get_bytes(self, key: str) -> bytes | None:
        rows = self._db.execute(
            "SELECT payload FROM mirror_artifacts WHERE key=%s", (key,)
        )
        return None if not rows else bytes(rows[0]["payload"])

    def delete(self, key: str) -> None:
        self._db.execute("DELETE FROM mirror_artifacts WHERE key=%s", (key,))

    def close(self) -> None:
        self._db.close()


class PostgresDeadLetterQueue(DeadLetterQueue):
    """Durable logical dead-letter store."""

    def __init__(self, dsn: str) -> None:
        self._db = _PostgresConnection(dsn)

    def record(self, record: DeadLetterRecord) -> None:
        self._db.execute(
            """
            INSERT INTO mirror_dead_letters(run_id,pipeline_id,step_id,reason,original_inputs,policy_state,provenance,retry_count,terminal_status,worker_id,lease_id,created_at)
            VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
            ON CONFLICT(run_id) DO UPDATE SET reason=EXCLUDED.reason,policy_state=EXCLUDED.policy_state,provenance=EXCLUDED.provenance,retry_count=EXCLUDED.retry_count,terminal_status=EXCLUDED.terminal_status,worker_id=EXCLUDED.worker_id,lease_id=EXCLUDED.lease_id
            """,
            (
                str(record.run_id),
                record.pipeline_id,
                record.step_id,
                record.reason,
                json.dumps(encode_metadata_value(record.original_inputs)),
                json.dumps(encode_metadata_value(record.policy_state)),
                json.dumps(encode_metadata_value(record.provenance)),
                record.retry_count,
                record.terminal_status,
                record.worker_id,
                record.lease_id,
                record.created_at,
            ),
        )

    def get(self, run_id: UUID) -> DeadLetterRecord | None:
        rows = self._db.execute(
            "SELECT * FROM mirror_dead_letters WHERE run_id=%s", (str(run_id),)
        )
        return None if not rows else _dead_letter_from_row(rows[0])

    def replay(self, run_id: UUID) -> DeadLetterRecord | None:
        return self.get(run_id)

    def list(self) -> list[DeadLetterRecord]:
        return [
            _dead_letter_from_row(row)
            for row in self._db.execute(
                "SELECT * FROM mirror_dead_letters ORDER BY created_at, run_id"
            )
        ]

    def close(self) -> None:
        self._db.close()
