"""Unmanaged Django models over Mirror's database schema.

These models mirror the tables owned by the ``mirror_database`` backend
(``mirror_database_sqlite`` / ``mirror_database_postgres``). They are declared
``managed = False``: Django never creates or migrates operational tables, and
this app ships no migration for them. Django uses these models for admin
presentation and read-only queries only; every write goes through
:class:`mirror_control.ControlService`.
"""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models


class MirrorUser(AbstractUser):
    """Django user model for the control plane, on the dedicated auth database."""

    class Meta:
        verbose_name = "Mirror user"
        verbose_name_plural = "Mirror users"


class TimestampedModel(models.Model):
    """Abstract base for the unmanaged control-plane models."""

    id = models.CharField(max_length=36, primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        abstract = True


class Project(TimestampedModel):
    """Mirror application workspace and ownership boundary."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "projects"
        managed = False
        ordering: ClassVar[list[str]] = ["slug"]

    def __str__(self) -> str:
        return self.name


class Pipeline(TimestampedModel):
    """Named pipeline definition and governance record."""

    class Origin(models.TextChoices):
        LOCAL = "local", "Local"
        IMPORTED = "imported", "Imported"
        TEMPLATE = "template", "Template"
        CODE = "code", "Code"
        MANAGED = "managed", "Managed"

    project_id = models.CharField(max_length=36, db_index=True)
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=128)
    origin = models.CharField(max_length=20, choices=Origin.choices, default=Origin.LOCAL)
    is_read_only = models.BooleanField(default=False)
    source_ref = models.CharField(max_length=512, null=True, blank=True)
    source_hash = models.CharField(max_length=64, null=True, blank=True)
    definition_ref = models.CharField(max_length=512, null=True, blank=True)
    current_version_number = models.PositiveIntegerField(default=0)
    current_version_hash = models.CharField(max_length=64, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "pipelines"
        managed = False
        ordering: ClassVar[list[str]] = ["slug"]

    def __str__(self) -> str:
        return f"{self.project_id}:{self.slug}"


class PipelineVersion(TimestampedModel):
    """Immutable version snapshot of a pipeline definition."""

    pipeline_id = models.CharField(max_length=36, db_index=True)
    version = models.PositiveIntegerField()
    definition_ref = models.CharField(max_length=512)
    definition_hash = models.CharField(max_length=64)
    definition_format = models.CharField(max_length=20, default="json")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "pipeline_versions"
        managed = False
        ordering: ClassVar[list[str]] = ["pipeline_id", "version"]

    def __str__(self) -> str:
        return f"{self.pipeline_id}@v{self.version}"


class ExecutionRun(TimestampedModel):
    """One run of a pipeline or one-shot operation."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        SKIPPED = "skipped", "Skipped"

    pipeline_id = models.CharField(max_length=36, db_index=True)
    pipeline_version = models.IntegerField()
    run_id = models.CharField(max_length=36, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    execution_class = models.CharField(max_length=40, default="default")
    worker_id = models.CharField(max_length=36, null=True, blank=True)
    inputs = models.JSONField(default=dict, blank=True)
    error = models.TextField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "execution_runs"
        managed = False
        ordering: ClassVar[list[str]] = ["-created_at", "run_id"]

    def __str__(self) -> str:
        return str(self.run_id)


class ExecutionStep(TimestampedModel):
    """One step inside a run."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        SKIPPED = "skipped", "Skipped"
        BLOCKED = "blocked", "Blocked"

    run_id = models.CharField(max_length=36, db_index=True)
    step_id = models.CharField(max_length=200)
    capability = models.CharField(max_length=200)
    provider = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    inputs = models.JSONField(default=dict, blank=True)
    error = models.TextField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "execution_steps"
        managed = False
        ordering: ClassVar[list[str]] = ["run_id", "step_id"]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.step_id}"


class Worker(TimestampedModel):
    """Registered worker or live worker heartbeat record."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        IDLE = "idle", "Idle"
        DISABLED = "disabled", "Disabled"
        OFFLINE = "offline", "Offline"

    worker_id = models.CharField(max_length=36, unique=True)
    backend = models.CharField(max_length=120)
    execution_class = models.CharField(max_length=40, default="default")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workers"
        managed = False
        ordering: ClassVar[list[str]] = ["worker_id"]

    def __str__(self) -> str:
        return str(self.worker_id)


class Schedule(TimestampedModel):
    """Scheduled execution policy for a pipeline."""

    class Status(models.TextChoices):
        ENABLED = "enabled", "Enabled"
        PAUSED = "paused", "Paused"
        DISABLED = "disabled", "Disabled"
        EXPIRED = "expired", "Expired"

    name = models.CharField(max_length=128)
    pipeline_id = models.CharField(max_length=36, db_index=True)
    cron = models.CharField(max_length=128)
    enabled = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENABLED)
    max_concurrency = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "schedules"
        managed = False
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self) -> str:
        return self.name


class CrawledURL(TimestampedModel):
    """URL discovered or crawled by the Crawl capability."""

    class Status(models.TextChoices):
        DISCOVERED = "discovered", "Discovered"
        CRAWLED = "crawled", "Crawled"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    pipeline_id = models.CharField(max_length=36, null=True, blank=True, db_index=True)
    run_id = models.CharField(max_length=36, null=True, blank=True)
    url = models.CharField(max_length=2048)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DISCOVERED)
    discovered_at = models.DateTimeField()
    crawled_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "crawled_urls"
        managed = False
        ordering: ClassVar[list[str]] = ["-discovered_at", "url"]
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["url"])]

    def __str__(self) -> str:
        return self.url


class ArchiveRecord(TimestampedModel):
    """Archived resource reference produced by Archive."""

    pipeline_id = models.CharField(max_length=36, null=True, blank=True, db_index=True)
    run_id = models.CharField(max_length=36, null=True, blank=True)
    resource_key = models.CharField(max_length=512)
    storage_ref = models.CharField(max_length=512)
    content_hash = models.CharField(max_length=64)
    content_type = models.CharField(max_length=120, null=True, blank=True)
    content_length = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "archive_records"
        managed = False
        ordering: ClassVar[list[str]] = ["-created_at", "resource_key"]
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["resource_key"])]

    def __str__(self) -> str:
        return self.resource_key


class Checkpoint(TimestampedModel):
    """Persisted checkpoint for resumable execution."""

    run_id = models.CharField(max_length=36, db_index=True)
    step_id = models.CharField(max_length=200)
    payload = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "checkpoints"
        managed = False
        ordering: ClassVar[list[str]] = ["-created_at", "run_id", "step_id"]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.step_id}"


class DeadLetter(TimestampedModel):
    """Terminal failure record for a run or step."""

    class TerminalStatus(models.TextChoices):
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        DISCARDED = "discarded", "Discarded"

    run_id = models.CharField(
        max_length=36,
    )
    pipeline_id = models.CharField(
        max_length=36,
    )
    step_id = models.CharField(max_length=200)
    terminal_status = models.CharField(max_length=20, choices=TerminalStatus.choices)
    reason = models.TextField()
    original_inputs = models.JSONField(default=dict, blank=True)
    policy_state = models.JSONField(default=dict, blank=True)
    provenance = models.JSONField(default=dict, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "dead_letters"
        managed = False
        ordering: ClassVar[list[str]] = ["-created_at", "run_id"]

    def __str__(self) -> str:
        return str(self.run_id)
