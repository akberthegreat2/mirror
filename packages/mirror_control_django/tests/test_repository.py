"""Repository tests for pipeline materialization.

These exercise the real composition path: the repository delegates to
``ControlService`` over the ``mirror_database`` SQLite backend, which persists
to the same database the unmanaged Django models read from.
"""

from __future__ import annotations

from pathlib import Path

from mirror_control_django import models
from mirror_control_django.repository import (
    ControlPlaneRepository,
    deserialize_pipeline_definition,
)
from mirror_core.pipeline import Pipeline, Step
from mirror_core.storage import FileSystemBlobStore


def _repo(tmp_path: Path) -> ControlPlaneRepository:
    return ControlPlaneRepository(blob_store=FileSystemBlobStore(tmp_path / "blobs"))


def test_materialize_pipeline_roundtrip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    pipeline = Pipeline(
        id="crawl-site",
        steps=[Step(id="crawl", capability="crawl")],
        inputs={"url": "string"},
    )

    managed, version = repo.materialize_pipeline(
        project_slug="demo",
        pipeline_slug="crawl-site",
        pipeline=pipeline,
        metadata={"owner": "alice"},
    )

    assert managed.slug == "crawl-site"
    assert version.version == 1
    blob = repo.blob_store.get_bytes(version.definition_ref)
    assert blob is not None
    restored = deserialize_pipeline_definition(blob)
    assert restored.id == pipeline.id

    # The write landed in Mirror's database, visible to the unmanaged model.
    assert models.Pipeline.objects.count() == 1
    assert models.Pipeline.objects.get(slug="crawl-site").current_version_number == 1


def test_managed_pipeline_versions_are_immutable(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    pipeline = Pipeline(id="managed", steps=[Step(id="one", capability="crawl")])

    _managed, first = repo.materialize_pipeline(
        project_slug="demo",
        pipeline_slug="managed",
        pipeline=pipeline,
    )
    second_pipeline = Pipeline(
        id="managed",
        steps=[Step(id="one", capability="fetch")],
    )
    _managed, second = repo.materialize_pipeline(
        project_slug="demo",
        pipeline_slug="managed",
        pipeline=second_pipeline,
    )

    assert first.version == 1
    assert second.version == 2
    assert first.definition_ref != second.definition_ref

    # Only the pipeline and its versions were touched: no stray rows.
    assert models.Pipeline.objects.count() == 1
    assert models.PipelineVersion.objects.count() == 2
    # The pipeline points at the latest immutable version.
    latest = models.PipelineVersion.objects.order_by("-version").first()
    assert latest.definition_ref == second.definition_ref
    assert _managed.current_version_number == 2


def test_code_pipeline_is_registered_read_only(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    pipeline = Pipeline(id="code", steps=[Step(id="one", capability="fetch")])

    managed, version = repo.register_code_pipeline(
        project_slug="demo",
        pipeline_slug="code",
        pipeline=pipeline,
        source_ref="git@example:repo.git",
        source_hash_value="abc123",
    )

    assert managed.is_read_only is True
    assert version.version == 1
    assert managed.source_ref == "git@example:repo.git"
    assert managed.source_hash == "abc123"
    assert models.Pipeline.objects.get(slug="code").definition_ref is not None
