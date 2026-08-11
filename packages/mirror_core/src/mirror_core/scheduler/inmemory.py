"""In-memory scheduler backend for development and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from mirror_core.scheduler.models import (
    ScheduleRecord,
    ScheduleState,
    ScheduleTriggerKind,
)
from mirror_core.scheduler.util import _coerce_datetime


class InMemoryScheduler:
    """In-memory scheduler for development and tests."""

    def __init__(self) -> None:
        self._records: dict[UUID, ScheduleRecord] = {}

    def schedule(self, record: ScheduleRecord) -> ScheduleRecord:
        self._records[record.schedule_id] = record
        return record

    def due(self, now: datetime | None = None) -> list[ScheduleRecord]:
        now = _coerce_datetime(now or datetime.now(timezone.utc))
        return sorted(
            [record for record in self._records.values() if record.is_due(now)],
            key=lambda record: (
                record.effective_due_at(),
                record.name,
                str(record.schedule_id),
            ),
        )

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
        self._records[schedule_id] = updated
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
        self._records[schedule_id] = updated
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
        self._records[schedule_id] = updated
        return updated

    def list(self) -> list[ScheduleRecord]:
        return sorted(
            self._records.values(),
            key=lambda record: (
                record.effective_due_at(),
                record.name,
                str(record.schedule_id),
            ),
        )

    def _require(self, schedule_id: UUID) -> ScheduleRecord:
        try:
            return self._records[schedule_id]
        except KeyError as exc:
            raise KeyError(f"Unknown schedule: {schedule_id}") from exc

    @staticmethod
    def _normalize(record: ScheduleRecord) -> ScheduleRecord:
        return record
