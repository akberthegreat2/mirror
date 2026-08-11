"""Ollama LLM provider.

Calls the Ollama ``/api/chat`` completion endpoint. The HTTP client is
created lazily on first use and owned by the provider lifecycle.
"""

from __future__ import annotations

import logging

import httpx
from mirror_core.extensions.models import ProviderManifest
from mirror_llm.errors import LLMError
from mirror_llm.models import LLMRequest, LLMResult, Usage
from mirror_llm.protocol import LLM

from .settings import OllamaLLMSettings

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLM):
    """Generate text completions via a local Ollama server."""

    def __init__(self, settings: OllamaLLMSettings | None = None) -> None:
        self._settings = settings or OllamaLLMSettings()
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url,
                timeout=self._settings.timeout,
            )
        return self._client

    async def _close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate(self, request: LLMRequest) -> LLMResult:
        model = request.model or self._settings.model
        client = self._ensure_client()

        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.text})

        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        payload.update(request.options)

        try:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise LLMError(
                f"Could not connect to Ollama at {self._settings.base_url}",
                details={"model": model},
                cause=exc,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"Ollama returned HTTP {response.status_code}",
                details={"model": model, "body": response.text[:500]},
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                "Ollama request failed",
                details={"model": model},
                cause=exc,
            ) from exc

        data = response.json()
        message = data.get("message") or {}
        text = message.get("content") or ""

        usage = Usage(
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
            total_tokens=int(data.get("prompt_eval_count") or 0)
            + int(data.get("eval_count") or 0),
        )
        finish_reason = "stop" if data.get("done") else "length"

        return LLMResult(
            text=text,
            model=str(data.get("model") or model),
            usage=usage,
            finish_reason=finish_reason,
            metadata={
                "provider": "ollama",
                "total_duration_ms": round(int(data.get("total_duration") or 0) / 1_000_000, 2),
            },
        )


provider = ProviderManifest(
    name="ollama",
    capability="llm",
    capability_api="~=1.0",
    factory="mirror_llm_ollama.provider:OllamaLLMProvider",
    settings_model="mirror_llm_ollama.settings:OllamaLLMSettings",
    features=["llm", "local", "offline"],
    priority=10,
    metadata={"description": "Ollama LLM generation provider."},
)
