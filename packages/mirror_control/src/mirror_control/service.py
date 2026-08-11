"""Framework-neutral application service for the Mirror control plane.

``ControlService`` is the single implementation of control-plane behavior. It
wraps a :class:`DatabaseBackend` for entity persistence and operational
transitions and an optional :class:`BlobStore` for pipeline definition
documents. CLI, Django admin, DRF, and a future dashboard are thin adapters
over this service and therefore behave identically.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from mirror_core.metadata.models import MetadataRecord
from mirror_core.metadata.store import MetadataStore, SQLiteMetadataStore
from mirror_core.pipeline import Pipeline as CorePipeline
from mirror_core.storage import BlobStore, FileSystemBlobStore
from mirror_core.workers.models import WorkerJob
from mirror_core.workers.protocols import WorkerBackend
from mirror_database.models import (
    ENTITY_MODEL_MAP,
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
from mirror_database.protocol import DatabaseBackend

from mirror_control.errors import (
    NotFoundError,
    UnknownEntityError,
)
from mirror_control.manifest import CONTROL_PLANE_MANIFEST

DEFAULT_BLOB_ENV = "MIRROR_CONTROL_BLOB_ROOT"
DEFAULT_BLOB_DIR = ".mirror/control-plane/blobs"
DEFAULT_METADATA_ENV = "MIRROR_CONTROL_METADATA_ROOT"
DEFAULT_METADATA_DIR = ".mirror/control-plane/metadata.db"

__all__ = [
    "CONTROL_PLANE_MANIFEST",
    "ControlService",
    "content_hash",
    "default_blob_root",
    "default_blob_store",
    "default_metadata_store",
    "deserialize_pipeline_definition",
    "serialize_pipeline_definition",
]


def default_blob_root() -> Path:
    """Return the configured blob store root for control-plane documents."""

    value = os.environ.get(DEFAULT_BLOB_ENV)
    return Path(value) if value else Path(DEFAULT_BLOB_DIR)


def default_blob_store() -> FileSystemBlobStore:
    """Build the default filesystem blob store."""

    return FileSystemBlobStore(default_blob_root())


def default_metadata_store() -> SQLiteMetadataStore:
    """Build the default SQLite store for operational metadata records."""

    value = os.environ.get(DEFAULT_METADATA_ENV)
    return SQLiteMetadataStore(Path(value) if value else Path(DEFAULT_METADATA_DIR))


def serialize_pipeline_definition(pipeline: CorePipeline) -> bytes:
    """Serialize a core pipeline into canonical JSON bytes."""

    payload = pipeline.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")


def deserialize_pipeline_definition(raw: bytes) -> CorePipeline:
    """Deserialize canonical JSON bytes back into a core pipeline."""

    return CorePipeline.model_validate_json(raw)


def content_hash(payload: bytes) -> str:
    """Return a stable digest for a pipeline definition blob."""

    return hashlib.sha256(payload).hexdigest()


def _definition_blob_key(project_slug: str, pipeline_slug: str, version: int) -> str:
    return f"pipelines/{project_slug}/{pipeline_slug}/v{version}.json"


# Manifest entity names (kebab-case) to backend entity types (snake_case).
_ENTITY_TYPE_BY_NAME: dict[str, EntityType] = {
    "project": "project",
    "pipeline": "pipeline",
    "pipeline-version": "pipeline_version",
    "execution-run": "execution_run",
    "execution-step": "execution_step",
    "worker": "worker",
    "schedule": "schedule",
    "crawled-url": "crawled_url",
    "archive-record": "archive_record",
    "checkpoint": "checkpoint",
    "dead-letter": "dead_letter",
}

_manifest_names = {spec.name for spec in CONTROL_PLANE_MANIFEST.entities}
if _manifest_names != set(_ENTITY_TYPE_BY_NAME):
    raise RuntimeError("control-plane manifest and entity-type map drifted")


def _entity_type(name: str) -> EntityType:
    try:
        return _ENTITY_TYPE_BY_NAME[name]
    except KeyError:
        raise UnknownEntityError(name) from None


class ControlService:
    """Framework-neutral application service for the control plane.

    All control-plane interfaces (CLI, Django admin, DRF) call the same methods
    on this service, guaranteeing identical operations across interfaces.
    """

    def __init__(
        self,
        backend: DatabaseBackend,
        blob_store: BlobStore | None = None,
        worker_backend: WorkerBackend | None = None,
        metadata_store: MetadataStore | None = None,
    ) -> None:
        self.backend = backend
        self.blob_store = blob_store or default_blob_store()
        self.worker_backend = worker_backend
        self.metadata_store = metadata_store

    def _audit(
        self,
        action: str,
        subject_id: str | UUID,
        *,
        actor: str | None,
        target: str,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Record an audit event when a metadata store is configured.

        Operational actions are the ones that mutate control-plane state, so
        they are audited by default; read operations are not.
        """

        if self.metadata_store is None:
            return
        payload: dict[str, Any] = {"actor": actor or "system", "action": action, "target": target}
        if extra:
            payload.update(extra)
        self.metadata_store.put(
            MetadataRecord.audit_event(subject_id, action, payload=payload)
        )

    @property
    def manifest(self) -> Any:
        return CONTROL_PLANE_MANIFEST

    # ------------------------------------------------------------------ CRUD

    async def create_entity(self, name: str, data: Mapping[str, Any]) -> BaseEntity:
        """Create an entity of the given control-plane type."""

        entity_type = _entity_type(name)
        model_cls = ENTITY_MODEL_MAP[entity_type]
        entity = model_cls.model_validate(dict(data))
        return await self.backend.create(entity)

    async def get_entity(self, name: str, entity_id: UUID) -> BaseEntity:
        """Get an entity by ID."""

        entity_type = _entity_type(name)
        entity = await self.backend.get(entity_type, entity_id)
        if entity is None:
            raise NotFoundError(f"{entity_type} {entity_id} not found")
        return entity

    async def update_entity(self, name: str, entity_id: UUID, data: Mapping[str, Any]) -> BaseEntity:
        """Update an existing entity with the given field values."""

        entity_type = _entity_type(name)
        existing = await self.backend.get(entity_type, entity_id)
        if existing is None:
            raise NotFoundError(f"{entity_type} {entity_id} not found")
        model_cls = ENTITY_MODEL_MAP[entity_type]
        payload = existing.model_dump()
        payload.update(dict(data))
        return await self.backend.update(model_cls.model_validate(payload))

    async def delete_entity(self, name: str, entity_id: UUID) -> bool:
        """Delete an entity by ID. Returns True if it existed."""

        entity_type = _entity_type(name)
        return await self.backend.delete(entity_type, entity_id)

    async def list_entities(
        self,
        name: str,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: Mapping[str, Any] | None = None,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> Sequence[BaseEntity]:
        """List entities of a type with filtering, pagination, and ordering."""

        entity_type = _entity_type(name)
        return await self.backend.list(
            entity_type,
            limit=limit,
            offset=offset,
            filters=filters,
            order_by=order_by,
            order_desc=order_desc,
        )

    async def count_entities(self, name: str, filters: Mapping[str, Any] | None = None) -> int:
        """Count entities of a type matching optional filters."""

        entity_type = _entity_type(name)
        return await self.backend.count(entity_type, filters=filters)

    # ------------------------------------------------------- entity lookups

    async def get_project_by_slug(self, slug: str) -> Project | None:
        return await self.backend.get_project_by_slug(slug)

    async def require_project(self, slug: str) -> Project:
        project = await self.backend.get_project_by_slug(slug)
        if project is None:
            raise NotFoundError(f"project {slug!r} not found")
        return project

    async def get_pipeline_by_slug(self, project_id: UUID, slug: str) -> Pipeline | None:
        return await self.backend.get_pipeline_by_slug(project_id, slug)

    async def get_latest_pipeline_version(self, pipeline_id: UUID) -> PipelineVersion | None:
        return await self.backend.get_latest_pipeline_version(pipeline_id)

    async def get_pipeline_version(self, pipeline_id: UUID, version: int) -> PipelineVersion | None:
        return await self.backend.get_pipeline_version(pipeline_id, version)

    async def list_pipeline_versions(self, pipeline_id: UUID) -> Sequence[PipelineVersion]:
        return await self.backend.list_pipeline_versions(pipeline_id)

    async def get_execution_run(self, run_id: UUID) -> ExecutionRun | None:
        return await self.backend.get_execution_run(run_id)

    async def list_execution_runs(
        self,
        pipeline_id: UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExecutionRun]:
        return await self.backend.list_execution_runs(pipeline_id, status=status, limit=limit, offset=offset)

    async def get_execution_steps(self, run_id: UUID) -> Sequence[ExecutionStep]:
        return await self.backend.get_execution_steps(run_id)

    async def get_worker(self, worker_id: UUID) -> Worker | None:
        return await self.backend.get_worker(worker_id)

    async def list_workers(
        self,
        execution_class: str | None = None,
        status: str | None = None,
    ) -> Sequence[Worker]:
        return await self.backend.list_workers(execution_class, status=status)

    async def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        return await self.backend.get_schedule(schedule_id)

    async def list_schedules(
        self,
        pipeline_id: UUID | None = None,
        status: str | None = None,
        enabled: bool | None = None,
    ) -> Sequence[Schedule]:
        return await self.backend.list_schedules(pipeline_id, status=status, enabled=enabled)

    async def get_crawled_urls(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CrawledURL]:
        return await self.backend.get_crawled_urls(
            pipeline_id,
            run_id=run_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_archive_records(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ArchiveRecord]:
        return await self.backend.get_archive_records(pipeline_id, run_id=run_id, limit=limit, offset=offset)

    async def get_checkpoints(self, run_id: UUID, step_id: str | None = None) -> Sequence[Checkpoint]:
        return await self.backend.get_checkpoints(run_id, step_id=step_id)

    async def get_dead_letters(
        self,
        pipeline_id: UUID | None = None,
        run_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DeadLetter]:
        return await self.backend.get_dead_letters(pipeline_id, run_id=run_id, limit=limit, offset=offset)

    # ------------------------------------------------- operational actions

    async def submit_run(
        self,
        pipeline_id: UUID,
        pipeline_version: int,
        inputs: Mapping[str, Any],
        execution_class: str,
        run_id: UUID,
        *,
        actor: str | None = None,
    ) -> ExecutionRun:
        """Submit a run and, when a worker backend is configured, queue a job."""

        run = await self.backend.submit_run(
            pipeline_id, pipeline_version, inputs, execution_class, run_id
        )
        if self.worker_backend is not None:
            job = WorkerJob(
                kind="pipeline",
                run_id=run_id,
                pipeline_id=str(pipeline_id),
                execution_class=execution_class,
                payload=dict(inputs),
                metadata={"pipeline_version": pipeline_version},
            )
            await self.worker_backend.submit(job)
        self._audit(
            "run",
            run_id,
            actor=actor,
            target=f"pipeline:{pipeline_id}",
            extra={"pipeline_version": pipeline_version, "execution_class": execution_class},
        )
        return run

    async def cancel_run(
        self,
        run_id: UUID,
        reason: str,
        *,
        actor: str | None = None,
    ) -> ExecutionRun:
        run = await self.backend.cancel_run(run_id, reason)
        self._audit("cancel", run_id, actor=actor, target=f"execution-run:{run_id}", extra={"reason": reason})
        return run

    async def retry_run(self, run_id: UUID, *, actor: str | None = None) -> ExecutionRun:
        run = await self.backend.retry_run(run_id)
        self._audit("retry", run_id, actor=actor, target=f"execution-run:{run_id}")
        return run

    async def pause_schedule(self, schedule_id: UUID, *, actor: str | None = None) -> Schedule:
        schedule = await self.backend.pause_schedule(schedule_id)
        self._audit("pause", schedule_id, actor=actor, target=f"schedule:{schedule_id}")
        return schedule

    async def resume_schedule(self, schedule_id: UUID, *, actor: str | None = None) -> Schedule:
        schedule = await self.backend.resume_schedule(schedule_id)
        self._audit("resume", schedule_id, actor=actor, target=f"schedule:{schedule_id}")
        return schedule

    async def disable_worker(self, worker_id: UUID, *, actor: str | None = None) -> Worker:
        worker = await self.backend.disable_worker(worker_id)
        self._audit("disable", worker_id, actor=actor, target=f"worker:{worker_id}")
        return worker

    async def replay_dead_letter(
        self,
        dead_letter_id: UUID,
        keep_original: bool = True,
        *,
        actor: str | None = None,
    ) -> ExecutionRun:
        run = await self.backend.replay_dead_letter(dead_letter_id, keep_original)
        self._audit(
            "replay",
            dead_letter_id,
            actor=actor,
            target=f"dead-letter:{dead_letter_id}",
            extra={"keep_original": keep_original},
        )
        return run

    async def discard_dead_letter(
        self,
        dead_letter_id: UUID,
        *,
        actor: str | None = None,
    ) -> bool:
        discarded = await self.backend.discard_dead_letter(dead_letter_id)
        self._audit("discard", dead_letter_id, actor=actor, target=f"dead-letter:{dead_letter_id}")
        return discarded

    # --------------------------------------------------- pipeline documents

    async def materialize_pipeline(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        pipeline: CorePipeline,
        metadata: Mapping[str, Any] | None = None,
        notes: str = "",
    ) -> tuple[Pipeline, PipelineVersion]:
        """Materialize a core pipeline as a new managed, versioned pipeline."""

        project = await self.require_project(project_slug)
        raw = serialize_pipeline_definition(pipeline)
        digest = content_hash(raw)
        blob_key = _definition_blob_key(project_slug, pipeline_slug, 1)
        self.blob_store.put_bytes(blob_key, raw)
        return await self.backend.materialize_pipeline(
            project_id=project.id,
            slug=pipeline_slug,
            name=pipeline.id,
            definition_ref=blob_key,
            definition_hash=digest,
            definition_format="json",
            metadata=dict(metadata or {}),
        )

    async def update_pipeline_definition(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        pipeline: CorePipeline,
        metadata: Mapping[str, Any] | None = None,
        notes: str = "",
    ) -> tuple[Pipeline, PipelineVersion]:
        """Update a managed pipeline's definition, creating a new version."""

        project = await self.require_project(project_slug)
        managed = await self.backend.get_pipeline_by_slug(project.id, pipeline_slug)
        if managed is None:
            raise NotFoundError(f"pipeline {project_slug}/{pipeline_slug} not found")
        next_version = managed.current_version_number + 1
        raw = serialize_pipeline_definition(pipeline)
        digest = content_hash(raw)
        blob_key = _definition_blob_key(project_slug, pipeline_slug, next_version)
        self.blob_store.put_bytes(blob_key, raw)
        return await self.backend.update_pipeline_definition(
            pipeline_id=managed.id,
            definition_ref=blob_key,
            definition_hash=digest,
            definition_format="json",
            metadata=dict(metadata or {}),
        )

    async def load_pipeline_definition(self, version: PipelineVersion) -> CorePipeline:
        """Load a pipeline definition from its blob reference."""

        payload = self.blob_store.get_bytes(version.definition_ref)
        if payload is None:
            raise NotFoundError(version.definition_ref)
        return deserialize_pipeline_definition(payload)

    async def pipeline_document(self, pipeline: Pipeline) -> dict[str, Any]:
        """Return a JSON-serialisable document for dashboards and APIs."""

        current = await self.backend.get_pipeline_version(pipeline.id, pipeline.current_version_number)
        if current is None:
            latest = await self.backend.get_latest_pipeline_version(pipeline.id)
        else:
            latest = current
        return {
            "project_id": str(pipeline.project_id),
            "slug": pipeline.slug,
            "name": pipeline.name,
            "source_ref": pipeline.source_ref,
            "source_hash": pipeline.source_hash,
            "definition_ref": pipeline.definition_ref,
            "current_version": pipeline.current_version_number,
            "current_version_hash": pipeline.current_version_hash,
            "metadata": pipeline.metadata,
            "version": None if latest is None else await self.version_document(latest),
        }

    async def version_document(self, version: PipelineVersion) -> dict[str, Any]:
        """Return a JSON-serialisable document for a pipeline version."""

        payload = self.blob_store.get_bytes(version.definition_ref)
        preview = payload.decode("utf-8") if payload is not None else ""
        return {
            "pipeline_id": str(version.pipeline_id),
            "version": version.version,
            "definition_ref": version.definition_ref,
            "definition_hash": version.definition_hash,
            "definition_format": version.definition_format,
            "metadata": version.metadata,
            "definition_preview": preview,
        }
