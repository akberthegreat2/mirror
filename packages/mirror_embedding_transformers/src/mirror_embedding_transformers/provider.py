"""sentence-transformers embedding provider.

Uses a SentenceTransformer model for generating embeddings.
Model is loaded lazily on first embed() call.
"""

from __future__ import annotations

import logging
from typing import Any

from mirror_core.extensions.models import ProviderManifest
from mirror_embedding.models import (
    EmbeddingInput,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)
from mirror_embedding.protocol import Embedder

from .settings import TransformersEmbeddingSettings

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore


class TransformersEmbeddingProvider(Embedder):
    """Embed text via a local sentence-transformers model."""

    def __init__(self, settings: TransformersEmbeddingSettings | None = None) -> None:
        self._settings = settings or TransformersEmbeddingSettings()
        self._model: Any = None  # SentenceTransformer instance

    def _ensure_model(self) -> Any:
        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install mirror-embedding-transformers"
            )
        if self._model is None:
            logger.info("Loading sentence-transformers model: %s", self._settings.model_name)
            self._model = SentenceTransformer(
                self._settings.model_name,
                device=self._settings.device,
            )
        return self._model

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        model = self._ensure_model()
        texts = [item.text for item in request.items]

        embeddings = model.encode(
            texts,
            batch_size=self._settings.batch_size,
            normalize_embeddings=self._settings.normalize_embeddings,
            show_progress_bar=False,
        )

        vectors: list[EmbeddingVector] = []
        for i, item in enumerate(request.items):
            vectors.append(
                EmbeddingVector(
                    item_id=item.item_id,
                    values=tuple(float(v) for v in embeddings[i]),
                    metadata=dict(item.metadata),
                )
            )

        return EmbeddingResult(vectors=vectors)


provider = ProviderManifest(
    name="transformers",
    capability="embedding",
    capability_api="~=1.0",
    factory="mirror_embedding_transformers.provider:TransformersEmbeddingProvider",
    settings_model="mirror_embedding_transformers.settings:TransformersEmbeddingSettings",
    features=["embedding", "transformers", "local", "offline"],
    metadata={"description": "sentence-transformers local embedding provider."},
)