"""Tests for executor control features: middleware, retry, and resume validation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from _executor_helpers import MockResult, make_plan, runner
from mirror_core.exceptions import ExecutionError
from mirror_core.executor import Executor, RunOutcome
from mirror_core.middleware import MiddlewareChain, MiddlewareInvocation
from mirror_core.pipeline import Step


@pytest.mark.asyncio
async def test_middleware_can_short_circuit_provider() -> None:
    provider = AsyncMock()

    class CacheMiddleware:
        async def __call__(self, invocation: MiddlewareInvocation, next_middleware):
            return MockResult(content="cached")

    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        )
    )
    executor = Executor(
        {("fetch", "httpx"): provider},
        middleware_chain=MiddlewareChain([CacheMiddleware()]),
    )

    result = await executor.execute_run(plan, inputs={"url": "x"}, runner=runner)

    assert result.results["a"].payload == MockResult(content="cached")
    provider.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_step_retry_policy_is_enforced() -> None:
    from mirror_core.pipeline import RetryPolicy

    provider = AsyncMock()
    provider.fetch = AsyncMock(
        side_effect=[ValueError("temporary"), MockResult(content="recovered")]
    )
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
            retry=RetryPolicy(attempts=2),
        )
    )
    executor = Executor({("fetch", "httpx"): provider})

    result = await executor.execute_run(plan, inputs={"url": "x"}, runner=runner)

    assert result.outcome is RunOutcome.SUCCEEDED
    assert provider.fetch.await_count == 2


@pytest.mark.asyncio
async def test_resume_rejects_unknown_checkpoint_steps() -> None:
    from mirror_core.workers import InMemoryCheckpointStore

    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        )
    )
    checkpoint = InMemoryCheckpointStore()
    run_id = __import__("uuid").UUID("00000000-0000-0000-0000-000000000999")
    checkpoint.save(
        run_id,
        "a",
        {
            "run_id": str(run_id),
            "pipeline_id": plan.pipeline_id,
            "step_id": "a",
            "states": {"ghost": "running"},
            "results": {},
            "errors": {},
            "retry_counts": {},
            "failed_step_id": None,
            "cancelled": False,
            "inputs": {"url": "x"},
        },
    )
    executor = Executor({("fetch", "httpx"): AsyncMock()}, checkpoint_store=checkpoint)

    with pytest.raises(ExecutionError, match="unknown step ids"):
        await executor.resume_from_checkpoint(
            plan, run_id=run_id, inputs={"url": "x"}, runner=runner
        )
