"""Settings for the semantic chunk provider."""

from __future__ import annotations

from pydantic import Field

from mirror_chunk.settings import ChunkSettings


class SemanticChunkSettings(ChunkSettings):
    """Settings for embedding-aware semantic chunking."""

    model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="sentence-transformers model for sentence embeddings",
    )
    similarity_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity between consecutive sentences to keep them in one chunk",
    )
    batch_size: int = Field(default=32, ge=1, le=256, description="Batch size for encoding")
    device: str = Field(default="cpu", description="PyTorch device: 'cpu', 'cuda', 'mps'")