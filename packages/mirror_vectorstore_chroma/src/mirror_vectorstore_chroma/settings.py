"""Settings for the Chroma vector store provider."""

from __future__ import annotations

from typing import Literal

from mirror_vectorstore.settings import VectorStoreSettings
from pydantic import Field


class ChromaVectorStoreSettings(VectorStoreSettings):
    """Chroma backend configuration."""

    persist_path: str | None = Field(
        default=None,
        description="Directory for a persistent Chroma store; None uses ephemeral storage.",
    )
    collection_name: str = Field(default="mirror", min_length=1)
    metric: Literal["l2", "cosine", "ip"] = Field(
        default="cosine",
        description="Distance metric used by the HNSW index.",
    )
    dimension: int | None = Field(
        default=None,
        ge=1,
        description="Expected embedding dimension; validated when provided.",
    )
