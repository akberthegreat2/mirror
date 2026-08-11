"""Celery execution transport backed by Redis and Mirror's durable worker state."""

from __future__ import annotations

import os
from uuid import UUID

from celery import Celery
from celery.utils.log import get_task_logger
from mirror_core.application import Application
from mirror_core.executor.models import RunOutcome
from mirror_core.settings import MirrorSettings
from mirror_core.worker_runtime import WorkerRuntime
from mirror_core.workers import WorkerJob
from mirror_worker_postgres import (
    PostgresCheckpointStore,
    PostgresDeadLetterQueue,
    PostgresLeaseManager,
    PostgresMetadataStore,
    PostgresWorkerBackend,
)

logger = get_task_logger(__name__)
REAPER_QUEUE = "mirror.reaper"


def queue_name(execution_class: str) -> str:
    """Map an execution class to an infrastructure queue name."""
    normalized = execution_class.strip().lower()
    if not normalized or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in normalized
    ):
        raise ValueError(
            "execution_class must contain only letters, numbers, '_' or '-'"
        )
    return f"mirror.{normalized}"


def create_celery_app(
    *, broker_url: str | None = None, app_name: str = "mirror"
) -> Celery:
    """Create the real Celery application used by Mirror workers."""
    broker = broker_url or os.environ.get(
        "MIRROR_CELERY_BROKER_URL", "redis://localhost:6379/0"
    )
    app = Celery(app_name, broker=broker)
    app.conf.update(
        task_ignore_result=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        task_serializer="json",
        accept_content=["json"],
        result_expires=0,
        task_routes={"mirror.requeue_expired": {"queue": REAPER_QUEUE}},
    )
    return app


class CeleryExecutionTransport:
    """Dispatch Mirror jobs to Celery without moving execution semantics into Celery."""

    def __init__(self, backend: PostgresWorkerBackend, app: Celery) -> None:
        self.backend = backend
        self.app = app

    async def submit(self, job: WorkerJob) -> WorkerJob:
        """Persist a job first, then publish only its ID to Redis/Celery."""
        stored = await self.backend.submit(job)
        self.publish(stored)
        return stored

    def publish(self, job: WorkerJob) -> None:
        """Publish an already-persisted job ID to its execution-class queue."""
        self.app.send_task(
            "mirror.execute_job",
            args=[str(job.job_id)],
            queue=queue_name(job.execution_class),
            routing_key=queue_name(job.execution_class),
        )


def configure_worker_task(
    app: Celery,
    *,
    postgres_dsn: str,
    settings: MirrorSettings | None = None,
    worker_id: str | None = None,
    lease_seconds: int = 60,
) -> None:
    """Register the generic Mirror execution task on a Celery app."""
    worker_name = (
        worker_id or os.environ.get("MIRROR_WORKER_ID") or _default_worker_id()
    )

    @app.task(name="mirror.execute_job", bind=False, acks_late=True)
    def execute_job(job_id: str) -> None:
        """Claim and execute one Mirror job; Celery owns no retry policy."""
        import asyncio

        asyncio.run(
            _execute_job(
                UUID(job_id),
                postgres_dsn=postgres_dsn,
                settings=settings or MirrorSettings(),
                worker_id=worker_name,
                lease_seconds=lease_seconds,
            )
        )

    @app.task(name="mirror.requeue_expired", bind=False)
    def requeue_expired() -> int:
        """Requeue expired durable jobs and republish them to execution-class queues.

        A reaper that only changes PostgreSQL state is incomplete (CLAUDE.md §8).
        The requeued jobs must be republished to their execution-class queue so a
        worker can claim and resume them.
        """
        import asyncio

        async def _requeue() -> int:
            backend = PostgresWorkerBackend(postgres_dsn, lease_seconds=lease_seconds)
            await backend.start()
            try:
                requeued = backend.requeue_expired()
                for job in requeued:
                    app.send_task(
                        "mirror.execute_job",
                        args=[str(job.job_id)],
                        queue=queue_name(job.execution_class),
                        routing_key=queue_name(job.execution_class),
                    )
                    logger.info(
                        "Reaper republished requeued job %s (class=%s)",
                        job.job_id,
                        job.execution_class,
                    )
                return len(requeued)
            finally:
                await backend.stop()

        return asyncio.run(_requeue())

    interval = float(os.environ.get("MIRROR_REAPER_INTERVAL_SECONDS", "15"))
    if interval <= 0:
        raise ValueError("MIRROR_REAPER_INTERVAL_SECONDS must be greater than zero")
    beat_schedule = dict(app.conf.beat_schedule or {})
    beat_schedule["mirror-lease-reaper"] = {
        "task": "mirror.requeue_expired",
        "schedule": interval,
        "options": {"queue": REAPER_QUEUE},
    }
    app.conf.beat_schedule = beat_schedule


def _default_worker_id() -> str:
    import socket
    import uuid

    return f"{socket.gethostname()}-{uuid.uuid4().hex[:12]}"


async def _execute_job(
    job_id: UUID,
    *,
    postgres_dsn: str,
    settings: MirrorSettings,
    worker_id: str,
    lease_seconds: int,
) -> None:
    backend = PostgresWorkerBackend(postgres_dsn, lease_seconds=lease_seconds)
    metadata = PostgresMetadataStore(postgres_dsn)
    checkpoints = PostgresCheckpointStore(postgres_dsn)
    dead_letters = PostgresDeadLetterQueue(postgres_dsn)
    leases = PostgresLeaseManager(postgres_dsn, ttl_seconds=lease_seconds)
    runtime = WorkerRuntime(
        backend,
        metadata_store=metadata,
        checkpoint_store=checkpoints,
        dead_letter_queue=dead_letters,
        lease_manager=leases,
    )
    await runtime.start()
    try:
        job = await runtime.claim_job(job_id, worker_id)
        if job is None:
            logger.info("Job %s was already claimed or completed", job_id)
            return
        heartbeat_task = __import__("asyncio").create_task(
            _heartbeat_loop(runtime, worker_id, job.job_id, lease_seconds)
        )
        try:
            app = Application(
                settings=settings,
                metadata_store=metadata,
                checkpoint_store=checkpoints,
                dead_letter_queue=dead_letters,
            )
            await app.start()
            try:
                result = await app.execute_worker_job(job)
            finally:
                await app.shutdown()
            # Map execution outcome to durable job terminal state (CLAUDE.md §9).
            # A successful worker-function return without SUCCEEDED is never
            # treated as success.
            if result.outcome is RunOutcome.SUCCEEDED:
                await runtime.complete(job.job_id)
            elif result.outcome is RunOutcome.CANCELLED:
                await runtime.cancel(job.job_id, reason="pipeline cancelled")
            else:
                # FAILED or PARTIALLY_SUCCEEDED → durable job is FAILED
                error_summary = "; ".join(
                    f"{step}: {err}" for step, err in result.errors.items()
                ) or f"execution outcome: {result.outcome.value}"
                await runtime.fail(job.job_id, error_summary)
        except BaseException as exc:
            await runtime.fail(job.job_id, str(exc), terminal=True)
            raise
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except __import__("asyncio").CancelledError:
                pass
    finally:
        await runtime.stop()
        metadata.close()
        checkpoints.close()
        dead_letters.close()
        leases.close()


async def _heartbeat_loop(
    runtime: WorkerRuntime, worker_id: str, job_id: UUID, lease_seconds: int
) -> None:
    import asyncio

    interval = max(1.0, lease_seconds / 3)
    while True:
        await asyncio.sleep(interval)
        await runtime.heartbeat(worker_id, job_id)
