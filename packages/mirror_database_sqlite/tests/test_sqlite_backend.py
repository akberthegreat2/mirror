"""Integration tests for the SQLite database backend (real SQLite, in-memory)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from mirror_database.models import (
    ArchiveRecord,
    Checkpoint,
    CrawledURL,
    CrawlStatus,
    DeadLetter,
    DeadLetterTerminalStatus,
    ExecutionRun,
    ExecutionStatus,
    ExecutionStep,
    Pipeline,
    PipelineVersion,
    Project,
    ProjectStatus,
    Schedule,
    ScheduleStatus,
    StepStatus,
    Worker,
    WorkerStatus,
)
from mirror_database_sqlite.backend import NotFoundError, SQLiteBackend


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
async def db():
    backend = SQLiteBackend("sqlite:///:memory:")
    await backend.initialize()
    yield backend
    await backend.close()


async def _make_project(db: SQLiteBackend) -> Project:
    now = _now()
    project = Project(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        slug="demo",
        name="Demo Project",
        status=ProjectStatus.ACTIVE,
        metadata={"owner": "tests"},
    )
    return await db.create(project)


async def _make_pipeline(db: SQLiteBackend, project_id) -> Pipeline:
    now = _now()
    pipeline = Pipeline(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        project_id=project_id,
        slug="ingest",
        name="Ingest",
        current_version_number=1,
    )
    return await db.create(pipeline)


async def _make_run(db: SQLiteBackend, pipeline_id, *, status=ExecutionStatus.PENDING):
    now = _now()
    run = ExecutionRun(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        pipeline_id=pipeline_id,
        pipeline_version=1,
        run_id=uuid4(),
        status=status,
        execution_class="default",
        inputs={"url": "https://example.com"},
    )
    return await db.create(run)


# ---------------------------------------------------------------------- CRUD


async def test_project_crud_roundtrip(db: SQLiteBackend):
    project = await _make_project(db)
    fetched = await db.get("project", project.id)
    assert fetched == project
    assert isinstance(fetched, Project)
    assert fetched.metadata == {"owner": "tests"}


async def test_get_missing_returns_none(db: SQLiteBackend):
    assert await db.get("project", uuid4()) is None


async def test_delete(db: SQLiteBackend):
    project = await _make_project(db)
    assert await db.delete("project", project.id) is True
    assert await db.delete("project", project.id) is False
    assert await db.get("project", project.id) is None


async def test_update_replaces_row(db: SQLiteBackend):
    project = await _make_project(db)
    renamed = project.model_copy(update={"name": "Renamed", "updated_at": _now(), "status": ProjectStatus.ARCHIVED})
    await db.update(renamed)
    fetched = await db.get("project", project.id)
    assert fetched.name == "Renamed"
    assert fetched.status == ProjectStatus.ARCHIVED


async def test_list_with_filters_and_pagination(db: SQLiteBackend):
    for i in range(5):
        now = _now()
        project = Project(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            slug=f"p{i}",
            name=f"P{i}",
            status=ProjectStatus.ACTIVE if i % 2 == 0 else ProjectStatus.ARCHIVED,
        )
        await db.create(project)

    active = await db.list("project", filters={"status": "active"}, order_by="slug")
    assert [p.slug for p in active] == ["p0", "p2", "p4"]

    page = await db.list("project", limit=2, offset=1, order_by="slug")
    assert len(page) == 2

    assert await db.count("project", filters={"status": "archived"}) == 2


# ------------------------------------------------------- entity-specific helpers


async def test_project_and_pipeline_by_slug(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)

    assert await db.get_project_by_slug("demo") == project
    assert await db.get_project_by_slug("nope") is None
    assert await db.get_pipeline_by_slug(project.id, "ingest") == pipeline
    assert await db.get_pipeline_by_slug(project.id, "nope") is None


async def test_pipeline_versions(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    now = _now()
    v1 = PipelineVersion(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        pipeline_id=pipeline.id,
        version=1,
        definition_ref="ref://1",
        definition_hash="hash1",
    )
    v2 = v1.model_copy(
        update={
            "id": uuid4(),
            "version": 2,
            "definition_ref": "ref://2",
            "definition_hash": "hash2",
            "updated_at": _now(),
        }
    )
    await db.create(v1)
    await db.create(v2)

    assert await db.get_latest_pipeline_version(pipeline.id) == v2
    assert await db.get_pipeline_version(pipeline.id, 1) == v1
    assert await db.get_pipeline_version(pipeline.id, 99) is None
    versions = await db.list_pipeline_versions(pipeline.id)
    assert [v.version for v in versions] == [1, 2]


async def test_execution_run_lookup(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    run = await _make_run(db, pipeline.id)

    assert await db.get_execution_run(run.run_id) == run
    runs = await db.list_execution_runs(pipeline_id=pipeline.id, status="pending")
    assert runs == [run]
    runs = await db.list_execution_runs(pipeline_id=pipeline.id, status="failed")
    assert runs == []


async def test_execution_steps(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    run = await _make_run(db, pipeline.id)
    now = _now()
    step = ExecutionStep(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        run_id=run.id,
        step_id="s1",
        capability="fetch",
        provider="httpx",
        status=StepStatus.SUCCEEDED,
    )
    await db.create(step)

    steps = await db.get_execution_steps(run.id)
    assert steps == [step]


async def test_workers(db: SQLiteBackend):
    now = _now()
    worker = Worker(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        worker_id=uuid4(),
        backend="celery",
        execution_class="default",
        status=WorkerStatus.ACTIVE,
    )
    await db.create(worker)

    assert await db.get_worker(worker.worker_id) == worker
    assert await db.get_worker(uuid4()) is None
    listed = await db.list_workers(execution_class="default", status="active")
    assert listed == [worker]


async def test_schedules(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    now = _now()
    schedule = Schedule(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        name="daily",
        pipeline_id=pipeline.id,
        cron="0 3 * * *",
        enabled=True,
        status=ScheduleStatus.ENABLED,
    )
    await db.create(schedule)

    assert await db.get_schedule(schedule.id) == schedule
    listed = await db.list_schedules(pipeline_id=pipeline.id, enabled=True)
    assert listed == [schedule]
    listed = await db.list_schedules(pipeline_id=pipeline.id, status="paused")
    assert listed == []


async def test_crawled_urls_and_archive_records(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    run = await _make_run(db, pipeline.id)
    now = _now()

    url = CrawledURL(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        pipeline_id=pipeline.id,
        run_id=run.id,
        url="https://example.com/a",
        status=CrawlStatus.DISCOVERED,
        discovered_at=now,
    )
    await db.create(url)
    got = await db.get_crawled_urls(pipeline_id=pipeline.id, run_id=run.id)
    assert got == [url]

    record = ArchiveRecord(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        pipeline_id=pipeline.id,
        run_id=run.id,
        resource_key="a.html",
        storage_ref="s3://bucket/a.html",
        content_hash="abc",
    )
    await db.create(record)
    assert await db.get_archive_records(pipeline_id=pipeline.id) == [record]


async def test_checkpoints(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    run = await _make_run(db, pipeline.id)
    now = _now()
    c1 = Checkpoint(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        run_id=run.id,
        step_id="fetch",
        payload={"done": 1},
    )
    c2 = c1.model_copy(update={"id": uuid4(), "step_id": "crawl", "updated_at": _now()})
    await db.create(c1)
    await db.create(c2)

    all_cps = await db.get_checkpoints(run.id)
    assert len(all_cps) == 2
    fetch_cps = await db.get_checkpoints(run.id, step_id="fetch")
    assert fetch_cps == [c1]


async def test_dead_letters(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    run = await _make_run(db, pipeline.id)
    now = _now()
    dead = DeadLetter(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        run_id=run.id,
        pipeline_id=pipeline.id,
        step_id="fetch",
        terminal_status=DeadLetterTerminalStatus.FAILED,
        reason="5xx",
        original_inputs={"url": "https://example.com"},
    )
    await db.create(dead)
    assert await db.get_dead_letters(pipeline_id=pipeline.id) == [dead]


# ------------------------------------------------------------ operational transitions


async def test_submit_and_cancel_run(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    run_id = uuid4()
    run = await db.submit_run(pipeline.id, 1, {"url": "https://example.com"}, "default", run_id)
    assert run.status == ExecutionStatus.PENDING
    assert run.run_id == run_id

    cancelled = await db.cancel_run(run_id, "operator request")
    assert cancelled.status == ExecutionStatus.CANCELLED
    assert cancelled.error == "operator request"
    assert cancelled.finished_at is not None


async def test_cancel_missing_run_raises(db: SQLiteBackend):
    with pytest.raises(NotFoundError):
        await db.cancel_run(uuid4(), "nope")


async def test_retry_run(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    failed = await _make_run(db, pipeline.id, status=ExecutionStatus.FAILED)

    retried = await db.retry_run(failed.run_id)
    assert retried.run_id != failed.run_id
    assert retried.status == ExecutionStatus.PENDING
    assert retried.inputs == failed.inputs
    assert retried.pipeline_id == failed.pipeline_id
    assert retried.retry_count == 1


async def test_schedule_pause_resume(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    now = _now()
    schedule = Schedule(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        name="daily",
        pipeline_id=pipeline.id,
        cron="0 3 * * *",
    )
    await db.create(schedule)

    paused = await db.pause_schedule(schedule.id)
    assert paused.status == ScheduleStatus.PAUSED
    assert paused.enabled is False

    resumed = await db.resume_schedule(schedule.id)
    assert resumed.status == ScheduleStatus.ENABLED
    assert resumed.enabled is True


async def test_disable_worker(db: SQLiteBackend):
    now = _now()
    worker = Worker(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        worker_id=uuid4(),
        backend="celery",
        execution_class="default",
    )
    await db.create(worker)
    disabled = await db.disable_worker(worker.worker_id)
    assert disabled.status == WorkerStatus.DISABLED


async def test_dead_letter_replay_and_discard(db: SQLiteBackend):
    project = await _make_project(db)
    pipeline = await _make_pipeline(db, project.id)
    run = await _make_run(db, pipeline.id)
    now = _now()
    dead = DeadLetter(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        run_id=run.id,
        pipeline_id=pipeline.id,
        step_id="fetch",
        terminal_status=DeadLetterTerminalStatus.FAILED,
        reason="5xx",
        original_inputs={"url": "https://example.com"},
    )
    await db.create(dead)

    new_run = await db.replay_dead_letter(dead.id, keep_original=True)
    assert new_run.pipeline_id == pipeline.id
    assert new_run.inputs == {"url": "https://example.com"}
    assert new_run.status == ExecutionStatus.PENDING
    # keep_original=True leaves the dead letter untouched
    still_failed = await db.get_dead_letters(pipeline_id=pipeline.id)
    assert still_failed[0].terminal_status == DeadLetterTerminalStatus.FAILED

    assert await db.discard_dead_letter(dead.id) is True
    discarded = await db.get_dead_letters(pipeline_id=pipeline.id)
    assert discarded[0].terminal_status == DeadLetterTerminalStatus.DISCARDED
    assert await db.discard_dead_letter(dead.id) is False


async def test_materialize_and_update_pipeline(db: SQLiteBackend):
    project = await _make_project(db)

    pipeline, version = await db.materialize_pipeline(
        project.id,
        "ingest",
        "Ingest",
        "ref://v1",
        "hash1",
        "json",
        source_ref="ref://source",
        metadata={"tier": 1},
    )
    assert pipeline.current_version_number == 1
    assert version.version == 1
    assert await db.get_pipeline_by_slug(project.id, "ingest") == pipeline
    assert await db.get_latest_pipeline_version(pipeline.id) == version

    updated, new_version = await db.update_pipeline_definition(pipeline.id, "ref://v2", "hash2", "yaml", metadata={"tier": 2})
    assert updated.current_version_number == 2
    assert new_version.version == 2
    assert new_version.definition_format.value == "yaml"
    versions = await db.list_pipeline_versions(pipeline.id)
    assert [v.version for v in versions] == [1, 2]


async def test_transaction_rollback(db: SQLiteBackend):
    project = await _make_project(db)
    with pytest.raises(RuntimeError):
        async with await db.transaction():
            await _make_pipeline(db, project.id)
            raise RuntimeError("boom")
    # The pipeline insert was rolled back
    assert await db.list("pipeline") == []


async def test_transaction_commit(db: SQLiteBackend):
    project = await _make_project(db)
    async with await db.transaction():
        await _make_pipeline(db, project.id)
    assert len(await db.list("pipeline")) == 1


async def test_health_check(db: SQLiteBackend):
    assert await db.health_check() is True


async def test_persistent_file_backend(tmp_path):
    db_file = tmp_path / "mirror.db"
    backend = SQLiteBackend(f"sqlite:///{db_file}")
    await backend.initialize()
    project = await _make_project(backend)
    await backend.close()

    # Reopen the same file and confirm the row survived
    backend2 = SQLiteBackend(f"sqlite:///{db_file}")
    await backend2.initialize()
    fetched = await backend2.get("project", project.id)
    assert fetched == project
    await backend2.close()
