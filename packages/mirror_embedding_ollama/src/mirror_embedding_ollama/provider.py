"""Ollama embedding provider wrapping the /api/embeddings endpoint."""

from __future__ import annotations

from typing import Any

import httpx

from mirror_core.extensions.models import ProviderManifest
from mirror_embedding.models import (
    EmbeddingInput,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)
from mirror_embedding.protocol import Embedder

from .settings import OllamaEmbeddingSettings


class OllamaEmbeddingProvider(Embedder):
    """Embed text via the Ollama HTTP API."""

    def __init__(self, settings: OllamaEmbeddingSettings | None = None) -> None:
        self._settings = settings or OllamaEmbeddingSettings()
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Return the HTTP client, creating it lazily on first use."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url,
                timeout=self._settings.timeout,
            )
        return self._client

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Embed a batch of inputs via Ollama's /api/embeddings endpoint."""
        vectors: list[EmbeddingVector] = []
        client = self._get_client()

        for item in request.items:
            embedding_values = await self._call_api(client, item)
            vectors.append(
                EmbeddingVector(
                    item_id=item.item_id,
                    values=tuple(embedding_values),
                    metadata=dict(item.metadata),
                )
            )

        return EmbeddingResult(vectors=vectors)

    async def _call_api(
        self, client: httpx.AsyncClient, item: EmbeddingInput
    ) -> list[float]:
        """Call the Ollama /api/embeddings endpoint for a single item."""
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "prompt": item.text,
        }

        try:
            response = await client.post("/api/embeddings", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Could not connect to Ollama at {self._settings.base_url}. "
                f"Is the Ollama server running?"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama API returned HTTP {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ConnectionError(
                f"Ollama request failed: {exc}"
            ) from exc

        data = response.json()
        return data["embedding"]


provider = ProviderManifest(
    name="ollama",
    capability="embedding",
    capability_api="~=1.0",
    factory="mirror_embedding_ollama.provider:OllamaEmbeddingProvider",
    settings_model="mirror_embedding_ollama.settings:OllamaEmbeddingSettings",
    metadata={"description": "Ollama HTTP embedding provider."},
)
