"""Unit tests for the LLM capability contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mirror_llm.models import LLMRequest, LLMResult, Usage
from mirror_llm.protocol import LLM


def test_llm_request_defaults() -> None:
    req = LLMRequest(text="Hello, world!")
    assert req.text == "Hello, world!"
    assert req.model is None
    assert req.temperature == 0.7
    assert req.max_tokens == 512
    assert req.system is None
    assert req.options == {}


def test_llm_request_custom() -> None:
    req = LLMRequest(
        text="Summarize this",
        model="qwen2.5:0.5b",
        temperature=0.0,
        max_tokens=1024,
        system="You are a summarizer.",
        options={"top_p": 0.9},
    )
    assert req.model == "qwen2.5:0.5b"
    assert req.temperature == 0.0
    assert req.max_tokens == 1024
    assert req.system == "You are a summarizer."
    assert req.options == {"top_p": 0.9}


def test_llm_request_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(text="")


def test_llm_request_rejects_bad_temperature() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(text="hi", temperature=5.0)


def test_llm_request_rejects_zero_max_tokens() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(text="hi", max_tokens=0)


def test_llm_result_defaults() -> None:
    result = LLMResult(text="Hi!", model="test")
    assert result.text == "Hi!"
    assert result.model == "test"
    assert result.finish_reason == "stop"
    assert result.usage.total_tokens == 0


def test_llm_usage_model() -> None:
    usage = Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 30


class _FakeLLM:
    """Minimal class satisfying the LLM protocol for static checks."""

    async def generate(self, request: LLMRequest) -> LLMResult:
        return LLMResult(text=f"echo: {request.text}", model="fake")


def test_fake_llm_satisfies_protocol() -> None:
    assert isinstance(_FakeLLM(), LLM)
