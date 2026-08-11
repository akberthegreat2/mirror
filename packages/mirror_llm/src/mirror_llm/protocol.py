"""LLM capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import LLMRequest, LLMResult


@runtime_checkable
class LLM(Protocol):
    """Protocol implemented by LLM providers."""

    async def generate(self, request: LLMRequest) -> LLMResult:
        """Generate a completion from the given prompt."""
        ...
