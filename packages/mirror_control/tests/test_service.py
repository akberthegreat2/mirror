"""Integration tests for ControlService against real SQLite + filesystem blobs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from mirror_control.errors import NotFoundError, UnknownEntityError
from mirror_control.manifest import CONTROL_PLANE_MANIFEST
from mirror_control.service import ControlService
from mirror_core.pipeline import Pipeline as CorePipeline
from mirror_core.pipeline import Step
from mirror_core.storage import FileSystemBlobStore
from mirror_database.models import (
    Project,
    ScheduleStatus,
    Worker,
    WorkerStatus,
)
from mirror_database_sqlite.backend import SQLiteBackend


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _core_pipeline(pipeline_id: str = "demo-ingest") -> CorePipeline:
    return CorePipeline(
        id=pipeline_id,
        version="1.0",
        steps=[
            Step(
                id="fetch",
                capability="fetch",
                provider="httpx",
                input={"url": "https://example.com"},
            )
        ],
        inputs={},
    )


@pytest.fixture
async def service(tmp_path: Path):
    backend = SQLiteBackend("sqlite:///:memory:")
    await backend.initialize()
    blob_store = FileSystemBlobStore(tmp_path / "blobs")
    svc = ControlService(backend, blob_store)
    yield svc
    await backend.close()


async def _make_project(svc: ControlService) -> Project:
    now = _now()
    project = await svc.create_entity(
        "project",
        {
            "id": uuid4(),
            "created_at": now,
            "updated_at": now,
            "slug": "demo",
            "name": "Demo Project",
            "metadata": {"owner": "tests"},
        },
    )
    assert isinstance(project, Project)
    return project


# ------------------------------------------------------------------- manifest


def test_manifest_covers_backend_entity_names() -> None:
    names = CONTROL_PLANE_MANIFEST.entity_names()
    assert "project" in names
    assert "pipeline" in names
    assert "pipeline-version" in names
    assert "execution-run" in names
    assert "execution-step" in names
    assert "worker" in names
    assert "schedule" in names
    assert "crawled-url" in names
    assert "archive-record" in names
    assert "checkpoint" in names
    assert "dead-letter" in names


def test_manifest_is_framework_neutral() -> None:
    # No interface technology may leak into the manifest.
    assert "django" not in repr(CONTROL_PLANE_MANIFEST).lower()
    assert "drf" not in repr(CONTROL_PLANE_MANIFEST).lower()


# ----------------------------------------------------------------------- CRUD


async def test_create_get_update_delete_roundtrip(service: ControlService) -> None:
    project = await _make_project(service)

    fetched = await service.get_entity("project", project.id)
    assert isinstance(fetched, Project)
    assert fetched.slug == "demo"

    updated = await service.update_entity(
        "project", project.id, {"name": "Renamed Project"}
    )
    assert isinstance(updated, Project)
    assert updated.name == "Renamed Project"

    listed = await service.list_entities("project")
    assert len(listed) == 1

    assert await service.count_entities("project") == 1
    assert await service.delete_entity("project", project.id) is True
    assert await service.count_entities("project") == 0


async def test_get_entity_missing_raises(service: ControlService) -> None:
    with pytest.raises(NotFoundError):
        await service.get_entity("project", uuid4())


async def test_update_entity_missing_raises(service: ControlService) -> None:
    with pytest.raises(NotFoundError):
        await service.update_entity("project", uuid4(), {"name": "x"})


async def test_unknown_entity_name_raises(service: ControlService) -> None:
    with pytest.raises(UnknownEntityError):
        await service.create_entity("definitely-not-an-entity", {"id": uuid4()})


# ------------------------------------------------------- operational actions


async def test_schedule_pause_resume(service: ControlService) -> None:
    project = await _make_project(service)
    now = _now()
    pipeline = await service.create_entity(
        "pipeline",
        {
            "id": uuid4(),
            "created_at": now,
            "updated_at": now,
            "project_id": project.id,
            "slug": "ingest",
            "name": "Ingest",
        },
    )
    schedule = await service.create_entity(
        "schedule",
        {
            "id": uuid4(),
            "created_at": now,
            "updated_at": now,
            "name": "daily",
            "pipeline_id": pipeline.id,
            "cron": "0 6 * * *",
        },
    )

    paused = await service.pause_schedule(schedule.id)
    assert paused.status == ScheduleStatus.PAUSED
    resumed = await service.resume_schedule(schedule.id)
    assert resumed.status == ScheduleStatus.ENABLED


async def test_disable_worker(service: ControlService) -> None:
    now = _now()
    worker_id = uuid4()
    worker = await service.create_entity(
        "worker",
        {
            "id": uuid4(),
            "created_at": now,
            "updated_at": now,
            "worker_id": worker_id,
            "backend": "celery",
            "execution_class": "default",
        },
    )
    assert isinstance(worker, Worker)
    # Backends key workers by their logical worker_id field, not the row id.
    disabled = await service.disable_worker(worker_id)
    assert disabled.status == WorkerStatus.DISABLED


# -------------------------------------------------- pipeline blob documents


async def test_materialize_and_update_pipeline_roundtrip(
    service: ControlService,
) -> None:
    project = await _make_project(service)
    pipeline, version = await service.materialize_pipeline(
        project_slug=project.slug,
        pipeline_slug="ingest",
        pipeline=_core_pipeline(),
        metadata={"env": "test"},
    )
    assert pipeline.current_version_number == 1
    assert version.version == 1
    assert version.definition_hash

    loaded = await service.load_pipeline_definition(version)
    assert loaded.id == "demo-ingest"

    doc = await service.version_document(version)
    assert "fetch" in doc["definition_preview"]

    pipeline2, version2 = await service.update_pipeline_definition(
        project_slug=project.slug,
        pipeline_slug="ingest",
        pipeline=_core_pipeline("demo-ingest-v2"),
        notes="add step",
    )
    assert pipeline2.current_version_number == 2
    assert version2.version == 2
    assert version2.definition_ref != version.definition_ref

    versions = await service.list_pipeline_versions(pipeline.id)
    assert [v.version for v in versions] == [1, 2]

    pdoc = await service.pipeline_document(pipeline2)
    assert pdoc["current_version"] == 2
    assert pdoc["slug"] == "ingest"


async def test_materialize_missing_project_raises(service: ControlService) -> None:
    with pytest.raises(NotFoundError):
        await service.materialize_pipeline(
            project_slug="missing",
            pipeline_slug="ingest",
            pipeline=_core_pipeline(),
        )
