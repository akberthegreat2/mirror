"""SQLite-backed schedule persistence for durable local workflows."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from mirror_core.scheduler.inmemory import InMemoryScheduler
from mirror_core.scheduler.models import (
    ScheduleRecord,
    ScheduleState,
    ScheduleTrigger,
    ScheduleTriggerKind,
)
from mirror_core.scheduler.util import _coerce_datetime, _parse_datetime


class SQLiteScheduler:
    """SQLite-backed scheduler for durable local workflows."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def schedule(self, record: ScheduleRecord) -> ScheduleRecord:
        self._conn.execute(
            """
            INSERT INTO schedules(
                schedule_id, name, due_at, interval_seconds, payload, state, last_run_at,
                trigger_kind, trigger_expression, trigger_every_seconds, trigger_depends_on,
                trigger_catch_up, execution_class, queue_name, next_run_at, expires_at, disabled_at, paused_at,
                max_concurrency, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(schedule_id)
            DO UPDATE SET name = excluded.name,
                          due_at = excluded.due_at,
                          interval_seconds = excluded.interval_seconds,
                          payload = excluded.payload,
                          state = excluded.state,
                          last_run_at = excluded.last_run_at,
                          trigger_kind = excluded.trigger_kind,
                          trigger_expression = excluded.trigger_expression,
                          trigger_every_seconds = excluded.trigger_every_seconds,
                          trigger_depends_on = excluded.trigger_depends_on,
                          trigger_catch_up = excluded.trigger_catch_up,
                          execution_class = excluded.execution_class,
                          queue_name = excluded.queue_name,
                          next_run_at = excluded.next_run_at,
                          expires_at = excluded.expires_at,
                          disabled_at = excluded.disabled_at,
                          paused_at = excluded.paused_at,
                          max_concurrency = excluded.max_concurrency,
                          metadata = excluded.metadata
            """,
            self._record_values(record),
        )
        self._conn.commit()
        return record

    def due(self, now: datetime | None = None) -> list[ScheduleRecord]:
        now = _coerce_datetime(now or datetime.now(timezone.utc))
        rows = self._conn.execute(
            """
            SELECT * FROM schedules
            WHERE state = ? AND COALESCE(next_run_at, due_at) <= ?
            ORDER BY COALESCE(next_run_at, due_at), name, schedule_id
            """,
            (ScheduleState.SCHEDULED.value, now.isoformat()),
        ).fetchall()
        return [
            self._row_to_record(row)
            for row in rows
            if self._row_to_record(row).is_due(now)
        ]

    def mark_run(
        self, schedule_id: UUID, *, ran_at: datetime | None = None
    ) -> ScheduleRecord:
        record = self._require(schedule_id)
        ran_at = _coerce_datetime(ran_at or datetime.now(timezone.utc))
        updated_base = record.model_copy(update={"last_run_at": ran_at})
        next_run_at = updated_base.next_run(ran_at)
        updated = updated_base.model_copy(
            update={
                "next_run_at": next_run_at,
                "state": ScheduleState.DONE
                if next_run_at is None
                else ScheduleState.SCHEDULED,
            }
        )
        self.schedule(updated)
        return updated

    def pause(self, schedule_id: UUID) -> ScheduleRecord:
        record = self._require(schedule_id)
        now = datetime.now(timezone.utc)
        updated = record.model_copy(
            update={
                "state": ScheduleState.PAUSED,
                "paused_at": now,
                "disabled_at": None,
            }
        )
        self.schedule(updated)
        return updated

    def resume(self, schedule_id: UUID) -> ScheduleRecord:
        record = self._require(schedule_id)
        now = datetime.now(timezone.utc)
        state = (
            ScheduleState.EXPIRED if record.is_expired(now) else ScheduleState.SCHEDULED
        )
        next_run_at = record.next_run(now)
        if record.trigger.kind is ScheduleTriggerKind.ONCE:
            next_run_at = None
        updated = record.model_copy(
            update={
                "state": state,
                "paused_at": None,
                "disabled_at": None,
                "next_run_at": next_run_at,
            }
        )
        self.schedule(updated)
        return updated

    def list(self) -> list[ScheduleRecord]:
        rows = self._conn.execute(
            "SELECT * FROM schedules ORDER BY COALESCE(next_run_at, due_at), name, schedule_id"
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                due_at TEXT NOT NULL,
                interval_seconds REAL,
                payload TEXT NOT NULL,
                state TEXT NOT NULL,
                last_run_at TEXT,
                trigger_kind TEXT NOT NULL,
                trigger_expression TEXT,
                trigger_every_seconds REAL,
                trigger_depends_on TEXT NOT NULL,
                trigger_catch_up INTEGER NOT NULL,
                execution_class TEXT NOT NULL DEFAULT 'default',
                queue_name TEXT NOT NULL,
                next_run_at TEXT,
                expires_at TEXT,
                disabled_at TEXT,
                paused_at TEXT,
                max_concurrency INTEGER NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _require(self, schedule_id: UUID) -> ScheduleRecord:
        row = self._conn.execute(
            "SELECT * FROM schedules WHERE schedule_id = ?",
            (str(schedule_id),),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown schedule: {schedule_id}")
        return self._row_to_record(row)

    def _record_values(self, record: ScheduleRecord) -> tuple[Any, ...]:
        return (
            str(record.schedule_id),
            record.name,
            record.due_at.isoformat(),
            record.interval_seconds,
            json.dumps(record.payload, sort_keys=True),
            record.state.value,
            record.last_run_at.isoformat() if record.last_run_at is not None else None,
            record.trigger.kind.value,
            record.trigger.expression,
            record.trigger.every_seconds,
            json.dumps(list(record.trigger.depends_on), sort_keys=True),
            1 if record.trigger.catch_up else 0,
            record.execution_class,
            record.queue_name,
            record.next_run_at.isoformat() if record.next_run_at is not None else None,
            record.expires_at.isoformat() if record.expires_at is not None else None,
            record.disabled_at.isoformat() if record.disabled_at is not None else None,
            record.paused_at.isoformat() if record.paused_at is not None else None,
            record.max_concurrency,
            json.dumps(dict(record.metadata), sort_keys=True),
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ScheduleRecord:
        trigger = ScheduleTrigger(
            kind=ScheduleTriggerKind(row["trigger_kind"]),
            expression=row["trigger_expression"],
            every_seconds=row["trigger_every_seconds"],
            depends_on=tuple(json.loads(row["trigger_depends_on"] or "[]")),
            catch_up=bool(row["trigger_catch_up"]),
        )
        record = ScheduleRecord(
            schedule_id=UUID(row["schedule_id"]),
            name=row["name"],
            due_at=_parse_datetime(row["due_at"]),
            interval_seconds=row["interval_seconds"],
            payload=json.loads(row["payload"]),
            state=ScheduleState(row["state"]),
            last_run_at=_parse_datetime(row["last_run_at"])
            if row["last_run_at"]
            else None,
            trigger=trigger,
            execution_class=row["execution_class"]
            if "execution_class" in row
            else row["queue_name"],
            queue_name=row["queue_name"],
            next_run_at=_parse_datetime(row["next_run_at"])
            if row["next_run_at"]
            else None,
            expires_at=_parse_datetime(row["expires_at"])
            if row["expires_at"]
            else None,
            disabled_at=_parse_datetime(row["disabled_at"])
            if row["disabled_at"]
            else None,
            paused_at=_parse_datetime(row["paused_at"]) if row["paused_at"] else None,
            max_concurrency=row["max_concurrency"],
            metadata=json.loads(row["metadata"]),
        )
        return InMemoryScheduler._normalize(record)
