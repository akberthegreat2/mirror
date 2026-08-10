"""Database backend protocol.

This module defines the abstract contract that all database backend implementations
must satisfy. Backends include mirror_database_sqlite and mirror_database_postgres.
"""

from __future__ import annotations

import types
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypeVar
from uuid import UUID

from mirror_database.models import (
    ArchiveRecord,
    BaseEntity,
    Checkpoint,
    CrawledURL,
    DeadLetter,
    EntityType,
    ExecutionRun,
    ExecutionStep,
    Pipeline,
    PipelineVersion,
    Project,
    Schedule,
    Worker,
)

T = TypeVar("T", bound=BaseEntity)


class DatabaseBackend(ABC):
    """Abstract database backend contract.

    All implementations must provide CRUD operations for control-plane entities
    plus the operational transitions the control plane needs.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend (create tables, indexes, etc.)."""

    @abstractmethod
    async def close(self) -> None:
        """Close connections and release resources."""

    # --- Generic CRUD ---

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create a new entity. Returns the created entity with generated fields."""

    @abstractmethod
    async def get(self, entity_type: EntityType, entity_id: UUID) -> BaseEntity | None:
        """Get an entity by ID. Returns None if not found."""

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update an existing entity. Returns the updated entity."""

    @abstractmethod
    async def delete(self, entity_type: EntityType, entity_id: UUID) -> bool:
        """Delete an entity by ID. Returns True if deleted, False if not found."""

    @abstractmethod
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
        """List entities with optional filtering, pagination, and ordering."""

    @abstractmethod
    async def count(self, entity_type: EntityType, filters: Mapping[str, Any] | None = None) -> int:
        """Count entities matching filters."""

    # --- Entity-specific query helpers ---

    @abstractmethod
    async def get_project_by_slug(self, slug: str) -> Project | None:
        """Get project by slug."""

    @abstractmethod
    async def get_pipeline_by_slug(self, project_id: UUID, slug: str) -> Pipeline | None:
        """Get pipeline by project and slug."""

    @abstractmethod
    async def get_latest_pipeline_version(self, pipeline_id: UUID) -> PipelineVersion | None:
        """Get the latest version of a pipeline."""

    @abstractmethod
    async def get_pipeline_version(self, pipeline_id: UUID, version: int) -> PipelineVersion | None:
        """Get a specific pipeline version."""

    @abstractmethod
    async def list_pipeline_versions(self, pipeline_id: UUID) -> Sequence[PipelineVersion]:
        """List all versions of a pipeline, ordered by version."""

    @abstractmethod
    async def get_execution_run(self, run_id: UUID) -> ExecutionRun | None:
        """Get execution run by run_id."""

    @abstractmethod
    async def list_execution_runs(
        self,
        pipeline_id: UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExecutionRun]:
        """List execution runs with optional filters."""

    @abstractmethod
    async def get_execution_steps(self, run_id: UUID) -> Sequence[ExecutionStep]:
        """Get all steps for an execution run."""

    @abstractmethod
    async def get_worker(self, worker_id: UUID) -> Worker | None:
        """Get worker by ID."""

    @abstractmethod
    async def list_workers(
        self,
        execution_class: str | None = None,
        status: str | None = None,
    ) -> Sequence[Worker]:
        """List workers with optional filters."""

    @abstractmethod
    async def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        """Get schedule by ID."""

    @abstractmethod
    async def list_schedules(
        self,
        pipeline_id: UUID | None = None,
        status: str | None = None,
        enabled: bool | None = None,
    ) -> Sequence[Schedule]:
        """List schedules with optional filters."""

    @abstractmethod
    async def get_crawled_urls(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CrawledURL]:
        """Get crawled URLs with optional filters."""

    @abstractmethod
    async def get_archive_records(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ArchiveRecord]:
        """Get archive records with optional filters."""

    @abstractmethod
    async def get_checkpoints(
        self,
        run_id: UUID,
        step_id: str | None = None,
    ) -> Sequence[Checkpoint]:
        """Get checkpoints for a run, optionally filtered by step."""

    @abstractmethod
    async def get_dead_letters(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DeadLetter]:
        """Get dead letters with optional filters."""

    # --- Operational transitions ---

    @abstractmethod
    async def submit_run(
        self,
        pipeline_id: UUID,
        pipeline_version: int,
        inputs: Mapping[str, Any],
        execution_class: str,
        run_id: UUID,
    ) -> ExecutionRun:
        """Submit a new execution run. Returns the created run."""

    @abstractmethod
    async def cancel_run(self, run_id: UUID, reason: str) -> ExecutionRun:
        """Cancel an execution run. Returns the updated run."""

    @abstractmethod
    async def retry_run(self, run_id: UUID) -> ExecutionRun:
        """Retry a failed execution run. Returns the new run."""

    @abstractmethod
    async def pause_schedule(self, schedule_id: UUID) -> Schedule:
        """Pause a schedule. Returns the updated schedule."""

    @abstractmethod
    async def resume_schedule(self, schedule_id: UUID) -> Schedule:
        """Resume a paused schedule. Returns the updated schedule."""

    @abstractmethod
    async def disable_worker(self, worker_id: UUID) -> Worker:
        """Disable a worker. Returns the updated worker."""

    @abstractmethod
    async def replay_dead_letter(self, dead_letter_id: UUID, keep_original: bool = True) -> ExecutionRun:
        """Replay a dead letter as a new execution run. Returns the new run."""

    @abstractmethod
    async def discard_dead_letter(self, dead_letter_id: UUID) -> bool:
        """Discard a dead letter. Returns True if discarded."""

    @abstractmethod
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
        """Materialize a pipeline definition into a managed pipeline with version.
        Returns the pipeline and its first version.
        """

    @abstractmethod
    async def update_pipeline_definition(
        self,
        pipeline_id: UUID,
        definition_ref: str,
        definition_hash: str,
        definition_format: Literal["json", "yaml"],
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[Pipeline, PipelineVersion]:
        """Update a pipeline's definition, creating a new version.
        Returns the updated pipeline and the new version.
        """

    # --- Transaction support ---

    @abstractmethod
    async def transaction(self) -> TransactionContext:
        """Return a transaction context manager for atomic operations."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the backend is healthy."""


class TransactionContext(ABC):
    """Transaction context manager for atomic multi-entity operations."""

    @abstractmethod
    async def __aenter__(self) -> TransactionContext: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
