"""Transform capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mirror_transform.models import TransformRequest, TransformResult


@runtime_checkable
class Transformer(Protocol):
    """Protocol implemented by transform providers."""

    async def transform(self, request: TransformRequest) -> TransformResult:
        """Reshape the request value into the requested output model."""
