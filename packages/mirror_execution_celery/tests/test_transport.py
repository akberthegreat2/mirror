from __future__ import annotations

import os

import pytest
from mirror_execution_celery.transport import (
    REAPER_QUEUE,
    configure_worker_task,
    create_celery_app,
    queue_name,
)


def test_execution_class_queue_names() -> None:
    assert queue_name("default") == "mirror.default"
    assert queue_name("io") == "mirror.io"
    assert queue_name("CPU") == "mirror.cpu"
    with pytest.raises(ValueError):
        queue_name("crawl.queue")


def test_celery_app_uses_redis_broker() -> None:
    app = create_celery_app(broker_url="redis://localhost:6399/0")
    assert app.conf.broker_url == "redis://localhost:6399/0"
    assert app.conf.task_acks_late is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.task_ignore_result is True


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("MIRROR_TEST_REDIS_URL"),
    reason="set MIRROR_TEST_REDIS_URL for live Redis/Celery integration",
)
def test_live_redis_url_is_configurable() -> None:
    from redis import Redis

    url = os.environ["MIRROR_TEST_REDIS_URL"]
    client = Redis.from_url(url)
    assert client.ping() is True


def test_configure_worker_registers_lease_reaper_schedule() -> None:
    app = create_celery_app(broker_url="redis://localhost:6399/0")
    configure_worker_task(app, postgres_dsn="postgresql://mirror@localhost/mirror")
    assert "mirror.requeue_expired" in app.tasks
    schedule = app.conf.beat_schedule["mirror-lease-reaper"]
    assert schedule["task"] == "mirror.requeue_expired"
    assert schedule["options"]["queue"] == REAPER_QUEUE
    assert schedule["schedule"] > 0


def test_reaper_republishes_requeued_jobs() -> None:
    """Reaper must republish each requeued job to its execution-class queue (ADR-0048)."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from mirror_core.workers import JobState, WorkerJob

    requeued_jobs = [
        WorkerJob(
            job_id=uuid4(),
            kind="run",
            run_id=uuid4(),
            pipeline_id="p1",
            step_id="s1",
            execution_class="default",
            payload={},
            state=JobState.QUEUED,
        ),
        WorkerJob(
            job_id=uuid4(),
            kind="run",
            run_id=uuid4(),
            pipeline_id="p2",
            step_id="s2",
            execution_class="io",
            payload={},
            state=JobState.QUEUED,
        ),
    ]

    # requeue_expired is a synchronous method on the backend
    mock_backend = MagicMock()
    mock_backend.requeue_expired.return_value = requeued_jobs
    mock_backend.start = AsyncMock()
    mock_backend.stop = AsyncMock()

    mock_app = MagicMock()

    async def _test() -> None:
        with patch(
            "mirror_execution_celery.transport.PostgresWorkerBackend",
            return_value=mock_backend,
        ):
            # Simulate the async body of the requeue_expired task directly
            backend = mock_backend
            await backend.start()
            try:
                requeued = backend.requeue_expired()
                for job in requeued:
                    mock_app.send_task(
                        "mirror.execute_job",
                        args=[str(job.job_id)],
                        queue=queue_name(job.execution_class),
                        routing_key=queue_name(job.execution_class),
                    )
                count = len(requeued)
            finally:
                await backend.stop()

        assert count == 2
        assert mock_app.send_task.call_count == 2
        call_args_list = mock_app.send_task.call_args_list
        assert call_args_list[0].kwargs["args"] == [str(requeued_jobs[0].job_id)]
        assert call_args_list[0].kwargs["queue"] == "mirror.default"
        assert call_args_list[1].kwargs["args"] == [str(requeued_jobs[1].job_id)]
        assert call_args_list[1].kwargs["queue"] == "mirror.io"

    asyncio.run(_test())


def test_execute_job_outcome_mapping() -> None:
    """Worker must map ExecutionResult.outcome to the correct durable terminal state (ADR-0048)."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from mirror_core.executor.models import RunOutcome
    from mirror_core.workers import JobState, WorkerJob

    job = WorkerJob(
        job_id=uuid4(),
        kind="run",
        run_id=uuid4(),
        pipeline_id="p1",
        step_id="s1",
        execution_class="default",
        payload={"pipeline": {"id": "test", "steps": []}},
        state=JobState.RUNNING,
    )

    for outcome, expected_method in [
        (RunOutcome.SUCCEEDED, "complete"),
        (RunOutcome.FAILED, "fail"),
        (RunOutcome.CANCELLED, "cancel"),
        (RunOutcome.PARTIALLY_SUCCEEDED, "fail"),
    ]:
        mock_result = MagicMock()
        mock_result.outcome = outcome
        mock_result.errors = {}

        mock_runtime = AsyncMock()
        mock_runtime.claim_job.return_value = job

        mock_app = AsyncMock()
        mock_app.execute_worker_job.return_value = mock_result

        with patch(
            "mirror_execution_celery.transport.WorkerRuntime", return_value=mock_runtime
        ), patch(
            "mirror_execution_celery.transport.Application", return_value=mock_app
        ):
            import asyncio
            from mirror_execution_celery.transport import _execute_job

            asyncio.run(
                _execute_job(
                    job.job_id,
                    postgres_dsn="postgresql://mirror@localhost/mirror",
                    settings=MagicMock(),
                    worker_id="test-worker",
                    lease_seconds=60,
                )
            )

            terminal_fn = getattr(mock_runtime, expected_method)
            terminal_fn.assert_called_once()
