"""Tests for the Transform capability."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from mirror_transform.capability import capability
from mirror_transform.errors import TransformError
from mirror_transform.models import TransformRequest, TransformResult
from mirror_transform.runner import transform_step
from pydantic import ValidationError


def test_capability_descriptor() -> None:
    """Capability manifest should expose the transform contract."""

    assert capability.name == "transform"
    assert capability.request_model == TransformRequest
    assert capability.result_model == TransformResult
    assert capability.runner == "mirror_transform.runner:transform_step"


def test_transform_request_requires_output_type() -> None:
    """A transform request must name the target model."""

    with pytest.raises(ValidationError):
        TransformRequest(value={"a": 1})


@pytest.mark.asyncio
async def test_transform_step_success() -> None:
    """The runner should delegate to the provider."""

    provider = AsyncMock()
    request = TransformRequest(value={"a": 1}, output_type="pkg:Model")
    expected = TransformResult(value={"a": 1}, produced_type="pkg:Model")
    provider.transform.return_value = expected

    result = await transform_step(provider, request)

    assert result == expected
    provider.transform.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_transform_step_wraps_provider_failure() -> None:
    """The runner should translate provider failures into TransformError."""

    provider = AsyncMock()
    provider.transform.side_effect = RuntimeError("boom")
    request = TransformRequest(value=1, output_type="pkg:Model")

    with pytest.raises(TransformError) as exc_info:
        await transform_step(provider, request)

    assert exc_info.value.cause is not None
