"""Repository helpers for the Mirror control plane.

This module is a thin adapter over the framework-neutral
:class:`mirror_control.ControlService`. It exists so existing Django/DRF
callers keep a synchronous, convenience-shaped API; all control-plane writes
delegate to the service and therefore never bypass Mirror semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from mirror_control.service import (
    content_hash,
    default_blob_root,
    default_blob_store,
    deserialize_pipeline_definition,
    serialize_pipeline_definition,
)
from mirror_core.pipeline import Pipeline as CorePipeline
from mirror_core.storage import BlobStore
from mirror_database.models import Pipeline as DatabasePipeline
from mirror_database.models import Project as DatabaseProject

from mirror_control_django.service import DjangoControlService

DEFAULT_BLOB_ENV = "MIRROR_CONTROL_BLOB_ROOT"
DEFAULT_BLOB_DIR = ".mirror/control-plane/blobs"
MANAGED_PIPELINE_ORIGIN = "managed"


@dataclass(frozen=True, slots=True)
class PipelineArtifact:
    """Metadata for one materialized pipeline version."""

    project_slug: str
    pipeline_slug: str
    version: int
    definition_ref: str
    definition_hash: str
    origin: str
    read_only: bool


class ControlPlaneRepository:
    """Synchronous convenience facade over ``ControlService``.

    Keeps the historical API (``ensure_project``, ``materialize_pipeline``,
    ``materialize_definition``, ``register_code_pipeline``, ...) used by the
    DRF interface and admin while routing every write through the service.
    """

    def __init__(
        self,
        blob_store: BlobStore | None = None,
        service: DjangoControlService | None = None,
    ) -> None:
        self.service = service or DjangoControlService(blob_store=blob_store)
        self.blob_store = blob_store or default_blob_store()

    # ------------------------------------------------------------------ read

    def get_project_by_slug(self, slug: str) -> Any:
        return self.service.get_project_by_slug(slug)

    def get_pipeline_by_slug(self, project_id: UUID, slug: str) -> Any:
        return self.service.get_pipeline_by_slug(project_id, slug)

    # ----------------------------------------------------------------- write

    def ensure_project(
        self,
        *,
        slug: str,
        name: str | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        project = cast(DatabaseProject | None, self.service.get_project_by_slug(slug))
        if project is not None:
            updates: dict[str, Any] = {"updated_at": project.updated_at}
            if name is not None and project.name != name:
                updates["name"] = name
            if description and getattr(project, "description", "") != description:
                updates["description"] = description
            if metadata is not None and project.metadata != metadata:
                updates["metadata"] = metadata
            if len(updates) > 1:
                return self.service.update_entity("project", project.id, updates)
            return project
        payload: dict[str, Any] = {
            "slug": slug,
            "name": name or slug.replace("-", " ").title(),
            "metadata": metadata or {},
        }
        if description:
            payload["description"] = description
        return self.service.create_entity("project", payload)

    def get_or_create_pipeline(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        name: str | None = None,
        origin: str = MANAGED_PIPELINE_ORIGIN,
        read_only: bool = False,
        source_ref: str = "",
        source_hash_value: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        project = self.ensure_project(slug=project_slug)
        existing = cast(
            DatabasePipeline | None,
            self.service.get_pipeline_by_slug(project.id, pipeline_slug),
        )
        if existing is not None:
            updates: dict[str, Any] = {"updated_at": existing.updated_at}
            if name is not None and existing.name != name:
                updates["name"] = name
            if existing.origin != origin:
                updates["origin"] = origin
            if existing.is_read_only != read_only:
                updates["is_read_only"] = read_only
            if existing.source_ref != source_ref:
                updates["source_ref"] = source_ref
            if existing.source_hash != source_hash_value:
                updates["source_hash"] = source_hash_value
            if metadata is not None and existing.metadata != metadata:
                updates["metadata"] = metadata
            if len(updates) > 1:
                return self.service.update_entity("pipeline", existing.id, updates)
            return existing
        return self.service.create_entity(
            "pipeline",
            {
                "project_id": project.id,
                "slug": pipeline_slug,
                "name": name or pipeline_slug.replace("-", " ").title(),
                "origin": origin,
                "is_read_only": read_only,
                "source_ref": source_ref or None,
                "source_hash": source_hash_value or None,
                "metadata": metadata or {},
            },
        )

    def register_code_pipeline(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        pipeline: CorePipeline,
        source_ref: str,
        source_hash_value: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Any, Any]:
        """Materialize a code pipeline as a read-only versioned document."""

        raw = serialize_pipeline_definition(pipeline)
        blob_key = self._definition_blob_key(project_slug, pipeline_slug, 1)
        self.blob_store.put_bytes(blob_key, raw)
        artifact = self.get_or_create_pipeline(
            project_slug=project_slug,
            pipeline_slug=pipeline_slug,
            name=pipeline.id,
            origin="code",
            read_only=True,
            source_ref=source_ref,
            source_hash_value=source_hash_value,
            metadata=metadata,
        )
        version = self.service.create_entity(
            "pipeline-version",
            {
                "pipeline_id": artifact.id,
                "version": 1,
                "definition_ref": blob_key,
                "definition_hash": content_hash(raw),
                "definition_format": "json",
                "metadata": metadata or {},
            },
        )
        self.service.update_entity(
            "pipeline",
            artifact.id,
            {
                "definition_ref": blob_key,
                "current_version_number": 1,
                "current_version_hash": content_hash(raw),
            },
        )
        return artifact, version

    def materialize_pipeline(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        pipeline: CorePipeline,
        metadata: dict[str, Any] | None = None,
        notes: str = "",
    ) -> tuple[Any, Any]:
        """Create or update a managed pipeline artifact from a core pipeline."""

        self.ensure_project(slug=project_slug, metadata=metadata)
        project = cast(DatabaseProject, self.service.get_project_by_slug(project_slug))
        existing = self.service.get_pipeline_by_slug(project.id, pipeline_slug)
        if existing is None:
            return self.service.materialize_pipeline(
                project_slug=project_slug,
                pipeline_slug=pipeline_slug,
                pipeline=pipeline,
                metadata=metadata,
                notes=notes,
            )
        return self.service.update_pipeline_definition(
            project_slug=project_slug,
            pipeline_slug=pipeline_slug,
            pipeline=pipeline,
            metadata=metadata,
            notes=notes,
        )

    def materialize_definition(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        definition: bytes,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
        notes: str = "",
    ) -> tuple[Any, Any]:
        """Validate and store a new immutable managed pipeline version."""

        pipeline = deserialize_pipeline_definition(definition)
        return self.materialize_pipeline(
            project_slug=project_slug,
            pipeline_slug=pipeline_slug,
            pipeline=pipeline,
            metadata=metadata,
            notes=notes,
        )

    def load_pipeline_definition(self, version: Any) -> CorePipeline:
        """Load a pipeline definition from its blob reference."""

        return self.service.load_pipeline_definition(version)

    def pipeline_document(self, pipeline: Any) -> dict[str, Any]:
        """Return a JSON-serialisable document for dashboards and APIs."""

        return self.service.pipeline_document(pipeline)

    def version_document(self, version: Any) -> dict[str, Any]:
        """Return a JSON-serialisable document for a pipeline version."""

        return self.service.version_document(version)

    def _definition_blob_key(self, project_slug: str, pipeline_slug: str, version: int) -> str:
        return f"pipelines/{project_slug}/{pipeline_slug}/v{version}.json"


__all__ = [
    "MANAGED_PIPELINE_ORIGIN",
    "ControlPlaneRepository",
    "PipelineArtifact",
    "content_hash",
    "default_blob_root",
    "default_blob_store",
    "deserialize_pipeline_definition",
    "serialize_pipeline_definition",
]
