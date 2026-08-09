"""Command-line bootstrap for a generic Mirror Celery worker."""

from __future__ import annotations

import argparse
import os

from .transport import (
    REAPER_QUEUE,
    CeleryExecutionTransport,
    configure_worker_task,
    create_celery_app,
    queue_name,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a generic Mirror Celery worker")
    parser.add_argument("--execution-class", default="default")
    parser.add_argument("--worker-id", default=None)
    parser.add_argument("--loglevel", default="INFO")
    args = parser.parse_args()

    postgres_dsn = os.environ.get("MIRROR_POSTGRES_DSN")
    if not postgres_dsn:
        raise SystemExit("MIRROR_POSTGRES_DSN is required")
    app = create_celery_app()
    configure_worker_task(app, postgres_dsn=postgres_dsn, worker_id=args.worker_id)
    app.worker_main(
        [
            "worker",
            "--loglevel",
            args.loglevel,
            "--queues",
            f"{queue_name(args.execution_class)},{REAPER_QUEUE}",
            "--hostname",
            f"mirror@{args.worker_id or 'worker'}",
        ]
    )


def submit_main() -> None:
    """Submit a serialized Mirror pipeline to the distributed worker pool."""
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="Submit a Mirror pipeline to Celery")
    parser.add_argument("pipeline", help="JSON file containing a Mirror pipeline")
    parser.add_argument("--inputs", default="{}", help="JSON object containing pipeline inputs")
    parser.add_argument("--execution-class", default="default")
    args = parser.parse_args()

    from mirror_core.application import Application, bake_provider_selections
    from mirror_core.pipeline import Pipeline
    from mirror_core.workers import WorkerJob
    from mirror_worker_postgres import PostgresWorkerBackend

    postgres_dsn = os.environ.get("MIRROR_POSTGRES_DSN")
    if not postgres_dsn:
        raise SystemExit("MIRROR_POSTGRES_DSN is required")
    with open(args.pipeline, encoding="utf-8") as stream:
        pipeline_data = json.load(stream)
    inputs = json.loads(args.inputs)
    app = create_celery_app()
    backend = PostgresWorkerBackend(postgres_dsn)
    transport = CeleryExecutionTransport(backend, app)

    async def submit() -> None:
        mirror_app = Application()
        await mirror_app.start()
        try:
            pipeline_model = Pipeline.model_validate(pipeline_data)
            plan = mirror_app.compile_pipeline(pipeline_model)
            provider_selections = {step_id: compiled.provider.name for step_id, compiled in plan.steps.items()}
            # The worker rebakes selections into the pipeline before compiling,
            # so the fingerprint must be computed over the same baked pipeline
            # or the two compilations can never match.
            baked = bake_provider_selections(pipeline_model, provider_selections)
            baked_plan = mirror_app.compile_pipeline(baked)
        finally:
            await mirror_app.shutdown()
        await backend.start()
        try:
            job = WorkerJob(
                kind="pipeline",
                pipeline_id=pipeline_model.id,
                execution_class=args.execution_class,
                payload={
                    "pipeline": pipeline_data,
                    "inputs": inputs,
                    "provider_selections": provider_selections,
                    "config_fingerprint": baked_plan.config_fingerprint,
                },
            )
            stored = await transport.submit(job)
            print(stored.job_id)
        finally:
            await backend.stop()

    asyncio.run(submit())


def beat_main() -> None:
    """Run Celery Beat for Mirror's durable lease-reaper schedule."""
    import argparse

    parser = argparse.ArgumentParser(description="Run the Mirror Celery Beat scheduler")
    parser.add_argument("--loglevel", default="INFO")
    args = parser.parse_args()

    postgres_dsn = os.environ.get("MIRROR_POSTGRES_DSN")
    if not postgres_dsn:
        raise SystemExit("MIRROR_POSTGRES_DSN is required")
    app = create_celery_app()
    configure_worker_task(app, postgres_dsn=postgres_dsn)
    app.start(["beat", "--loglevel", args.loglevel])
