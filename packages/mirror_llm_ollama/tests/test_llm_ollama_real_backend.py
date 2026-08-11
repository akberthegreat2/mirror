"""Real-backend tests for the Ollama LLM provider (CLAUDE.md §11/§12).

These tests exercise the actual Ollama ``/api/chat`` completion endpoint against
a real local Ollama server. They are opt-in via ``MIRROR_LIVE_TESTS=1``.
"""

from __future__ import annotations

import os

import pytest
from mirror_llm.models import LLMRequest
from mirror_llm_ollama.provider import OllamaLLMProvider
from mirror_llm_ollama.settings import OllamaLLMSettings


def _live_enabled() -> bool:
    return os.environ.get("MIRROR_LIVE_TESTS") == "1"


def _skip_if_no_ollama() -> None:
    if not _live_enabled():
        pytest.skip("Live Ollama tests require MIRROR_LIVE_TESTS=1")


@pytest.mark.asyncio
async def test_llm_ollama_real_generate() -> None:
    _skip_if_no_ollama()
    provider = OllamaLLMProvider()
    result = await provider.generate(LLMRequest(text="What is 2+2? Answer with a single digit."))
    await provider._close()
    assert result.text
    assert "4" in result.text
    assert result.finish_reason in ("stop", "length")
    assert result.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_llm_ollama_real_with_system_prompt() -> None:
    _skip_if_no_ollama()
    provider = OllamaLLMProvider()
    result = await provider.generate(
        LLMRequest(
            text="Who are you?",
            system="You are a concise assistant. Reply in one sentence.",
        )
    )
    await provider._close()
    assert result.text
    assert len(result.text) > 0


@pytest.mark.asyncio
async def test_llm_ollama_custom_model() -> None:
    _skip_if_no_ollama()
    # Use the small distilled model if available; otherwise skip.
    import httpx

    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        r.raise_for_status()
        models = r.json().get("models", [])
        model_names = [m["name"] for m in models]
    except Exception:
        pytest.skip("Ollama server not reachable")

    # Pick any available model, preferring qwen2.5:0.5b if present.
    model = "qwen2.5:0.5b" if "qwen2.5:0.5b" in model_names else model_names[0] if model_names else None
    if not model:
        pytest.skip("No Ollama models available")

    provider = OllamaLLMProvider(OllamaLLMSettings(model=model))
    result = await provider.generate(LLMRequest(text="Say 'hello' in one word."))
    await provider._close()
    assert result.text
