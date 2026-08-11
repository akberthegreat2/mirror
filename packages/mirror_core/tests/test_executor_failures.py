"""Tests for executor failure, abort, timeout, and cancellation handling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from _executor_helpers import MockRequest, MockResult, make_plan, runner
from mirror_core.exceptions import ExecutionError
from mirror_core.executor import Executor, RunOutcome, StepState
from mirror_core.pipeline import Step


@pytest.mark.asyncio
async def test_executor_abort_is_reported_and_raised() -> None:
    provider = AsyncMock()
    provider.fetch = AsyncMock(side_effect=ValueError("network failed"))
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
            on_error="abort",
        ),
        Step(
            id="b",
            capability="fetch",
            input={"url": "a.content"},
            outputs=["result"],
        ),
    )
    executor = Executor({("fetch", "httpx"): provider})

    with pytest.raises(ExecutionError, match="network failed"):
        await executor.execute(plan, inputs={"url": "x"}, runner=runner)

    assert executor.last_run is not None
    assert executor.last_run.outcome is RunOutcome.FAILED
    assert executor.last_run.states["a"] is StepState.FAILED
    assert executor.last_run.states["b"] in {StepState.CANCELLED, StepState.SKIPPED}


@pytest.mark.asyncio
async def test_step_timeout_is_enforced() -> None:
    import asyncio

    provider = AsyncMock()

    async def slow_fetch(request: MockRequest) -> MockResult:
        await asyncio.sleep(1)
        return MockResult(content="late")

    provider.fetch = slow_fetch
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
            timeout=0.01,
        )
    )
    executor = Executor({("fetch", "httpx"): provider})

    result = await executor.execute_run(plan, inputs={"url": "x"}, runner=runner)

    assert result.outcome is RunOutcome.FAILED
    assert result.states["a"] is StepState.FAILED


@pytest.mark.asyncio
async def test_cancel_stops_a_running_task() -> None:
    import asyncio

    started = asyncio.Event()
    cancelled = asyncio.Event()
    provider = AsyncMock()

    async def blocking_fetch(request: MockRequest) -> MockResult:
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return MockResult(content="never")

    provider.fetch = blocking_fetch
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        )
    )
    executor = Executor({("fetch", "httpx"): provider})
    task = asyncio.create_task(
        executor.execute_run(plan, inputs={"url": "x"}, runner=runner)
    )
    await started.wait()
    run_id = next(iter(executor._active_runs))
    executor.cancel(run_id)
    result = await task

    assert cancelled.is_set()
    assert result.outcome is RunOutcome.CANCELLED
    assert result.states["a"] is StepState.CANCELLED


@pytest.mark.asyncio
async def test_abort_after_prior_success_is_partially_succeeded() -> None:
    provider = AsyncMock()
    provider.fetch = AsyncMock(
        side_effect=[MockResult(content="ok"), ValueError("boom")]
    )
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        ),
        Step(
            id="b",
            capability="fetch",
            input={"url": "a.content"},
            outputs=["result"],
            on_error="abort",
        ),
    )
    executor = Executor({("fetch", "httpx"): provider})

    result = await executor.execute_run(plan, inputs={"url": "x"}, runner=runner)

    assert result.outcome is RunOutcome.PARTIALLY_SUCCEEDED
    assert result.states["a"] is StepState.SUCCEEDED
    assert result.states["b"] is StepState.FAILED
