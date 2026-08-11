"""Tests for the ADR-0025 runtime context and policy contracts."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from _execution_semantics_helpers import Result, _plan
from mirror_core.execution import CapabilityContext, ExecutionContext, ExecutionPolicy
from mirror_core.executor import RunOutcome
from mirror_core.resource import ProducerRef, ResourceEnvelope


@pytest.mark.asyncio
async def test_executor_passes_runtime_contexts_to_runners() -> None:
    provider = AsyncMock()
    provider.fetch = AsyncMock(return_value=Result(content="ok"))
    executor, plan = _plan()
    executor.components = {("fetch", "httpx"): provider}

    seen: dict[str, object] = {}

    async def runner(provider, request, runner_context=None):
        seen["execution_context"] = (
            runner_context.execution_context if runner_context else None
        )
        seen["capability_context"] = (
            runner_context.capability_context if runner_context else None
        )
        seen["middleware_context"] = (
            runner_context.middleware_context if runner_context else None
        )
        seen["signal_bus"] = runner_context.signal_bus if runner_context else None
        seen["step_id"] = runner_context.step_id if runner_context else None
        return await provider.fetch(request)

    result = await executor.execute_run(
        plan, inputs={"url": "https://example.com"}, runner=runner
    )

    assert result.outcome is RunOutcome.SUCCEEDED
    execution_context = seen["execution_context"]
    capability_context = seen["capability_context"]
    middleware_context = seen["middleware_context"]
    assert isinstance(execution_context, ExecutionContext)
    assert isinstance(capability_context, CapabilityContext)
    assert middleware_context.step_id == "fetch"
    assert capability_context.execution is execution_context
    assert capability_context.step_id == "fetch"
    assert capability_context.provider == "httpx"
    assert capability_context.policy.on_error == "abort"
    assert seen["step_id"] == "fetch"
    assert seen["signal_bus"] is executor.signal_bus


def test_execution_context_is_immutable_snapshot() -> None:
    execution = ExecutionContext(
        run_id=__import__("uuid").uuid4(),
        pipeline_id="demo",
        inputs={"url": "https://example.com"},
        results={},
        metadata={"source": "test"},
    )

    with pytest.raises(TypeError):
        execution.inputs["url"] = "changed"  # type: ignore[index]

    assert execution.metadata["source"] == "test"


def test_capability_context_uses_explicit_execution_policy() -> None:
    execution = ExecutionContext(
        run_id=__import__("uuid").uuid4(),
        pipeline_id="demo",
    )
    policy = ExecutionPolicy(on_error="continue")
    context = CapabilityContext.from_execution(
        execution,
        step_id="step-1",
        capability="fetch",
        capability_version="1.0",
        provider="httpx",
        provider_version="1.0",
        policy=policy,
        metadata={"provider": "httpx"},
    )

    assert context.execution is execution
    assert context.policy == policy
    assert context.metadata["provider"] == "httpx"


def test_resource_envelope_deep_copies_payload() -> None:
    payload = Result(content="before")
    envelope = ResourceEnvelope.create(
        resource_type="Result",
        schema_version="1.0",
        payload=payload,
        producer=ProducerRef(
            capability="fetch",
            capability_version="1.0",
            provider="httpx",
        ),
    )

    payload.content = "after"
    assert envelope.payload.content == "before"
