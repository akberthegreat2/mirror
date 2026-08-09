"""Durable and in-memory metadata stores for Mirror Core."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

from mirror_core.metadata.encoding import (
    _decode_metadata_value,
    _encode_metadata_value,
    _parse_datetime,
)
from mirror_core.metadata.models import MetadataRecord


@runtime_checkable
class MetadataStore(Protocol):
    """Persistence contract for structured operational metadata records."""

    def put(self, record: MetadataRecord) -> None: ...

    def get(self, namespace: str, key: str) -> MetadataRecord | None: ...

    def list(self, namespace: str | None = None) -> list[MetadataRecord]: ...


class InMemoryMetadataStore:
    """In-memory metadata store for tests and local development."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], MetadataRecord] = {}

    def put(self, record: MetadataRecord) -> None:
        self._records[(record.namespace, record.key)] = record

    def get(self, namespace: str, key: str) -> MetadataRecord | None:
        return self._records.get((namespace, key))

    def list(self, namespace: str | None = None) -> list[MetadataRecord]:
        records = list(self._records.values())
        if namespace is not None:
            records = [record for record in records if record.namespace == namespace]
        return sorted(records, key=lambda record: (record.namespace, record.key))


class SQLiteMetadataStore:
    """SQLite-backed metadata store for durable local workflows."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def put(self, record: MetadataRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO metadata(namespace, key, payload, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(namespace, key)
            DO UPDATE SET payload = excluded.payload,
                          created_at = excluded.created_at
            """,
            (
                record.namespace,
                record.key,
                json.dumps(_encode_metadata_value(record.payload), sort_keys=True),
                record.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, namespace: str, key: str) -> MetadataRecord | None:
        row = self._conn.execute(
            "SELECT namespace, key, payload, created_at FROM metadata WHERE namespace = ? AND key = ?",
            (namespace, key),
        ).fetchone()
        if row is None:
            return None
        return MetadataRecord(
            namespace=row["namespace"],
            key=row["key"],
            payload=_decode_metadata_value(json.loads(row["payload"])),
            created_at=_parse_datetime(row["created_at"]),
        )

    def list(self, namespace: str | None = None) -> list[MetadataRecord]:
        if namespace is None:
            rows = self._conn.execute(
                "SELECT namespace, key, payload, created_at FROM metadata ORDER BY namespace, key"
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT namespace, key, payload, created_at
                FROM metadata
                WHERE namespace = ?
                ORDER BY namespace, key
                """,
                (namespace,),
            ).fetchall()
        return [
            MetadataRecord(
                namespace=row["namespace"],
                key=row["key"],
                payload=_decode_metadata_value(json.loads(row["payload"])),
                created_at=_parse_datetime(row["created_at"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(namespace, key)
            )
            """
        )
        self._conn.commit()
