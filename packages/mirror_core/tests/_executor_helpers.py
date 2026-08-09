"""Shared helpers for the executor test modules.

This module is intentionally named with a leading underscore so pytest does
not collect it as a test module (it also does not match ``test_*.py``).
"""

from __future__ import annotations

from mirror_core.extensions.models import CapabilityManifest, ProviderManifest
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.pipeline import Pipeline, Step
from mirror_core.planner import Planner
from pydantic import BaseModel


class MockRequest(BaseModel):
    url: str


class MockResult(BaseModel):
    content: str
    status: int = 200


def make_plan(*steps: Step):
    registry = ExtensionRegistryManager()
    registry.register_capability(
        CapabilityManifest(
            name="fetch",
            api_version="1.2",
            request_model=MockRequest,
            result_model=MockResult,
            output_ports={"result": MockResult},
        )
    )
    registry.register_provider(
        ProviderManifest(
            name="httpx",
            capability="fetch",
            capability_api="~=1.0",
            factory="test:provider",
            metadata={"version": "0.9"},
        )
    )
    pipeline = Pipeline(
        id="test",
        steps=list(steps),
        inputs={"url": "str"},
    )
    return Planner(registry, default_providers={"fetch": "httpx"}).plan(pipeline)


async def runner(provider, request, runner_context=None):
    return await provider.fetch(request)
