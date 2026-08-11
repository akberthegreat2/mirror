"""Control-plane entity models.

These are the canonical Pydantic models for Mirror's control-plane entities.
Database backends (SQLite, PostgreSQL) persist these entities.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class PipelineOrigin(str, enum.Enum):
    LOCAL = "local"
    IMPORTED = "imported"
    TEMPLATE = "template"
    CODE = "code"
    MANAGED = "managed"


class DefinitionFormat(str, enum.Enum):
    JSON = "json"
    YAML = "yaml"


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class WorkerStatus(str, enum.Enum):
    ACTIVE = "active"
    IDLE = "idle"
    DISABLED = "disabled"
    OFFLINE = "offline"


class ScheduleStatus(str, enum.Enum):
    ENABLED = "enabled"
    PAUSED = "paused"
    DISABLED = "disabled"
    EXPIRED = "expired"


class CrawlStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    CRAWLED = "crawled"
    FAILED = "failed"
    SKIPPED = "skipped"


class DeadLetterTerminalStatus(str, enum.Enum):
    FAILED = "failed"
    CANCELLED = "cancelled"
    DISCARDED = "discarded"


class BaseEntity(BaseModel):
    """Base model with common fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class Project(BaseEntity):
    """Project entity."""

    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=128)
    status: ProjectStatus = ProjectStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class Pipeline(BaseEntity):
    """Pipeline entity."""

    project_id: UUID
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=128)
    origin: PipelineOrigin = PipelineOrigin.LOCAL
    is_read_only: bool = False
    source_ref: str | None = Field(default=None, max_length=512)
    source_hash: str | None = Field(default=None, max_length=64)
    definition_ref: str | None = Field(default=None, max_length=512)
    current_version_number: int = 0
    current_version_hash: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineVersion(BaseEntity):
    """Pipeline version entity."""

    pipeline_id: UUID
    version: int = Field(ge=1)
    definition_ref: str = Field(min_length=1, max_length=512)
    definition_hash: str = Field(min_length=1, max_length=64)
    definition_format: DefinitionFormat = DefinitionFormat.JSON
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionRun(BaseEntity):
    """Execution run entity."""

    pipeline_id: UUID
    pipeline_version: int
    run_id: UUID
    status: ExecutionStatus = ExecutionStatus.PENDING
    execution_class: str = "default"
    worker_id: UUID | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    retry_count: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExecutionStep(BaseEntity):
    """Execution step entity."""

    run_id: UUID
    step_id: str
    capability: str
    provider: str
    status: StepStatus = StepStatus.PENDING
    inputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    retry_count: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Worker(BaseEntity):
    """Worker entity."""

    worker_id: UUID
    backend: str
    execution_class: str
    status: WorkerStatus = WorkerStatus.ACTIVE
    heartbeat_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Schedule(BaseEntity):
    """Schedule entity."""

    name: str = Field(min_length=1, max_length=128)
    pipeline_id: UUID
    cron: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    next_run_at: datetime | None = None
    status: ScheduleStatus = ScheduleStatus.ENABLED
    max_concurrency: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrawledURL(BaseEntity):
    """Crawled URL entity."""

    pipeline_id: UUID | None = None
    run_id: UUID | None = None
    url: str = Field(min_length=1, max_length=2048)
    status: CrawlStatus = CrawlStatus.DISCOVERED
    discovered_at: datetime
    crawled_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchiveRecord(BaseEntity):
    """Archive record entity."""

    pipeline_id: UUID | None = None
    run_id: UUID | None = None
    resource_key: str = Field(min_length=1, max_length=512)
    storage_ref: str = Field(min_length=1, max_length=512)
    content_hash: str = Field(min_length=1, max_length=64)
    content_type: str | None = None
    content_length: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Checkpoint(BaseEntity):
    """Checkpoint entity."""

    run_id: UUID
    step_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeadLetter(BaseEntity):
    """Dead letter entity."""

    run_id: UUID
    pipeline_id: UUID
    step_id: str
    terminal_status: DeadLetterTerminalStatus
    reason: str = Field(min_length=1)
    original_inputs: dict[str, Any] = Field(default_factory=dict)
    policy_state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


# Type aliases for entity registry
EntityType = Literal[
    "project",
    "pipeline",
    "pipeline_version",
    "execution_run",
    "execution_step",
    "worker",
    "schedule",
    "crawled_url",
    "archive_record",
    "checkpoint",
    "dead_letter",
]

ENTITY_MODEL_MAP: dict[EntityType, type[BaseEntity]] = {
    "project": Project,
    "pipeline": Pipeline,
    "pipeline_version": PipelineVersion,
    "execution_run": ExecutionRun,
    "execution_step": ExecutionStep,
    "worker": Worker,
    "schedule": Schedule,
    "crawled_url": CrawledURL,
    "archive_record": ArchiveRecord,
    "checkpoint": Checkpoint,
    "dead_letter": DeadLetter,
}
