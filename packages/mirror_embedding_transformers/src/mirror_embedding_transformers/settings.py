"""Settings for the sentence-transformers embedding provider."""

from __future__ import annotations

from pydantic import Field

from mirror_embedding.settings import EmbeddingSettings


class TransformersEmbeddingSettings(EmbeddingSettings):
    """Settings for the sentence-transformers embedding provider."""

    model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="HuggingFace model name or path for sentence-transformers",
    )
    batch_size: int = Field(default=32, ge=1, le=256, description="Batch size for encoding")
    device: str = Field(default="cpu", description="PyTorch device: 'cpu', 'cuda', 'mps'")
    normalize_embeddings: bool = Field(default=True, description="L2-normalize output vectors")