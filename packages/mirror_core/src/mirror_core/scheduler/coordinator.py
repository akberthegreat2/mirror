"""Core-owned coordination service for scheduling and dispatching."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from mirror_core.metadata import MetadataRecord, MetadataStore
from mirror_core.scheduler.backend import SchedulerBackend
from mirror_core.scheduler.models import ScheduleRecord
from mirror_core.scheduler.util import _coerce_datetime
from mirror_core.workers import WorkerBackend, WorkerJob


class SchedulerCoordinator:
    """Core-owned service that turns due schedules into worker jobs."""

    def __init__(
        self,
        scheduler: SchedulerBackend,
        worker_backend: WorkerBackend,
        metadata_store: MetadataStore | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._worker_backend = worker_backend
        self._metadata_store = metadata_store

    async def dispatch_due(self, now: datetime | None = None) -> list[WorkerJob]:
        """Submit all due schedules to the worker backend."""
        now = _coerce_datetime(now or datetime.now(timezone.utc))
        jobs: list[WorkerJob] = []
        for record in self._scheduler.due(now):
            job = WorkerJob(
                kind=record.name,
                pipeline_id=record.metadata.get("pipeline_id", record.name),
                payload={
                    "schedule_id": str(record.schedule_id),
                    "name": record.name,
                    "execution_class": record.execution_class,
                    "queue_name": record.queue_name,
                    "scheduled_at": record.effective_due_at().isoformat(),
                    "payload": record.payload,
                    "metadata": dict(record.metadata),
                },
                metadata={
                    "schedule_id": str(record.schedule_id),
                    "schedule_name": record.name,
                    "execution_class": record.execution_class,
                    "queue_name": record.queue_name,
                    "trigger": record.trigger.model_dump(mode="json"),
                },
            )
            submitted = await self._worker_backend.submit(job)
            updated = self._scheduler.mark_run(record.schedule_id, ran_at=now)
            self._record_metadata(
                MetadataRecord.scheduler(
                    record.schedule_id,
                    payload={
                        "name": updated.name,
                        "state": updated.state.value,
                        "execution_class": updated.execution_class,
                        "queue_name": updated.queue_name,
                        "last_run_at": updated.last_run_at.isoformat()
                        if updated.last_run_at is not None
                        else None,
                        "next_run_at": updated.next_run_at.isoformat()
                        if updated.next_run_at is not None
                        else None,
                        "trigger": updated.trigger.model_dump(mode="json"),
                    },
                )
            )
            jobs.append(submitted)
        return jobs

    def schedule(self, record: ScheduleRecord) -> ScheduleRecord:
        """Persist a schedule and record its metadata."""
        stored = self._scheduler.schedule(record)
        self._record_metadata(
            MetadataRecord.scheduler(
                stored.schedule_id,
                payload={
                    "name": stored.name,
                    "state": stored.state.value,
                    "execution_class": stored.execution_class,
                    "queue_name": stored.queue_name,
                    "due_at": stored.due_at.isoformat(),
                    "next_run_at": stored.next_run_at.isoformat()
                    if stored.next_run_at is not None
                    else None,
                    "trigger": stored.trigger.model_dump(mode="json"),
                },
            )
        )
        return stored

    def pause(self, schedule_id: UUID) -> ScheduleRecord:
        """Pause an existing schedule and record the state transition."""
        updated = self._scheduler.pause(schedule_id)
        self._record_metadata(
            MetadataRecord.scheduler(
                schedule_id,
                payload={
                    "state": updated.state.value,
                    "execution_class": updated.execution_class,
                    "queue_name": updated.queue_name,
                },
            )
        )
        return updated

    def resume(self, schedule_id: UUID) -> ScheduleRecord:
        """Resume an existing schedule and record the state transition."""
        updated = self._scheduler.resume(schedule_id)
        self._record_metadata(
            MetadataRecord.scheduler(
                schedule_id,
                payload={
                    "state": updated.state.value,
                    "execution_class": updated.execution_class,
                    "queue_name": updated.queue_name,
                },
            )
        )
        return updated

    def _record_metadata(self, record: MetadataRecord) -> None:
        if self._metadata_store is not None:
            self._metadata_store.put(record)
