"""Metadata contracts and durable stores for Mirror Core.

ADR-0030 makes metadata a first-class core concern separate from blob storage.
The contracts in this module are intentionally narrow: structured operational
records go here, while large binary payloads stay in :mod:`mirror_core.storage`.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

_REGISTERED_METADATA_ENUMS: dict[str, type[Enum]] = {}


def register_metadata_enum(enum_type: type[Enum]) -> type[Enum]:
    """Register an enum for safe durable metadata rehydration.

    Metadata decoding never imports an arbitrary module named by persisted
    data. Applications that need enum identity after a fresh process starts
    should register the enum during trusted application initialization.
    Already-loaded enum modules are also supported for compatibility.
    """
    if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
        raise TypeError("enum_type must be an Enum subclass")
    key = f"{enum_type.__module__}:{enum_type.__qualname__}"
    _REGISTERED_METADATA_ENUMS[key] = enum_type
    return enum_type


class MetadataNamespaces:
    """Canonical namespaces for operational metadata records."""

    PIPELINE_VERSIONS = "pipeline.versions"
    EXECUTION_RUNS = "execution.runs"
    STEP_RUNS = "execution.steps"
    RETRIES = "execution.retries"
    TERMINAL_OUTCOMES = "execution.terminals"
    SCHEDULER_STATE = "scheduler.state"
    WORKER_STATE = "workers.state"
    WORKER_LEASES = "workers.leases"
    LINEAGE = "lineage"
    PROVENANCE = "provenance"
    POLICY_SNAPSHOTS = "policy.snapshots"
    REPLAY_POINTERS = "replay.pointers"
    AUDIT_EVENTS = "audit.events"


class MetadataRecord(BaseModel):
    """Immutable structured metadata stored by the core metadata layer."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    namespace: str = Field(min_length=1)
    key: str = Field(min_length=1)
    payload: Mapping[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any, /) -> None:
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))

    @field_serializer("payload")
    def _serialize_payload(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)

    @classmethod
    def pipeline_version(
        cls,
        pipeline_id: str,
        version: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a pipeline-version record."""
        return cls(
            namespace=MetadataNamespaces.PIPELINE_VERSIONS,
            key=f"{pipeline_id}:{version}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def execution_run(
        cls,
        run_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create an execution-run record."""
        return cls(
            namespace=MetadataNamespaces.EXECUTION_RUNS,
            key=str(run_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def step_run(
        cls,
        run_id: str | UUID,
        step_id: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a step-run record."""
        return cls(
            namespace=MetadataNamespaces.STEP_RUNS,
            key=f"{run_id}:{step_id}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def retry(
        cls,
        run_id: str | UUID,
        step_id: str,
        attempt: int,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a retry record."""
        return cls(
            namespace=MetadataNamespaces.RETRIES,
            key=f"{run_id}:{step_id}:{attempt}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def terminal_outcome(
        cls,
        run_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a terminal-outcome record."""
        return cls(
            namespace=MetadataNamespaces.TERMINAL_OUTCOMES,
            key=str(run_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def scheduler(
        cls,
        schedule_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a scheduler-bookkeeping record."""
        return cls(
            namespace=MetadataNamespaces.SCHEDULER_STATE,
            key=str(schedule_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def worker(
        cls,
        worker_id: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a worker state record."""
        return cls(
            namespace=MetadataNamespaces.WORKER_STATE,
            key=worker_id,
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def worker_lease(
        cls,
        run_id: str | UUID,
        worker_id: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a worker-lease record."""
        return cls(
            namespace=MetadataNamespaces.WORKER_LEASES,
            key=f"{run_id}:{worker_id}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def lineage(
        cls,
        subject_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a lineage record."""
        return cls(
            namespace=MetadataNamespaces.LINEAGE,
            key=str(subject_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def provenance(
        cls,
        subject_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a provenance record."""
        return cls(
            namespace=MetadataNamespaces.PROVENANCE,
            key=str(subject_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def policy_snapshot(
        cls,
        run_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a policy-resolution snapshot record."""
        return cls(
            namespace=MetadataNamespaces.POLICY_SNAPSHOTS,
            key=str(run_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def replay_pointer(
        cls,
        run_id: str | UUID,
        pointer: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a replay/resume pointer record."""
        return cls(
            namespace=MetadataNamespaces.REPLAY_POINTERS,
            key=f"{run_id}:{pointer}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def audit_event(
        cls,
        subject_id: str | UUID,
        event: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create an audit-event record."""
        return cls(
            namespace=MetadataNamespaces.AUDIT_EVENTS,
            key=f"{subject_id}:{event}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )


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


def _freeze_mapping(value: Mapping[str, Any]) -> MappingProxyType[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze_value(item) for item in value), key=repr))
    return value


_METADATA_TAG = "__mirror_metadata_type__"
_METADATA_VALUE = "value"
_METADATA_ENUM = "enum"


def _encode_metadata_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _encode_metadata_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_metadata_value(item) for item in value]
    if isinstance(value, tuple):
        return [_encode_metadata_value(item) for item in value]
    if isinstance(value, set):
        return [_encode_metadata_value(item) for item in sorted(value, key=repr)]
    if isinstance(value, datetime):
        return {
            _METADATA_TAG: "datetime",
            _METADATA_VALUE: value.isoformat(),
        }
    if isinstance(value, UUID):
        return {
            _METADATA_TAG: "uuid",
            _METADATA_VALUE: str(value),
        }
    if isinstance(value, Path):
        return {
            _METADATA_TAG: "path",
            _METADATA_VALUE: str(value),
        }
    if isinstance(value, Enum):
        return {
            _METADATA_TAG: "enum",
            _METADATA_ENUM: f"{value.__class__.__module__}:{value.__class__.__qualname__}",
            _METADATA_VALUE: value.value,
        }
    if isinstance(value, BaseModel):
        return _encode_metadata_value(value.model_dump(mode="json"))
    return value


def _decode_metadata_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_metadata_value(item) for item in value]
    if isinstance(value, dict):
        marker = value.get(_METADATA_TAG)
        if marker == "datetime" and _METADATA_VALUE in value:
            return _parse_datetime(value[_METADATA_VALUE])
        if marker == "uuid" and _METADATA_VALUE in value:
            return UUID(value[_METADATA_VALUE])
        if marker == "path" and _METADATA_VALUE in value:
            return Path(value[_METADATA_VALUE])
        if marker == "enum" and _METADATA_VALUE in value and _METADATA_ENUM in value:
            enum_reference = value[_METADATA_ENUM]
            enum_type = _REGISTERED_METADATA_ENUMS.get(enum_reference)
            if enum_type is None:
                module_name, _, class_name = enum_reference.rpartition(":")
                module = sys.modules.get(module_name)
                if module is not None:
                    candidate: Any = module
                    try:
                        for part in class_name.split("."):
                            candidate = getattr(candidate, part)
                    except AttributeError:
                        candidate = None
                    if isinstance(candidate, type) and issubclass(candidate, Enum):
                        enum_type = candidate
            if enum_type is not None:
                try:
                    return enum_type(value[_METADATA_VALUE])
                except ValueError:
                    return value[_METADATA_VALUE]
            return value[_METADATA_VALUE]
        return {key: _decode_metadata_value(item) for key, item in value.items()}
    return value


def encode_metadata_value(value: Any) -> Any:
    """Encode a metadata value into JSON-compatible durable data."""
    return _encode_metadata_value(value)


def decode_metadata_value(value: Any) -> Any:
    """Decode durable metadata data back into Python values."""
    return _decode_metadata_value(value)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = [
    "InMemoryMetadataStore",
    "MetadataNamespaces",
    "MetadataRecord",
    "MetadataStore",
    "SQLiteMetadataStore",
    "decode_metadata_value",
    "encode_metadata_value",
    "register_metadata_enum",
]
