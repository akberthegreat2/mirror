"""Tests for fallback, compensation, and on-error policy semantics."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from _execution_semantics_helpers import (
    FallbackProvider,
    Payload,
    PrimaryProvider,
    Request,
    Result,
)
from mirror_core.executor import Executor, RunOutcome, StepState
from mirror_core.extensions.models import CapabilityManifest, ProviderManifest
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.metadata import InMemoryMetadataStore, MetadataNamespaces
from mirror_core.pipeline import CompensationPolicy, FallbackPolicy, Pipeline, Step
from mirror_core.planner import Planner


@pytest.mark.asyncio
async def test_executor_uses_fallback_provider_when_primary_fails() -> None:
    registry = ExtensionRegistryManager()
    registry.register_capability(
        CapabilityManifest(
            name="fetch",
            api_version="1.0",
            request_model=Request,
            result_model=Result,
            output_ports={"result": Result},
        )
    )
    registry.register_provider(
        ProviderManifest(
            name="primary",
            capability="fetch",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    registry.register_provider(
        ProviderManifest(
            name="fallback",
            capability="fetch",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    pipeline = Pipeline(
        id="fallback",
        inputs={"url": "str"},
        steps=[
            Step(
                id="fetch",
                capability="fetch",
                provider="primary",
                input={"url": "$pipeline.url"},
                outputs=["result"],
                fallback=FallbackPolicy(providers=("fallback",)),
                on_error="fallback",
            )
        ],
    )
    plan = Planner(registry).plan(pipeline)
    executor = Executor(
        {
            ("fetch", "primary"): PrimaryProvider(),
            ("fetch", "fallback"): FallbackProvider(),
        }
    )

    async def runner(provider, request, **kwargs):
        return await provider.run(request)

    result = await executor.execute_run(
        plan, inputs={"url": "https://example.com"}, runner=runner
    )

    assert result.outcome is RunOutcome.SUCCEEDED
    envelope = result.results["fetch"]
    assert envelope.producer.provider == "fallback"
    assert envelope.payload.content == "fallback:https://example.com"


@pytest.mark.asyncio
async def test_executor_records_metadata_and_triggers_compensation() -> None:
    registry = ExtensionRegistryManager()
    registry.register_capability(
        CapabilityManifest(
            name="demo",
            api_version="1.0",
            request_model=Request,
            result_model=Result,
            output_ports={"result": Result},
        )
    )
    registry.register_provider(
        ProviderManifest(
            name="boom",
            capability="demo",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    pipeline = Pipeline(
        id="compensation",
        inputs={"url": "str"},
        steps=[
            Step(
                id="primary",
                capability="demo",
                provider="boom",
                input={"url": "$pipeline.url"},
                outputs=["result"],
                compensation=CompensationPolicy(steps=("cleanup",)),
                on_error="abort",
            )
        ],
    )
    plan = Planner(registry).plan(pipeline)
    metadata_store = InMemoryMetadataStore()
    compensation_handler = AsyncMock()

    class BoomProvider:
        async def run(self, request: Request) -> Result:
            raise RuntimeError("boom")

    executor = Executor(
        {("demo", "boom"): BoomProvider()},
        metadata_store=metadata_store,
        compensation_handler=compensation_handler,
    )

    async def runner(provider, request, **kwargs):
        return await provider.run(request)

    result = await executor.execute_run(
        plan, inputs={"url": "https://example.com"}, runner=runner
    )

    assert result.outcome is RunOutcome.FAILED
    compensation_handler.assert_awaited_once()
    assert (
        metadata_store.get(MetadataNamespaces.EXECUTION_RUNS, str(result.run_id))
        is not None
    )
    step_record = metadata_store.get(
        MetadataNamespaces.STEP_RUNS, f"{result.run_id}:primary"
    )
    assert step_record is not None
    assert step_record.payload["state"] == RunOutcome.FAILED.value
    audit_record = metadata_store.get(
        MetadataNamespaces.AUDIT_EVENTS, f"{result.run_id}:compensation.triggered"
    )
    assert audit_record is not None
    terminal_record = metadata_store.get(
        MetadataNamespaces.TERMINAL_OUTCOMES, str(result.run_id)
    )
    assert terminal_record is not None
    assert terminal_record.payload["outcome"] == RunOutcome.FAILED.value


@pytest.mark.asyncio
@pytest.mark.parametrize("on_error", ["continue", "skip"])
async def test_on_error_policy_controls_dependent_steps(on_error: str) -> None:
    registry = ExtensionRegistryManager()
    registry.register_capability(
        CapabilityManifest(
            name="demo",
            api_version="1.0",
            request_model=Payload,
            result_model=Payload,
            output_ports={"result": Payload},
        )
    )
    registry.register_provider(
        ProviderManifest(
            name="demo",
            capability="demo",
            capability_api="~=1.0",
            factory="tests:test",
        )
    )
    pipeline = Pipeline(
        id=f"error-policy-{on_error}",
        inputs={"value": "int"},
        steps=[
            Step(
                id="failed",
                capability="demo",
                input={"value": "$pipeline.value"},
                outputs=["result"],
                on_error=on_error,
            ),
            Step(
                id="dependent",
                capability="demo",
                input={"value": "failed.value"},
                outputs=["result"],
            ),
            Step(
                id="independent",
                capability="demo",
                input={"value": "$pipeline.value"},
                outputs=["result"],
            ),
        ],
    )
    plan = Planner(registry).plan(pipeline)
    calls: list[str] = []

    async def runner(provider, request, runner_context=None):
        step_id = runner_context.step_id
        calls.append(step_id)
        if step_id == "failed":
            raise RuntimeError("boom")
        return request

    executor = Executor({("demo", "demo"): object()})
    result = await executor.execute_run(plan, inputs={"value": 1}, runner=runner)

    assert result.outcome is RunOutcome.PARTIALLY_SUCCEEDED
    assert result.states["failed"] is StepState.FAILED
    assert result.states["independent"] is StepState.SUCCEEDED
    assert result.states["dependent"] is StepState.SKIPPED
    assert calls.count("failed") == 1
    assert calls.count("independent") == 1
    assert "dependent" not in calls
