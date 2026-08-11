"""Settings for the pgvector vector store provider."""

from __future__ import annotations

from typing import Literal

from mirror_vectorstore.settings import VectorStoreSettings
from pydantic import Field


class PgVectorStoreSettings(VectorStoreSettings):
    """pgvector backend configuration."""

    dsn: str = Field(
        default="postgresql://mirror:mirror@localhost:5433/mirror",
        description="PostgreSQL connection string.",
    )
    table_prefix: str = Field(
        default="mirror_vectors",
        description="Table name prefix; actual table is {prefix}_{namespace}.",
    )
    metric: Literal["l2", "cosine", "inner_product"] = Field(
        default="cosine",
        description="Distance metric for pgvector index.",
    )
    dimension: int | None = Field(
        default=None,
        ge=1,
        description="Expected embedding dimension; used for index creation.",
    )
    ef_construction: int = Field(
        default=64,
        ge=16,
        description="HNSW index ef_construction parameter.",
    )
    m: int = Field(
        default=16,
        ge=2,
        description="HNSW index M parameter (max connections per layer).",
    )