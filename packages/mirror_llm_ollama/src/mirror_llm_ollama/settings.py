"""Settings for the Ollama LLM provider."""

from __future__ import annotations

from pydantic import Field

from mirror_llm.settings import LLMSettings


class OllamaLLMSettings(LLMSettings):
    """Settings for the Ollama LLM provider."""

    base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL of the Ollama HTTP API",
    )
    model: str = Field(
        default="qwen2.5:0.5b",
        description="Ollama model name for generation",
    )
    timeout: float = Field(default=30.0, gt=0, description="Request timeout in seconds")