"""Settings for the LLM capability."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    """Runtime defaults for LLM generation."""

    model: str = Field(default="", description="Default model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=32768)