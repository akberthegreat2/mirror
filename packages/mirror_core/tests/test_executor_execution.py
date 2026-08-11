"""Tests for basic isolated execution runs and producer/resource tracking."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from _executor_helpers import MockRequest, MockResult, make_plan, runner
from mirror_core.executor import Executor, RunOutcome, StepState
from mirror_core.pipeline import Step


@pytest.mark.asyncio
async def test_executor_uses_runtime_inputs_and_accurate_producer() -> None:
    provider = AsyncMock()
    provider.fetch = AsyncMock(return_value=MockResult(content="hello"))
    plan = make_plan(
        Step(
            id="fetch_page",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        )
    )
    executor = Executor({("fetch", "httpx"): provider})

    result = await executor.execute_run(
        plan,
        inputs={"url": "https://example.com"},
        runner=runner,
    )

    assert result.outcome is RunOutcome.SUCCEEDED
    envelope = result.results["fetch_page"]
    assert envelope.producer.capability == "fetch"
    assert envelope.producer.capability_version == "1.2"
    assert envelope.producer.provider == "httpx"
    assert envelope.producer.step_id == "fetch_page"
    assert envelope.parents == ()
    provider.fetch.assert_awaited_once_with(MockRequest(url="https://example.com"))


@pytest.mark.asyncio
async def test_executor_does_not_force_keyword_arguments() -> None:
    provider = AsyncMock()
    provider.fetch = AsyncMock(return_value=MockResult(content="hello"))
    plan = make_plan(
        Step(
            id="fetch_page",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        ),
    )
    executor = Executor({("fetch", "httpx"): provider})

    result = await executor.execute_run(
        plan,
        inputs={"url": "https://example.com"},
        runner=runner,
    )

    assert result.outcome is RunOutcome.SUCCEEDED
    provider.fetch.assert_awaited_once_with(MockRequest(url="https://example.com"))


@pytest.mark.asyncio
async def test_executor_tracks_only_direct_resource_parents() -> None:
    provider = AsyncMock()
    provider.fetch = AsyncMock(
        side_effect=[MockResult(content="a"), MockResult(content="b")]
    )
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        ),
        Step(
            id="b", capability="fetch", input={"url": "a.content"}, outputs=["result"]
        ),
    )
    executor = Executor({("fetch", "httpx"): provider}, max_concurrency=1)

    result = await executor.execute_run(
        plan, inputs={"url": "https://example.com"}, runner=runner
    )

    assert result.results["b"].parents == (result.results["a"].resource_id,)


@pytest.mark.asyncio
async def test_executor_condition_can_skip_step() -> None:
    provider = AsyncMock()
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
            condition="false",
        )
    )
    executor = Executor({("fetch", "httpx"): provider})

    result = await executor.execute_run(plan, inputs={"url": "x"}, runner=runner)

    assert result.states["a"] is StepState.SKIPPED
    assert result.outcome is RunOutcome.SUCCEEDED
    provider.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_runs_do_not_share_state() -> None:
    provider = AsyncMock()
    provider.fetch = AsyncMock(
        side_effect=lambda request: MockResult(content=request.url)
    )
    plan = make_plan(
        Step(
            id="a",
            capability="fetch",
            input={"url": "$pipeline.url"},
            outputs=["result"],
        )
    )
    executor = Executor({("fetch", "httpx"): provider})

    first, second = await __import__("asyncio").gather(
        executor.execute_run(plan, inputs={"url": "one"}, runner=runner),
        executor.execute_run(plan, inputs={"url": "two"}, runner=runner),
    )

    assert first.run_id != second.run_id
    assert first.results["a"].payload.content == "one"
    assert second.results["a"].payload.content == "two"
