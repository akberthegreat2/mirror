"""pgvector provider for Mirror VectorStore."""

from __future__ import annotations

from .provider import PgVectorStoreProvider, provider
from .settings import PgVectorStoreSettings

__all__ = ["PgVectorStoreProvider", "PgVectorStoreSettings", "provider"]