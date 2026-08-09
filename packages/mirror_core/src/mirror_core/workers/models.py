"""Worker state and data models shared by backends, stores, and queues."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class JobState(str, Enum):
    """Lifecycle states for one submitted worker job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerJob(BaseModel):
    """Immutable worker job payload."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    job_id: UUID = Field(default_factory=uuid4)
    kind: str = "generic"
    run_id: UUID | None = None
    pipeline_id: str | None = None
    step_id: str | None = None
    execution_class: str = "default"
    payload: dict[str, Any] = Field(default_factory=dict)
    state: JobState = JobState.QUEUED
    worker_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    claimed_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    lease_expires_at: datetime | None = None

    def model_post_init(self, __context: Any, /) -> None:
        if self.run_id is None:
            object.__setattr__(self, "run_id", self.job_id)
        if self.pipeline_id is None:
            object.__setattr__(
                self, "pipeline_id", self.metadata.get("pipeline_id", self.kind)
            )
        if self.step_id is None and self.metadata.get("step_id") is not None:
            object.__setattr__(self, "step_id", str(self.metadata["step_id"]))


class WorkerLease(BaseModel):
    """Lease granted to one worker for a submitted job."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    job_id: UUID
    worker_id: str
    expires_at: datetime


class ExecutionRecord(BaseModel):
    """Stored execution metadata for a completed run."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    run_id: UUID
    outcome: str
    payload: dict[str, Any] = Field(default_factory=dict)
    worker_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeadLetterRecord(BaseModel):
    """Structured terminal failure record for distributed execution."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    run_id: UUID
    pipeline_id: str
    step_id: str | None = None
    reason: str
    original_inputs: dict[str, Any] = Field(default_factory=dict)
    policy_state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)
    terminal_status: str
    worker_id: str | None = None
    lease_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

