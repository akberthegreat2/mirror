"""Mirror Ollama embedding provider."""

from .provider import OllamaEmbeddingProvider, provider
from .settings import OllamaEmbeddingSettings

__all__ = ["OllamaEmbeddingProvider", "OllamaEmbeddingSettings", "provider"]
