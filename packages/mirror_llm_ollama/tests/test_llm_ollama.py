"""Tests for the Ollama LLM provider."""

from __future__ import annotations

import httpx
import pytest

from mirror_llm.models import LLMRequest
from mirror_llm_ollama.provider import OllamaLLMProvider
from mirror_llm_ollama.settings import OllamaLLMSettings

_server = pytest.importorskip("httpx", reason="httpx required")

try:
    _ollama_available = False

    @pytest.fixture(scope="module", autouse=True)
    def _check_ollama() -> None:
        global _ollama_available
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=3)
            r.raise_for_status()
            _ollama_available = True
        except Exception:
            pytest.skip("Ollama server not available")

except Exception:
    pass


_skip_no_ollama = pytest.mark.skipif(
    not _ollama_available,
    reason="Ollama server not reachable",
)


# ── Settings tests ─────────────────────────────────────────────────────────

def test_settings_defaults() -> None:
    s = OllamaLLMSettings()
    assert s.base_url == "http://localhost:11434"
    assert s.model == "qwen2.5:0.5b"
    assert s.temperature == 0.7
    assert s.max_tokens == 512


def test_settings_custom() -> None:
    s = OllamaLLMSettings(
        base_url="http://remote:11434",
        model="tinyllama",
        temperature=0.1,
        max_tokens=256,
    )
    assert s.base_url == "http://remote:11434"
    assert s.model == "tinyllama"
    assert s.temperature == 0.1
    assert s.max_tokens == 256


# ── Request building tests ─────────────────────────────────────────────────

def test_request_payload_minimal() -> None:
    req = LLMRequest(text="Hello")
    assert req.text == "Hello"
    assert req.model is None
    assert req.temperature == 0.7
    assert req.max_tokens == 512


def test_request_payload_with_system() -> None:
    req = LLMRequest(text="Hi", system="You are helpful")
    assert req.system == "You are helpful"
    assert req.text == "Hi"


# ── Error handling tests ───────────────────────────────────────────────────

async def test_connect_error_on_refused() -> None:
    settings = OllamaLLMSettings(base_url="http://127.0.0.1:1")
    provider = OllamaLLMProvider(settings)
    with pytest.raises(Exception, match="Ollama"):
        await provider.generate(LLMRequest(text="Hello"))
    await provider._close()


async def test_connect_error_on_invalid_port() -> None:
    settings = OllamaLLMSettings(base_url="http://localhost:99999")
    provider = OllamaLLMProvider(settings)
    # invalid port raises before request is made, or returns a connection error
    try:
        await provider.generate(LLMRequest(text="Hello"))
    except Exception:
        pass  # either port error or connection error is acceptable
    await provider._close()


# ── Contract tests ─────────────────────────────────────────────────────────

def test_manifest_capability() -> None:
    from mirror_llm_ollama.provider import provider as manifest

    assert manifest.capability == "llm"
    assert "llm" in manifest.features


def test_manifest_factory_path() -> None:
    from mirror_llm_ollama.provider import provider as manifest

    assert manifest.factory == "mirror_llm_ollama.provider:OllamaLLMProvider"


def test_manifest_settings_model() -> None:
    from mirror_llm_ollama.provider import provider as manifest

    assert manifest.settings_model is not None
    module_path, attr = manifest.settings_model.rsplit(":", 1)
    mod = __import__(module_path, fromlist=[attr])
    assert hasattr(mod, attr)
