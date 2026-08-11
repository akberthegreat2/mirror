"""Settings for the Ollama embedding provider."""

from mirror_embedding.settings import EmbeddingSettings


class OllamaEmbeddingSettings(EmbeddingSettings):
    """Runtime settings for Ollama-backed text embeddings."""

    base_url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"
    timeout: float = 30.0
