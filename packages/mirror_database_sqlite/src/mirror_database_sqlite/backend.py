"""SQLite database backend implementing the Mirror DatabaseBackend contract."""

from __future__ import annotations

import enum
import json
import pkgutil
import sqlite3
import types
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin
from uuid import UUID, uuid4

import aiosqlite
from mirror_database.models import (
    ENTITY_MODEL_MAP,
    ArchiveRecord,
    BaseEntity,
    Checkpoint,
    CrawledURL,
    DeadLetter,
    DeadLetterTerminalStatus,
    DefinitionFormat,
    EntityType,
    ExecutionRun,
    ExecutionStatus,
    ExecutionStep,
    Pipeline,
    PipelineVersion,
    Project,
    Schedule,
    ScheduleStatus,
    Worker,
    WorkerStatus,
)
from mirror_database.protocol import DatabaseBackend, T, TransactionContext

_schema_data = pkgutil.get_data("mirror_database_sqlite", "schema.sql")
if _schema_data is None:  # pragma: no cover
    raise RuntimeError("mirror_database_sqlite.schema.sql missing from package")
_SCHEMA = _schema_data.decode()

_TABLES: dict[EntityType, str] = {
    "project": "projects",
    "pipeline": "pipelines",
    "pipeline_version": "pipeline_versions",
    "execution_run": "execution_runs",
    "execution_step": "execution_steps",
    "worker": "workers",
    "schedule": "schedules",
    "crawled_url": "crawled_urls",
    "archive_record": "archive_records",
    "checkpoint": "checkpoints",
    "dead_letter": "dead_letters",
}

_MODEL_TO_ENTITY: dict[type[BaseEntity], EntityType] = {model: entity_type for entity_type, model in ENTITY_MODEL_MAP.items()}


class NotFoundError(LookupError):
    """Raised when an operational transition targets a missing entity."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_sqlite_dsn(dsn: str) -> str:
    """Extract the SQLite path from a ``sqlite:///path`` DSN or a raw path."""
    for prefix in ("sqlite:///", "sqlite://"):
        if dsn.startswith(prefix):
            return dsn[len(prefix) :]
    return dsn


def _is_dict_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is dict:
        return True
    if origin is Union:
        return any(_is_dict_annotation(a) for a in get_args(annotation))
    return False


def _coerce_value(value: Any, annotation: Any) -> Any:
    """Coerce a raw SQLite scalar back to the model field type."""
    if value is None:
        return None
    origin = get_origin(annotation)
    if origin is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return _coerce_value(value, non_none[0])
        return value
    if annotation is UUID:
        return UUID(str(value))
    if annotation is datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation(value)
    return value


def _model_to_row(entity: BaseEntity) -> dict[str, Any]:
    """Serialize a model to a flat dict of SQLite-safe column values."""
    data = entity.model_dump(mode="python")
    row: dict[str, Any] = {}
    for key, value in data.items():
        annotation = type(entity).model_fields[key].annotation
        if _is_dict_annotation(annotation):
            row[key] = json.dumps(value)
        elif isinstance(value, UUID):
            row[key] = str(value)
        elif isinstance(value, datetime):
            row[key] = value.isoformat()
        elif isinstance(value, enum.Enum):
            row[key] = value.value
        else:
            row[key] = value
    return row


def _row_to_model(model_cls: type[T], row: Mapping[str, Any]) -> T:
    row_dict = dict(row)
    data: dict[str, Any] = {}
    for key, field in model_cls.model_fields.items():
        if key not in row_dict:
            continue
        value = row_dict[key]
        if value is None:
            data[key] = None
            continue
        if _is_dict_annotation(field.annotation):
            data[key] = json.loads(value)
        else:
            data[key] = _coerce_value(value, field.annotation)
    return model_cls.model_validate(data)


def _filter_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class _SQLiteTransaction(TransactionContext):
    """Explicit BEGIN/COMMIT transaction on the shared SQLite connection."""

    def __init__(self, backend: SQLiteBackend) -> None:
        self._backend = backend
        self._closed = False

    async def __aenter__(self) -> TransactionContext:
        await self._backend._execute("BEGIN")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        if not self._closed:
            await self._backend._execute("COMMIT")
            self._closed = True

    async def rollback(self) -> None:
        if not self._closed:
            await self._backend._execute("ROLLBACK")
            self._closed = True


class SQLiteBackend(DatabaseBackend):
    """A SQLite implementation of the Mirror database contract.

    The backend owns its schema; no ORM is involved. All control-plane entity
    tables live in a single SQLite database file (or in-memory with ``:memory:``).
    """

    def __init__(self, dsn: str = "sqlite:///mirror.db") -> None:
        path = _parse_sqlite_dsn(dsn)
        self._path = path if path else "mirror.db"
        self._db: aiosqlite.Connection | None = None

    @property
    def database_path(self) -> str:
        """Return the resolved database file path (or ':memory:')."""
        return self._path

    async def initialize(self) -> None:
        if self._path != ":memory:":
            parent = Path(self._path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._path, isolation_level=None)
        self._db.row_factory = aiosqlite.Row
        await self._execute("PRAGMA journal_mode = WAL")
        await self._execute("PRAGMA synchronous = NORMAL")
        await self._execute("PRAGMA foreign_keys = ON")
        await self._execute("PRAGMA busy_timeout = 5000")
        await self._db.executescript(_SCHEMA)

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def _execute(self, sql: str, params: Sequence[Any] = ()) -> aiosqlite.Cursor:
        if self._db is None:
            raise RuntimeError("SQLiteBackend not initialized")
        cur = await self._db.execute(sql, tuple(params))
        return cur

    async def _fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        if self._db is None:
            raise RuntimeError("SQLiteBackend not initialized")
        cur = await self._db.execute(sql, tuple(params))
        row = await cur.fetchone()
        return dict(row) if row is not None else None

    async def _fetch_all(self, sql: str, params: Sequence[Any] = ()) -> Sequence[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("SQLiteBackend not initialized")
        cur = await self._db.execute(sql, tuple(params))
        return [dict(row) for row in await cur.fetchall()]

    def _resolve(self, entity_type: EntityType) -> tuple[type[BaseEntity], str]:
        return ENTITY_MODEL_MAP[entity_type], _TABLES[entity_type]

    # ------------------------------------------------------------------ CRUD

    async def create(self, entity: T) -> T:
        model_cls = type(entity)
        entity_type = _MODEL_TO_ENTITY[model_cls]
        table = _TABLES[entity_type]
        row = _model_to_row(entity)
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        await self._execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", list(row.values()))
        return entity

    async def get(self, entity_type: EntityType, entity_id: UUID) -> BaseEntity | None:
        model_cls = ENTITY_MODEL_MAP[entity_type]
        table = _TABLES[entity_type]
        row = await self._fetch_one(f"SELECT * FROM {table} WHERE id = ?", (str(entity_id),))
        if row is None:
            return None
        return _row_to_model(model_cls, row)

    async def update(self, entity: T) -> T:
        model_cls = type(entity)
        entity_type = _MODEL_TO_ENTITY[model_cls]
        table = _TABLES[entity_type]
        row = _model_to_row(entity)
        set_clause = ", ".join(f"{col} = ?" for col in row)
        await self._execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", [*row.values(), str(entity.id)])
        return entity

    async def delete(self, entity_type: EntityType, entity_id: UUID) -> bool:
        _, table = self._resolve(entity_type)
        cur = await self._execute(f"DELETE FROM {table} WHERE id = ?", (str(entity_id),))
        return cur.rowcount > 0

    async def list(
        self,
        entity_type: EntityType,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: Mapping[str, Any] | None = None,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> Sequence[BaseEntity]:
        model_cls = ENTITY_MODEL_MAP[entity_type]
        table = _TABLES[entity_type]
        where, params = self._build_filters(filters)
        order = f" ORDER BY {order_by}" if order_by else ""
        if order_by and order_desc:
            order += " DESC"
        rows = await self._fetch_all(
            f"SELECT * FROM {table}{where}{order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [_row_to_model(model_cls, row) for row in rows]

    async def count(self, entity_type: EntityType, filters: Mapping[str, Any] | None = None) -> int:
        _, table = self._resolve(entity_type)
        where, params = self._build_filters(filters)
        row = await self._fetch_one(f"SELECT COUNT(*) AS n FROM {table}{where}", params)
        if row is None:
            return 0
        return int(row["n"])

    def _build_filters(self, filters: Mapping[str, Any] | None) -> tuple[str, Sequence[Any]]:
        if not filters:
            return "", []
        conds = [f"{key} = ?" for key in filters]
        params = [_filter_value(value) for value in filters.values()]
        return " WHERE " + " AND ".join(conds), params

    # ------------------------------------------------- entity-specific helpers

    async def get_project_by_slug(self, slug: str) -> Project | None:
        row = await self._fetch_one("SELECT * FROM projects WHERE slug = ?", (slug,))
        if row is None:
            return None
        return _row_to_model(Project, row)

    async def get_pipeline_by_slug(self, project_id: UUID, slug: str) -> Pipeline | None:
        row = await self._fetch_one(
            "SELECT * FROM pipelines WHERE project_id = ? AND slug = ?",
            (str(project_id), slug),
        )
        if row is None:
            return None
        return _row_to_model(Pipeline, row)

    async def get_latest_pipeline_version(self, pipeline_id: UUID) -> PipelineVersion | None:
        row = await self._fetch_one(
            "SELECT * FROM pipeline_versions WHERE pipeline_id = ? ORDER BY version DESC LIMIT 1",
            (str(pipeline_id),),
        )
        if row is None:
            return None
        return _row_to_model(PipelineVersion, row)

    async def get_pipeline_version(self, pipeline_id: UUID, version: int) -> PipelineVersion | None:
        row = await self._fetch_one(
            "SELECT * FROM pipeline_versions WHERE pipeline_id = ? AND version = ?",
            (str(pipeline_id), version),
        )
        if row is None:
            return None
        return _row_to_model(PipelineVersion, row)

    async def list_pipeline_versions(self, pipeline_id: UUID) -> Sequence[PipelineVersion]:
        rows = await self._fetch_all(
            "SELECT * FROM pipeline_versions WHERE pipeline_id = ? ORDER BY version",
            (str(pipeline_id),),
        )
        return [_row_to_model(PipelineVersion, row) for row in rows]

    async def get_execution_run(self, run_id: UUID) -> ExecutionRun | None:
        row = await self._fetch_one("SELECT * FROM execution_runs WHERE run_id = ?", (str(run_id),))
        if row is None:
            return None
        return _row_to_model(ExecutionRun, row)

    async def list_execution_runs(
        self,
        pipeline_id: UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExecutionRun]:
        conds: list[str] = []
        params: list[Any] = []
        if pipeline_id is not None:
            conds.append("pipeline_id = ?")
            params.append(str(pipeline_id))
        if status is not None:
            conds.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conds) if conds else ""
        rows = await self._fetch_all(
            f"SELECT * FROM execution_runs{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [_row_to_model(ExecutionRun, row) for row in rows]

    async def get_execution_steps(self, run_id: UUID) -> Sequence[ExecutionStep]:
        rows = await self._fetch_all("SELECT * FROM execution_steps WHERE run_id = ? ORDER BY created_at", (str(run_id),))
        return [_row_to_model(ExecutionStep, row) for row in rows]

    async def get_worker(self, worker_id: UUID) -> Worker | None:
        row = await self._fetch_one("SELECT * FROM workers WHERE worker_id = ?", (str(worker_id),))
        if row is None:
            return None
        return _row_to_model(Worker, row)

    async def list_workers(self, execution_class: str | None = None, status: str | None = None) -> Sequence[Worker]:
        conds: list[str] = []
        params: list[Any] = []
        if execution_class is not None:
            conds.append("execution_class = ?")
            params.append(execution_class)
        if status is not None:
            conds.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conds) if conds else ""
        rows = await self._fetch_all(f"SELECT * FROM workers{where} ORDER BY created_at", params)
        return [_row_to_model(Worker, row) for row in rows]

    async def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        row = await self._fetch_one("SELECT * FROM schedules WHERE id = ?", (str(schedule_id),))
        if row is None:
            return None
        return _row_to_model(Schedule, row)

    async def list_schedules(
        self,
        pipeline_id: UUID | None = None,
        status: str | None = None,
        enabled: bool | None = None,
    ) -> Sequence[Schedule]:
        conds: list[str] = []
        params: list[Any] = []
        if pipeline_id is not None:
            conds.append("pipeline_id = ?")
            params.append(str(pipeline_id))
        if status is not None:
            conds.append("status = ?")
            params.append(status)
        if enabled is not None:
            conds.append("enabled = ?")
            params.append(1 if enabled else 0)
        where = " WHERE " + " AND ".join(conds) if conds else ""
        rows = await self._fetch_all(f"SELECT * FROM schedules{where} ORDER BY created_at", params)
        return [_row_to_model(Schedule, row) for row in rows]

    async def get_crawled_urls(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CrawledURL]:
        conds: list[str] = []
        params: list[Any] = []
        if pipeline_id is not None:
            conds.append("pipeline_id = ?")
            params.append(str(pipeline_id))
        if run_id is not None:
            conds.append("run_id = ?")
            params.append(str(run_id))
        if status is not None:
            conds.append("status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(conds) if conds else ""
        rows = await self._fetch_all(
            f"SELECT * FROM crawled_urls{where} ORDER BY discovered_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [_row_to_model(CrawledURL, row) for row in rows]

    async def get_archive_records(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ArchiveRecord]:
        conds: list[str] = []
        params: list[Any] = []
        if pipeline_id is not None:
            conds.append("pipeline_id = ?")
            params.append(str(pipeline_id))
        if run_id is not None:
            conds.append("run_id = ?")
            params.append(str(run_id))
        where = " WHERE " + " AND ".join(conds) if conds else ""
        rows = await self._fetch_all(
            f"SELECT * FROM archive_records{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [_row_to_model(ArchiveRecord, row) for row in rows]

    async def get_checkpoints(self, run_id: UUID, step_id: str | None = None) -> Sequence[Checkpoint]:
        if step_id is not None:
            rows = await self._fetch_all(
                "SELECT * FROM checkpoints WHERE run_id = ? AND step_id = ? ORDER BY created_at",
                (str(run_id), step_id),
            )
        else:
            rows = await self._fetch_all("SELECT * FROM checkpoints WHERE run_id = ? ORDER BY created_at", (str(run_id),))
        return [_row_to_model(Checkpoint, row) for row in rows]

    async def get_dead_letters(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DeadLetter]:
        conds: list[str] = []
        params: list[Any] = []
        if pipeline_id is not None:
            conds.append("pipeline_id = ?")
            params.append(str(pipeline_id))
        if run_id is not None:
            conds.append("run_id = ?")
            params.append(str(run_id))
        where = " WHERE " + " AND ".join(conds) if conds else ""
        rows = await self._fetch_all(
            f"SELECT * FROM dead_letters{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [_row_to_model(DeadLetter, row) for row in rows]

    # ------------------------------------------------- operational transitions

    async def submit_run(
        self,
        pipeline_id: UUID,
        pipeline_version: int,
        inputs: Mapping[str, Any],
        execution_class: str,
        run_id: UUID,
    ) -> ExecutionRun:
        now = _now()
        run = ExecutionRun(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            run_id=run_id,
            status=ExecutionStatus.PENDING,
            execution_class=execution_class,
            inputs=dict(inputs),
        )
        await self.create(run)
        return run

    async def cancel_run(self, run_id: UUID, reason: str) -> ExecutionRun:
        run = await self.get_execution_run(run_id)
        if run is None:
            raise NotFoundError(f"execution run {run_id} not found")
        now = _now()
        updated = run.model_copy(
            update={
                "status": ExecutionStatus.CANCELLED,
                "error": reason,
                "finished_at": now,
                "updated_at": now,
            }
        )
        await self.update(updated)
        return updated

    async def retry_run(self, run_id: UUID) -> ExecutionRun:
        original = await self.get_execution_run(run_id)
        if original is None:
            raise NotFoundError(f"execution run {run_id} not found")
        now = _now()
        new_run = ExecutionRun(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            pipeline_id=original.pipeline_id,
            pipeline_version=original.pipeline_version,
            run_id=uuid4(),
            status=ExecutionStatus.PENDING,
            execution_class=original.execution_class,
            inputs=original.inputs,
            retry_count=original.retry_count + 1,
        )
        await self.create(new_run)
        return new_run

    async def pause_schedule(self, schedule_id: UUID) -> Schedule:
        schedule = await self.get_schedule(schedule_id)
        if schedule is None:
            raise NotFoundError(f"schedule {schedule_id} not found")
        updated = schedule.model_copy(
            update={
                "status": ScheduleStatus.PAUSED,
                "enabled": False,
                "updated_at": _now(),
            }
        )
        await self.update(updated)
        return updated

    async def resume_schedule(self, schedule_id: UUID) -> Schedule:
        schedule = await self.get_schedule(schedule_id)
        if schedule is None:
            raise NotFoundError(f"schedule {schedule_id} not found")
        updated = schedule.model_copy(
            update={
                "status": ScheduleStatus.ENABLED,
                "enabled": True,
                "updated_at": _now(),
            }
        )
        await self.update(updated)
        return updated

    async def disable_worker(self, worker_id: UUID) -> Worker:
        worker = await self.get_worker(worker_id)
        if worker is None:
            raise NotFoundError(f"worker {worker_id} not found")
        updated = worker.model_copy(update={"status": WorkerStatus.DISABLED, "updated_at": _now()})
        await self.update(updated)
        return updated

    async def replay_dead_letter(self, dead_letter_id: UUID, keep_original: bool = True) -> ExecutionRun:
        dead = await self.get("dead_letter", dead_letter_id)
        if dead is None or not isinstance(dead, DeadLetter):
            raise NotFoundError(f"dead letter {dead_letter_id} not found")
        now = _now()
        run = ExecutionRun(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            pipeline_id=dead.pipeline_id,
            pipeline_version=0,
            run_id=uuid4(),
            status=ExecutionStatus.PENDING,
            inputs=dead.original_inputs,
        )
        await self.create(run)
        if not keep_original:
            discarded = dead.model_copy(
                update={
                    "terminal_status": DeadLetterTerminalStatus.DISCARDED,
                    "updated_at": now,
                }
            )
            await self.update(discarded)
        return run

    async def discard_dead_letter(self, dead_letter_id: UUID) -> bool:
        dead = await self.get("dead_letter", dead_letter_id)
        if dead is None or not isinstance(dead, DeadLetter):
            return False
        if dead.terminal_status == DeadLetterTerminalStatus.DISCARDED:
            return False
        updated = dead.model_copy(
            update={
                "terminal_status": DeadLetterTerminalStatus.DISCARDED,
                "updated_at": _now(),
            }
        )
        await self.update(updated)
        return True

    async def materialize_pipeline(
        self,
        project_id: UUID,
        slug: str,
        name: str,
        definition_ref: str,
        definition_hash: str,
        definition_format: Literal["json", "yaml"],
        source_ref: str | None = None,
        source_hash: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[Pipeline, PipelineVersion]:
        now = _now()
        pipeline_id = uuid4()
        fmt = DefinitionFormat(definition_format)
        pipeline = Pipeline(
            id=pipeline_id,
            created_at=now,
            updated_at=now,
            project_id=project_id,
            slug=slug,
            name=name,
            source_ref=source_ref,
            source_hash=source_hash,
            definition_ref=definition_ref,
            current_version_number=1,
            current_version_hash=definition_hash,
            metadata=dict(metadata or {}),
        )
        version = PipelineVersion(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            pipeline_id=pipeline_id,
            version=1,
            definition_ref=definition_ref,
            definition_hash=definition_hash,
            definition_format=fmt,
            metadata=dict(metadata or {}),
        )
        async with await self.transaction():
            await self.create(pipeline)
            await self.create(version)
        return pipeline, version

    async def update_pipeline_definition(
        self,
        pipeline_id: UUID,
        definition_ref: str,
        definition_hash: str,
        definition_format: Literal["json", "yaml"],
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[Pipeline, PipelineVersion]:
        row = await self._fetch_one("SELECT * FROM pipelines WHERE id = ?", (str(pipeline_id),))
        if row is None:
            raise NotFoundError(f"pipeline {pipeline_id} not found")
        pipeline = _row_to_model(Pipeline, row)
        now = _now()
        next_version = pipeline.current_version_number + 1
        version = PipelineVersion(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            pipeline_id=pipeline_id,
            version=next_version,
            definition_ref=definition_ref,
            definition_hash=definition_hash,
            definition_format=DefinitionFormat(definition_format),
            metadata=dict(metadata or {}),
        )
        updated_pipeline = pipeline.model_copy(
            update={
                "definition_ref": definition_ref,
                "current_version_number": next_version,
                "current_version_hash": definition_hash,
                "updated_at": now,
            }
        )
        async with await self.transaction():
            await self.create(version)
            await self.update(updated_pipeline)
        return updated_pipeline, version

    # ------------------------------------------------------------ transactions

    async def transaction(self) -> TransactionContext:
        return _SQLiteTransaction(self)

    async def health_check(self) -> bool:
        if self._db is None:
            return False
        try:
            await self._fetch_one("SELECT 1")
            return True
        except sqlite3.Error:
            return False
