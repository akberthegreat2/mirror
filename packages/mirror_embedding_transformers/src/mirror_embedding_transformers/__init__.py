"""sentence-transformers embedding provider for Mirror Embedding."""

from __future__ import annotations

from .provider import TransformersEmbeddingProvider, provider
from .settings import TransformersEmbeddingSettings

__all__ = ["TransformersEmbeddingProvider", "TransformersEmbeddingSettings", "provider"]