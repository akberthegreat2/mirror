"""SQLite-backed dead-letter queue and checkpoint store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from mirror_core.metadata import decode_metadata_value, encode_metadata_value
from mirror_core.workers._util import _parse_datetime, _utcnow
from mirror_core.workers.models import DeadLetterRecord


class SQLiteDeadLetterQueue:
    """SQLite-backed terminal failure queue for durable local workflows."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def record(self, record: DeadLetterRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO dead_letters(
                run_id, pipeline_id, step_id, reason, original_inputs,
                policy_state, provenance, retry_count, terminal_status, worker_id,
                lease_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                pipeline_id = excluded.pipeline_id,
                step_id = excluded.step_id,
                reason = excluded.reason,
                original_inputs = excluded.original_inputs,
                policy_state = excluded.policy_state,
                provenance = excluded.provenance,
                retry_count = excluded.retry_count,
                terminal_status = excluded.terminal_status,
                worker_id = excluded.worker_id,
                lease_id = excluded.lease_id,
                created_at = excluded.created_at
            """,
            (
                str(record.run_id),
                record.pipeline_id,
                record.step_id,
                record.reason,
                json.dumps(record.original_inputs, sort_keys=True),
                json.dumps(record.policy_state, sort_keys=True),
                json.dumps(record.provenance, sort_keys=True),
                record.retry_count,
                record.terminal_status,
                record.worker_id,
                record.lease_id,
                record.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, run_id: UUID) -> DeadLetterRecord | None:
        row = self._conn.execute(
            "SELECT * FROM dead_letters WHERE run_id = ?", (str(run_id),)
        ).fetchone()
        return None if row is None else self._row_to_record(row)

    def list(self) -> list[DeadLetterRecord]:
        rows = self._conn.execute(
            "SELECT * FROM dead_letters ORDER BY created_at DESC, run_id DESC"
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def replay(self, run_id: UUID) -> DeadLetterRecord | None:
        record = self.get(run_id)
        if record is None:
            return None
        self._conn.execute("DELETE FROM dead_letters WHERE run_id = ?", (str(run_id),))
        self._conn.commit()
        return record

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dead_letters (
                run_id TEXT PRIMARY KEY,
                pipeline_id TEXT NOT NULL,
                step_id TEXT,
                reason TEXT NOT NULL,
                original_inputs TEXT NOT NULL,
                policy_state TEXT NOT NULL,
                provenance TEXT NOT NULL,
                retry_count INTEGER NOT NULL,
                terminal_status TEXT NOT NULL,
                worker_id TEXT,
                lease_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> DeadLetterRecord:
        return DeadLetterRecord(
            run_id=UUID(row["run_id"]),
            pipeline_id=row["pipeline_id"],
            step_id=row["step_id"],
            reason=row["reason"],
            original_inputs=json.loads(row["original_inputs"]),
            policy_state=json.loads(row["policy_state"]),
            provenance=json.loads(row["provenance"]),
            retry_count=row["retry_count"],
            terminal_status=row["terminal_status"],
            worker_id=row["worker_id"],
            lease_id=row["lease_id"],
            created_at=_parse_datetime(row["created_at"]),
        )


class SQLiteCheckpointStore:
    """SQLite-backed checkpoint store for durable resumable workflows."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def save(self, run_id: UUID, step_id: str, payload: Mapping[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO checkpoints(run_id, step_id, payload, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id, step_id)
            DO UPDATE SET payload = excluded.payload,
                          created_at = excluded.created_at
            """,
            (
                str(run_id),
                step_id,
                json.dumps(encode_metadata_value(payload), sort_keys=True),
                _utcnow().isoformat(),
            ),
        )
        self._conn.commit()

    def load(self, run_id: UUID, step_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload FROM checkpoints WHERE run_id = ? AND step_id = ?",
            (str(run_id), step_id),
        ).fetchone()
        if row is None:
            return None
        return cast(dict[str, Any], decode_metadata_value(json.loads(row["payload"])))

    def latest(self, run_id: UUID) -> tuple[str, dict[str, Any]] | None:
        row = self._conn.execute(
            """
            SELECT step_id, payload
            FROM checkpoints
            WHERE run_id = ?
            ORDER BY created_at DESC, step_id DESC
            LIMIT 1
            """,
            (str(run_id),),
        ).fetchone()
        if row is None:
            return None
        return row["step_id"], cast(
            dict[str, Any], decode_metadata_value(json.loads(row["payload"]))
        )

    def delete(self, run_id: UUID, step_id: str) -> None:
        self._conn.execute(
            "DELETE FROM checkpoints WHERE run_id = ? AND step_id = ?",
            (str(run_id), step_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(run_id, step_id)
            )
            """
        )
        self._conn.commit()

