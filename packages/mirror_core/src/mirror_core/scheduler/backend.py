"""Persistence and due-job contract implemented by schedule backends."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from mirror_core.scheduler.models import ScheduleRecord


@runtime_checkable
class SchedulerBackend(Protocol):
    """Persistence and due-job contract for schedulers."""

    def schedule(self, record: ScheduleRecord) -> ScheduleRecord: ...

    def due(self, now: datetime | None = None) -> list[ScheduleRecord]: ...

    def mark_run(
        self, schedule_id: UUID, *, ran_at: datetime | None = None
    ) -> ScheduleRecord: ...

    def pause(self, schedule_id: UUID) -> ScheduleRecord: ...

    def resume(self, schedule_id: UUID) -> ScheduleRecord: ...

    def list(self) -> list[ScheduleRecord]: ...
