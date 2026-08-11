"""Shared helpers for the execution semantics test modules.

This module is intentionally named with a leading underscore so pytest does
not collect it as a test module (it also does not match ``test_*.py``).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from mirror_core.executor import Executor
from mirror_core.extensions.models import CapabilityManifest, ProviderManifest
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.pipeline import Pipeline, Step
from mirror_core.planner import Planner
from pydantic import BaseModel


class Request(BaseModel):
    url: str


class Result(BaseModel):
    content: str


class Payload(BaseModel):
    value: int


def _plan() -> tuple[Executor, object]:
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
            name="httpx",
            capability="fetch",
            capability_api="~=1.0",
            factory="tests:test",
            metadata={"version": "1.0"},
        )
    )
    pipeline = Pipeline(
        id="runtime",
        inputs={"url": "str"},
        steps=[
            Step(
                id="fetch",
                capability="fetch",
                input={"url": "$pipeline.url"},
                outputs=["result"],
            )
        ],
    )
    plan = Planner(registry, default_providers={"fetch": "httpx"}).plan(pipeline)
    executor = Executor({("fetch", "httpx"): AsyncMock()})
    return executor, plan


class PrimaryProvider:
    async def run(self, request: Request) -> Result:
        raise RuntimeError("primary failed")


class FallbackProvider:
    async def run(self, request: Request) -> Result:
        return Result(content=f"fallback:{request.url}")


class TransientProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, request: Payload) -> Payload:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient failure")
        return Payload(value=request.value + 1)
