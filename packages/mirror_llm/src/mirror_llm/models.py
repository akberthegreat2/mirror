"""Typed request, result, and settings models for LLM workflows."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """Input for an LLM completion request."""

    text: str = Field(min_length=1, description="The prompt text to generate from")
    model: str | None = Field(default=None, description="Model name override")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=32768)
    system: str | None = Field(default=None, description="System prompt prefix")
    options: dict[str, Any] = Field(default_factory=dict, description="Provider-specific options")


class Usage(BaseModel):
    """Token usage from a generation."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResult(BaseModel):
    """Output of an LLM generation."""

    text: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str = "stop"
    metadata: dict[str, Any] = Field(default_factory=dict)
