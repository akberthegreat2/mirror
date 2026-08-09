"""Scheduled-job domain models: lifecycle states, triggers, and records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from mirror_core.scheduler.util import _coerce_datetime, _next_cron_time


class ScheduleState(str, Enum):
    """Lifecycle states for a scheduled job."""

    SCHEDULED = "scheduled"
    PAUSED = "paused"
    RUNNING = "running"
    DONE = "done"
    DISABLED = "disabled"
    EXPIRED = "expired"


class ScheduleTriggerKind(str, Enum):
    """Supported schedule trigger families."""

    ONCE = "once"
    DELAY = "delay"
    INTERVAL = "interval"
    CRON = "cron"
    DEPENDENCY = "dependency"
    BACKFILL = "backfill"


class ScheduleTrigger(BaseModel):
    """Declarative scheduling trigger metadata."""

    model_config = ConfigDict(frozen=True)

    kind: ScheduleTriggerKind = ScheduleTriggerKind.ONCE
    expression: str | None = None
    every_seconds: float | None = Field(default=None, gt=0.0)
    depends_on: tuple[str, ...] = Field(default_factory=tuple)
    catch_up: bool = False

    def is_recurring(self) -> bool:
        """Return whether the trigger can produce more than one run."""
        return self.kind in {
            ScheduleTriggerKind.DELAY,
            ScheduleTriggerKind.INTERVAL,
            ScheduleTriggerKind.CRON,
            ScheduleTriggerKind.DEPENDENCY,
            ScheduleTriggerKind.BACKFILL,
        }


class ScheduleRecord(BaseModel):
    """Immutable scheduled job record."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    schedule_id: UUID = Field(default_factory=uuid4)
    name: str
    due_at: datetime
    interval_seconds: float | None = Field(default=None, gt=0.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    state: ScheduleState = ScheduleState.SCHEDULED
    last_run_at: datetime | None = None
    trigger: ScheduleTrigger = Field(default_factory=ScheduleTrigger)
    execution_class: str = "default"
    queue_name: str = "default"
    next_run_at: datetime | None = None
    expires_at: datetime | None = None
    disabled_at: datetime | None = None
    paused_at: datetime | None = None
    max_concurrency: int = Field(default=1, ge=1)
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any, /) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.execution_class == "default" and self.queue_name != "default":
            object.__setattr__(self, "execution_class", self.queue_name)

    def is_paused(self) -> bool:
        """Return whether the schedule is explicitly paused."""
        return self.state is ScheduleState.PAUSED

    def is_disabled(self) -> bool:
        """Return whether the schedule is disabled."""
        return self.state is ScheduleState.DISABLED

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return whether the schedule has expired."""
        if self.state is ScheduleState.EXPIRED:
            return True
        if self.expires_at is None:
            return False
        now = _coerce_datetime(now or datetime.now(timezone.utc))
        return self.expires_at <= now

    def effective_due_at(self) -> datetime:
        """Return the next time this schedule should be considered due."""
        return self.next_run_at or self.due_at

    def is_due(self, now: datetime | None = None) -> bool:
        """Return whether the schedule should be dispatched now."""
        now = _coerce_datetime(now or datetime.now(timezone.utc))
        return (
            self.state is ScheduleState.SCHEDULED
            and not self.is_expired(now)
            and self.effective_due_at() <= now
        )

    def next_run(self, now: datetime | None = None) -> datetime | None:
        """Compute the next run time based on trigger metadata."""
        now = _coerce_datetime(now or datetime.now(timezone.utc))
        if self.is_expired(now) or self.state in {
            ScheduleState.DONE,
            ScheduleState.EXPIRED,
        }:
            return None

        trigger = self.trigger
        if trigger.kind is ScheduleTriggerKind.ONCE:
            return None if self.last_run_at is not None else self.effective_due_at()

        if trigger.kind in {ScheduleTriggerKind.DELAY, ScheduleTriggerKind.INTERVAL}:
            interval = trigger.every_seconds or self.interval_seconds
            if interval is None:
                return self.effective_due_at()
            if self.last_run_at is None:
                return self.effective_due_at()
            base = self.last_run_at
            return base + timedelta(seconds=interval)

        if trigger.kind is ScheduleTriggerKind.CRON:
            expression = trigger.expression
            if expression:
                parsed = _next_cron_time(expression, after=self.last_run_at or now)
                if parsed is not None:
                    return parsed
            return self.effective_due_at() if self.last_run_at is None else None

        if trigger.kind in {
            ScheduleTriggerKind.DEPENDENCY,
            ScheduleTriggerKind.BACKFILL,
        }:
            if trigger.catch_up and self.last_run_at is not None:
                interval = trigger.every_seconds or self.interval_seconds
                if interval is not None:
                    return self.last_run_at + timedelta(seconds=interval)
            return self.effective_due_at() if self.last_run_at is None else None

        return self.effective_due_at() if self.last_run_at is None else None
