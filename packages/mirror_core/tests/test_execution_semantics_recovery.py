"""Tests for checkpointing, dead-letter, and resume/replay recovery semantics."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from _execution_semantics_helpers import Payload, TransientProvider
from mirror_core.executor import Executor, RunOutcome
from mirror_core.extensions.models import CapabilityManifest, ProviderManifest
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.pipeline import Pipeline, Step
from mirror_core.planner import Planner
from mirror_core.workers import InMemoryCheckpointStore, InMemoryDeadLetterQueue


@pytest.mark.asyncio
async def test_executor_records_checkpoint_and_dead_letter() -> None:
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
            name="ok",
            capability="demo",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
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
        id="runtime",
        inputs={"value": "int"},
        steps=[
            Step(
                id="first",
                capability="demo",
                provider="ok",
                input={"value": "$pipeline.value"},
                outputs=["result"],
            ),
            Step(
                id="second",
                capability="demo",
                provider="boom",
                input={"value": "first.value"},
                outputs=["result"],
            ),
        ],
    )
    plan = Planner(registry).plan(pipeline)
    checkpoint_store = InMemoryCheckpointStore()
    dead_letters = InMemoryDeadLetterQueue()
    executor = Executor(
        {
            ("demo", "ok"): AsyncMock(run=AsyncMock(return_value=Payload(value=1))),
            ("demo", "boom"): AsyncMock(
                run=AsyncMock(side_effect=RuntimeError("boom"))
            ),
        },
        checkpoint_store=checkpoint_store,
        dead_letter_queue=dead_letters,
    )

    async def runner(provider, request, **kwargs):
        return await provider.run(request)

    result = await executor.execute_run(plan, inputs={"value": 1}, runner=runner)

    assert result.outcome is RunOutcome.PARTIALLY_SUCCEEDED
    checkpoint = checkpoint_store.load(result.run_id, "first")
    assert checkpoint is not None
    assert checkpoint["step_id"] == "first"
    record = dead_letters.get(result.run_id)
    assert record is not None
    assert record.step_id == "second"
    assert record.terminal_status == "partially_succeeded"


@pytest.mark.asyncio
async def test_executor_can_resume_from_checkpoint() -> None:
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
            name="first",
            capability="demo",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    registry.register_provider(
        ProviderManifest(
            name="second",
            capability="demo",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    pipeline = Pipeline(
        id="resume",
        inputs={"value": "int"},
        steps=[
            Step(
                id="first",
                capability="demo",
                provider="first",
                input={"value": "$pipeline.value"},
                outputs=["result", "value"],
            ),
            Step(
                id="second",
                capability="demo",
                provider="second",
                input={"value": "first.value"},
                outputs=["result", "value"],
            ),
        ],
    )
    plan = Planner(registry).plan(pipeline)
    checkpoint_store = InMemoryCheckpointStore()
    executor = Executor(
        {
            ("demo", "first"): AsyncMock(run=AsyncMock(return_value=Payload(value=1))),
            ("demo", "second"): TransientProvider(),
        },
        checkpoint_store=checkpoint_store,
    )

    async def runner(provider, request, **kwargs):
        return await provider.run(request)

    failed = await executor.execute_run(plan, inputs={"value": 0}, runner=runner)
    assert failed.outcome is RunOutcome.PARTIALLY_SUCCEEDED
    latest = checkpoint_store.latest(failed.run_id)
    assert latest is not None
    assert latest[0] == "first"

    resumed = await executor.resume_from_checkpoint(
        plan, run_id=failed.run_id, runner=runner
    )
    assert resumed.run_id == failed.run_id
    assert resumed.outcome is RunOutcome.SUCCEEDED
    assert resumed.results["second"].payload.value == 2


@pytest.mark.asyncio
async def test_executor_replays_dead_letter_from_checkpoint() -> None:
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
            name="first",
            capability="demo",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    registry.register_provider(
        ProviderManifest(
            name="second",
            capability="demo",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    pipeline = Pipeline(
        id="replay",
        inputs={"value": "int"},
        steps=[
            Step(
                id="first",
                capability="demo",
                provider="first",
                input={"value": "$pipeline.value"},
                outputs=["result", "value"],
            ),
            Step(
                id="second",
                capability="demo",
                provider="second",
                input={"value": "first.value"},
                outputs=["result", "value"],
            ),
        ],
    )
    plan = Planner(registry).plan(pipeline)
    checkpoint_store = InMemoryCheckpointStore()
    dead_letters = InMemoryDeadLetterQueue()
    second = TransientProvider()
    executor = Executor(
        {
            ("demo", "first"): AsyncMock(run=AsyncMock(return_value=Payload(value=1))),
            ("demo", "second"): second,
        },
        checkpoint_store=checkpoint_store,
        dead_letter_queue=dead_letters,
    )

    async def runner(provider, request, **kwargs):
        return await provider.run(request)

    failed = await executor.execute_run(plan, inputs={"value": 0}, runner=runner)
    assert failed.outcome is RunOutcome.PARTIALLY_SUCCEEDED
    assert dead_letters.get(failed.run_id) is not None

    replayed = await executor.replay_dead_letter(
        plan, run_id=failed.run_id, runner=runner
    )
    assert replayed.run_id == failed.run_id
    assert replayed.outcome is RunOutcome.SUCCEEDED
    assert dead_letters.get(failed.run_id) is None
