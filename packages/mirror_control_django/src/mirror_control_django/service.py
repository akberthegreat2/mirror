"""Synchronous facade over :class:`mirror_control.ControlService` for Django.

Django's admin/request cycle is synchronous. This module wraps the async
framework-neutral service so Django views and admin actions can call it
directly. It is a thin adapter: all control-plane behavior still lives in
``ControlService`` and runs against the ``mirror_database`` backend.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from django.conf import settings
from mirror_control.service import ControlService, default_blob_store
from mirror_database.models import BaseEntity
from mirror_database.protocol import DatabaseBackend


def _default_backend() -> DatabaseBackend:
    """Build the database backend for the configured Mirror database alias."""

    from mirror_database_sqlite.backend import SQLiteBackend

    alias = getattr(settings, "MIRROR_CONTROL_DB_ALIAS", "mirror")
    name = settings.DATABASES[alias]["NAME"]
    backend = SQLiteBackend(f"sqlite:///{name}")
    asyncio.run(backend.initialize())
    return backend


def _run(coro: Any) -> Any:
    """Run a ControlService coroutine to completion in the sync Django context."""

    return asyncio.run(coro)


class DjangoControlService:
    """Synchronous adapter exposing the framework-neutral control service."""

    def __init__(
        self,
        backend: DatabaseBackend | None = None,
        blob_store: Any | None = None,
    ) -> None:
        self._service = ControlService(backend or _default_backend(), blob_store or default_blob_store())

    @property
    def service(self) -> ControlService:
        return self._service

    # ------------------------------------------------------------------ CRUD

    def create_entity(self, name: str, data: Mapping[str, Any]) -> BaseEntity:
        payload = dict(data)
        now = datetime.now(timezone.utc)
        if not payload.get("id"):
            payload["id"] = uuid4()
        if not payload.get("created_at"):
            payload["created_at"] = now
        if not payload.get("updated_at"):
            payload["updated_at"] = now
        return _run(self._service.create_entity(name, payload))

    def get_entity(self, name: str, entity_id: UUID) -> BaseEntity:
        return _run(self._service.get_entity(name, entity_id))

    def update_entity(self, name: str, entity_id: UUID, data: Mapping[str, Any]) -> BaseEntity:
        payload = dict(data)
        payload.setdefault("updated_at", datetime.now(timezone.utc))
        return _run(self._service.update_entity(name, entity_id, payload))

    def delete_entity(self, name: str, entity_id: UUID) -> bool:
        return _run(self._service.delete_entity(name, entity_id))

    def list_entities(
        self,
        name: str,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: Mapping[str, Any] | None = None,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> Sequence[BaseEntity]:
        return _run(
            self._service.list_entities(
                name,
                limit=limit,
                offset=offset,
                filters=filters,
                order_by=order_by,
                order_desc=order_desc,
            )
        )

    # --------------------------------------------------------- lookups

    def get_project_by_slug(self, slug: str) -> BaseEntity | None:
        return _run(self._service.get_project_by_slug(slug))

    def get_pipeline_by_slug(self, project_id: UUID, slug: str) -> BaseEntity | None:
        return _run(self._service.get_pipeline_by_slug(project_id, slug))

    # ------------------------------------------------- operational actions

    def pause_schedule(self, schedule_id: UUID) -> BaseEntity:
        return _run(self._service.pause_schedule(schedule_id))

    def resume_schedule(self, schedule_id: UUID) -> BaseEntity:
        return _run(self._service.resume_schedule(schedule_id))

    def disable_worker(self, worker_id: UUID) -> BaseEntity:
        return _run(self._service.disable_worker(worker_id))

    def cancel_run(self, run_id: UUID, reason: str) -> BaseEntity:
        return _run(self._service.cancel_run(run_id, reason))

    def retry_run(self, run_id: UUID) -> BaseEntity:
        return _run(self._service.retry_run(run_id))

    # ------------------------------------------------- pipeline documents

    def materialize_pipeline(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        pipeline: Any,
        metadata: Mapping[str, Any] | None = None,
        notes: str = "",
    ) -> tuple[Any, Any]:
        return _run(
            self._service.materialize_pipeline(
                project_slug=project_slug,
                pipeline_slug=pipeline_slug,
                pipeline=pipeline,
                metadata=metadata,
                notes=notes,
            )
        )

    def update_pipeline_definition(
        self,
        *,
        project_slug: str,
        pipeline_slug: str,
        pipeline: Any,
        metadata: Mapping[str, Any] | None = None,
        notes: str = "",
    ) -> tuple[Any, Any]:
        return _run(
            self._service.update_pipeline_definition(
                project_slug=project_slug,
                pipeline_slug=pipeline_slug,
                pipeline=pipeline,
                metadata=metadata,
                notes=notes,
            )
        )

    def load_pipeline_definition(self, version: Any) -> Any:
        return _run(self._service.load_pipeline_definition(version))

    def pipeline_document(self, pipeline: Any) -> dict[str, Any]:
        return _run(self._service.pipeline_document(pipeline))

    def version_document(self, version: Any) -> dict[str, Any]:
        return _run(self._service.version_document(version))

    def list_pipeline_versions(self, pipeline_id: UUID) -> Sequence[Any]:
        return _run(self._service.list_pipeline_versions(pipeline_id))


__all__ = ["DjangoControlService"]
