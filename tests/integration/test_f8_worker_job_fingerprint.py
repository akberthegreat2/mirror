"""Regression tests for the distributed job config fingerprint (F8).

The submitter and the worker must compute ``config_fingerprint`` over the same
provider-baked pipeline. The submitter resolves providers, bakes the selections
into the serialized pipeline, and fingerprints that baked pipeline; the worker
rebakes the same selections before compiling. Before the fix, the submitter
fingerprinted the raw (unbaked) pipeline, which can never match the worker's
baked compilation, so every CLI-submitted job was rejected.
"""

from __future__ import annotations

import pytest
from mirror_core.application import Application, bake_provider_selections
from mirror_core.exceptions import ApplicationError
from mirror_core.pipeline import Pipeline
from mirror_core.settings import MirrorSettings
from mirror_core.workers import WorkerJob

TRANSFORM_PIPELINE = {
    "id": "transform-job",
    "version": "1.0",
    "inputs": {},
    "steps": [
        {
            "id": "make_docs",
            "capability": "transform",
            "input": {
                "value": {"document_id": "doc-1", "text": "hello mirror"},
                "output_type": "mirror_chunk.models:ChunkDocument",
                "mapping": {"document_id": "document_id", "text": "text"},
            },
            "outputs": ["result"],
        }
    ],
}


def _cli_built_job(app: Application, fingerprint: str) -> WorkerJob:
    """Build the job exactly as the mirror_execution_celery submit CLI does."""
    pipeline_model = Pipeline.model_validate(TRANSFORM_PIPELINE)
    plan = app.compile_pipeline(pipeline_model)
    provider_selections = {step_id: compiled.provider.name for step_id, compiled in plan.steps.items()}
    return WorkerJob(
        kind="pipeline",
        pipeline_id=pipeline_model.id,
        execution_class="default",
        payload={
            "pipeline": TRANSFORM_PIPELINE,
            "inputs": {},
            "provider_selections": provider_selections,
            "config_fingerprint": fingerprint,
        },
    )


async def test_worker_job_fingerprint_over_baked_pipeline() -> None:
    app = Application(MirrorSettings())
    await app.start()
    try:
        pipeline_model = Pipeline.model_validate(TRANSFORM_PIPELINE)
        plan = app.compile_pipeline(pipeline_model)
        provider_selections = {step_id: compiled.provider.name for step_id, compiled in plan.steps.items()}
        baked = bake_provider_selections(pipeline_model, provider_selections)
        baked_plan = app.compile_pipeline(baked)

        # Baking pins the provider into the as-written pipeline, so the baked
        # fingerprint must differ from the raw one; otherwise the original
        # fingerprint mismatch could never have reproduced.
        assert baked_plan.config_fingerprint != plan.config_fingerprint

        job = _cli_built_job(app, baked_plan.config_fingerprint)
        result = await app.execute_worker_job(job)
    finally:
        await app.shutdown()

    assert result.outcome.value == "succeeded"
    transformed = result.results["make_docs"].payload.value
    assert transformed.document_id == "doc-1"
    assert transformed.text == "hello mirror"


async def test_worker_job_rejects_raw_pipeline_fingerprint() -> None:
    """The pre-F8 CLI sent the raw pipeline's fingerprint, which can never
    match the worker's baked compilation, so every submitted job was rejected."""
    app = Application(MirrorSettings())
    await app.start()
    try:
        pipeline_model = Pipeline.model_validate(TRANSFORM_PIPELINE)
        plan = app.compile_pipeline(pipeline_model)
        job = _cli_built_job(app, plan.config_fingerprint)
        with pytest.raises(ApplicationError, match="fingerprint does not match"):
            await app.execute_worker_job(job)
    finally:
        await app.shutdown()
